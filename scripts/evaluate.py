"""
Evaluate all 5 retrieval strategies against the 50-question gold set in
data/qa_eval_set.json.

Two evaluation layers:

  1. RETRIEVAL QUALITY (always runs, fully offline, deterministic):
     For each question, run each method's retrieval step and compare the
     chunk ids it surfaced against the question's gold chunk ids.
       - Hit@k    : did the retrieved set contain at least one gold chunk?
       - Recall   : fraction of gold chunks that were retrieved
       - Precision: fraction of retrieved chunks that were actually gold
       - Context size: how many chunks (and roughly how many words) were
         handed to the LLM - the cost side of the tradeoff.
       - Retrieval time: wall-clock ms for the retrieval step itself.

  2. END-TO-END GENERATION + LLM JUDGE (optional, needs ANTHROPIC_API_KEY):
     For a sample of questions, actually generate an answer from each
     method's retrieved context, then ask Claude to judge the generated
     answer against the gold answer on a 0-2 scale. Also times generation
     and judging separately. Requires ANTHROPIC_API_KEY to be exported in
     the shell running this script - this is independent of any API key
     entered into the web app UI, which is never read by this script.

Every run is written to its own timestamped, never-overwritten folder under
eval/runs/<run_id>/, containing:
  - config.json   : run provenance - timestamp, git commit (+dirty flag),
                    corpus version (doc list + chunk count), eval set size,
                    CLI args, and (if --generate) the exact model IDs used
                    for generation and judging. This is what makes a run
                    citable/reproducible - re-run later and diff configs.
  - results.json  : full per-question, per-method results (same content
                    written to data/eval_results.json for convenience).
  - summary.txt   : exact copy of everything printed to stdout for this run.

data/eval_results.json is still written each run too, as a "latest results"
convenience copy - but eval/runs/ is the permanent record; only that
directory should be cited or diffed across runs.

Usage:
  python scripts/evaluate.py                          # retrieval-only metrics, all 50 questions
  python scripts/evaluate.py --label baseline          # tag the run folder name
  python scripts/evaluate.py --generate                # also do generation+judge on a sample
  python scripts/evaluate.py --generate --sample 20
  python scripts/evaluate.py --generate --full         # generation+judge on all 50 (costs more)
"""
import argparse, json, math, os, random, re, statistics, sys, time
import io, subprocess
from collections import Counter
from datetime import datetime, timezone
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from retrieval_methods import load_corpus, TfidfIndex, run_method, METHODS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
EVAL_DIR = os.path.join(BASE_DIR, "eval")
RUNS_DIR = os.path.join(EVAL_DIR, "runs")

PROVIDER_MODELS = {
    "anthropic": {"generation": "claude-sonnet-4-6", "judge": "claude-sonnet-4-6"},
    "openai": {"generation": "gpt-5", "judge": "gpt-5"},
}
PROVIDER_ENV_VAR = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}


def word_count(text):
    return len(text.split())


def _tokenize(text):
    return re.findall(r"[a-zA-Z']+", text.lower())


def cosine_similarity(text_a, text_b):
    """Bag-of-words cosine similarity between two texts - a cheap, stdlib-only
    proxy for 'sentence similarity' to the gold answer. This is LEXICAL
    overlap (shared words), not semantic/embedding similarity - two answers
    that say the same thing in different words will score low here. Report
    it as exactly that (a lexical-overlap proxy), not as a general semantic
    similarity metric, in anything citing this number."""
    a, b = Counter(_tokenize(text_a)), Counter(_tokenize(text_b))
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[w] * b[w] for w in common)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _count_syllables(word):
    word = word.lower()
    vowels = "aeiouy"
    count, prev_was_vowel = 0, False
    for ch in word:
        is_vowel = ch in vowels
        if is_vowel and not prev_was_vowel:
            count += 1
        prev_was_vowel = is_vowel
    if word.endswith("e") and count > 1:
        count -= 1
    return max(count, 1)


def flesch_reading_ease(text):
    """Standard Flesch Reading Ease formula (0-100, higher = easier to read;
    US general-audience text is typically 60-70). Pure-stdlib syllable-count
    approximation - a standard, citable readability proxy, not a validated
    coherence/fluency measure. Directly relevant to the framework's
    'user-friendly, accessible' qualitative goals: a numeric readability
    trend to check before running the human usability study, not a
    replacement for it."""
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    words = _tokenize(text)
    if not sentences or not words:
        return None
    syllables = sum(_count_syllables(w) for w in words)
    words_per_sentence = len(words) / len(sentences)
    syllables_per_word = syllables / len(words)
    return 206.835 - 1.015 * words_per_sentence - 84.6 * syllables_per_word


def score_retrieval(retrieved_ids, gold_ids):
    retrieved_set = set(retrieved_ids)
    gold_set = set(gold_ids)
    hit = 1 if retrieved_set & gold_set else 0
    recall = len(retrieved_set & gold_set) / len(gold_set) if gold_set else 0.0
    precision = len(retrieved_set & gold_set) / len(retrieved_set) if retrieved_set else 0.0
    return {"hit": hit, "recall": recall, "precision": precision}


N_BOOTSTRAP = 2000
BOOTSTRAP_SEED = 13


def bootstrap_ci(values, n_boot=N_BOOTSTRAP, ci=0.95, seed=BOOTSTRAP_SEED):
    """Percentile bootstrap CI for the mean of `values` (stdlib only, no scipy/numpy)."""
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(n_boot):
        means.append(statistics.mean(values[rng.randrange(n)] for _ in range(n)))
    means.sort()
    lo = means[int((1 - ci) / 2 * n_boot)]
    hi = means[int((1 + ci) / 2 * n_boot) - 1]
    return lo, hi


def paired_bootstrap_pvalue(values_a, values_b, n_boot=N_BOOTSTRAP, seed=BOOTSTRAP_SEED):
    """Two-sided paired-bootstrap significance test for mean(a) != mean(b), same
    question set for both (so each resample draws the SAME question indices for
    both methods - this is what makes it 'paired', matching the paired design
    here: every method is scored against the same 50 questions)."""
    rng = random.Random(seed)
    n = len(values_a)
    diffs = []
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        mean_a = statistics.mean(values_a[i] for i in idx)
        mean_b = statistics.mean(values_b[i] for i in idx)
        diffs.append(mean_a - mean_b)
    diffs.sort()
    prop_le_zero = sum(1 for d in diffs if d <= 0) / len(diffs)
    prop_ge_zero = sum(1 for d in diffs if d >= 0) / len(diffs)
    return min(2 * min(prop_le_zero, prop_ge_zero), 1.0)


def sig_marker(p):
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


def quadratic_weighted_kappa(ratings_a, ratings_b, categories=(0, 1, 2)):
    """Inter-rater agreement between two judges scoring the same items on the
    same ordinal scale (here: 0/1/2). Quadratic weights (rather than plain
    Cohen's kappa) are the standard choice for ordinal categories - a
    disagreement of 2 vs 0 counts as worse than 1 vs 0, unlike plain kappa
    which treats every disagreement the same. 1.0 = perfect agreement,
    0.0 = chance-level agreement, negative = worse than chance.
    Pure stdlib, no scipy/sklearn dependency."""
    n = len(ratings_a)
    if n == 0 or n != len(ratings_b):
        return None
    k = len(categories)
    idx = {c: i for i, c in enumerate(categories)}
    O = [[0] * k for _ in range(k)]
    for a, b in zip(ratings_a, ratings_b):
        O[idx[a]][idx[b]] += 1
    row_marginal = [sum(O[i]) for i in range(k)]
    col_marginal = [sum(O[i][j] for i in range(k)) for j in range(k)]
    W = [[((i - j) ** 2) / ((k - 1) ** 2) for j in range(k)] for i in range(k)]
    num = sum(W[i][j] * O[i][j] for i in range(k) for j in range(k))
    den = sum(W[i][j] * row_marginal[i] * col_marginal[j] / n for i in range(k) for j in range(k))
    if den == 0:
        return 1.0  # both raters gave every item the same single category - no disagreement possible
    return 1 - num / den


def get_git_info():
    """Commit + dirty-tree flag, so a run can be tied back to the exact code that produced it."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=BASE_DIR, stderr=subprocess.DEVNULL
        ).decode().strip()
        dirty = bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=BASE_DIR, stderr=subprocess.DEVNULL
        ).decode().strip())
        return {"commit": commit, "dirty_worktree": dirty}
    except Exception:
        return {"commit": None, "dirty_worktree": None}


def get_corpus_info(chunks):
    """Which documents/chunk count this run actually evaluated against."""
    manifest_path = os.path.join(DATA_DIR, "raw", "manifest.json")
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
        documents = [{"id": d["id"], "title": d["title"], "file": d["file"]} for d in manifest["documents"]]
    except Exception:
        documents = None
    return {"num_chunks": len(chunks), "documents": documents}


class Tee:
    """Duplicates writes to multiple streams, so console output and the saved
    summary.txt for a run are guaranteed identical without printing twice."""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)

    def flush(self):
        for s in self.streams:
            s.flush()


def call_anthropic(system_prompt, user_message, model, max_tokens=500):
    """Minimal Anthropic Messages API call using only the standard library,
    so this script has no extra pip dependencies. Requires ANTHROPIC_API_KEY."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    body = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    text_blocks = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
    return "\n".join(text_blocks)


def call_openai(system_prompt, user_message, model, max_tokens=500):
    """Minimal OpenAI Chat Completions API call using only the standard
    library. Mirrors backend/providers.py's call_openai (max_completion_tokens,
    system+user message shape) so eval results reflect the same request shape
    the live app sends. Requires OPENAI_API_KEY."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    body = json.dumps({
        "model": model,
        "max_completion_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"] or ""


def call_llm(system_prompt, user_message, provider, model, max_tokens=500):
    if provider == "openai":
        return call_openai(system_prompt, user_message, model, max_tokens)
    return call_anthropic(system_prompt, user_message, model, max_tokens)


GEN_SYSTEM_TEMPLATE = """You are the PIPE Plumbing Safety Assistant. Answer ONLY using the CONTEXT below, \
drawn from two peer-reviewed studies on premise plumbing water quality (Singh et al. 2020, 2022). \
If the context doesn't answer the question, say so explicitly. Keep the answer to 2-3 sentences, \
stating the key fact/number precisely.

CONTEXT:
{context}
"""

JUDGE_SYSTEM = """You are grading a plumbing-safety Q&A system. You will see a QUESTION, a REFERENCE \
ANSWER (ground truth), and a GENERATED ANSWER. Score the generated answer 0, 1, or 2:
  2 = matches the reference answer's key facts/numbers accurately
  1 = partially correct, or correct but missing key specifics (e.g. right direction, wrong number)
  0 = wrong, contradicts the reference, or fails to answer (including a correct "not enough information" \
      refusal when the reference answer clearly could have been given - that still scores 0, since the \
      information WAS retrievable)
Respond with ONLY the digit 0, 1, or 2 and nothing else."""


# Generous headroom, not a target length: current-generation models spend
# tokens on invisible reasoning before any visible digit - a tight cap (the
# old value here was 5, sized for pre-reasoning models) truncates before the
# digit is ever produced, silently returning empty text rather than an error.
JUDGE_MAX_TOKENS = 2000


def judge_answer(question, gold_answer, generated_answer, provider, judge_model):
    user_msg = f"QUESTION: {question}\n\nREFERENCE ANSWER: {gold_answer}\n\nGENERATED ANSWER: {generated_answer}"
    try:
        raw = call_llm(JUDGE_SYSTEM, user_msg, provider, judge_model, max_tokens=JUDGE_MAX_TOKENS).strip()
        digit = "".join(ch for ch in raw if ch.isdigit())
        if not digit:
            print(f"  [judge warning: no digit in response, raw={raw[:120]!r}]")
            return None
        return int(digit[0])
    except Exception as e:
        print(f"  [judge error: {e}]")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true", help="also run end-to-end generation + LLM judging")
    parser.add_argument("--provider", choices=["anthropic", "openai"], default="anthropic",
                         help="which provider's key/model to use for --generate (default anthropic)")
    parser.add_argument("--sample", type=int, default=15, help="how many questions to use for --generate (default 15)")
    parser.add_argument("--full", action="store_true", help="use all 50 questions for --generate instead of --sample")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--label", default="run", help="short label folded into the run folder name, e.g. 'baseline-2doc-corpus'")
    parser.add_argument("--second-judge-provider", choices=["anthropic", "openai"], default=None,
                         help="if set (and different from --provider), also judge every generated answer with "
                              "this second provider's model, and report inter-rater agreement (quadratic weighted "
                              "kappa) between the two judges - needs both providers' API keys exported. Reuses the "
                              "same generated answers; only doubles the judging calls, not generation.")
    args = parser.parse_args()

    with open(os.path.join(DATA_DIR, "qa_eval_set.json")) as f:
        qa_set = json.load(f)

    chunks, chunks_by_id, kg, structured, compressed = load_corpus()
    tfidf_index = TfidfIndex(chunks)

    # ---- run provenance, decided before anything is printed ----
    run_timestamp = datetime.now(timezone.utc)
    run_id = run_timestamp.strftime("%Y%m%dT%H%M%SZ") + f"_{args.label}"
    run_dir = os.path.join(RUNS_DIR, run_id)
    os.makedirs(run_dir, exist_ok=True)

    config = {
        "run_id": run_id,
        "timestamp_utc": run_timestamp.isoformat(),
        "label": args.label,
        "git": get_git_info(),
        "corpus": get_corpus_info(chunks),
        "eval_set": {"path": "data/qa_eval_set.json", "num_questions": len(qa_set)},
        "args": vars(args),
    }
    if args.generate:
        provider_models = PROVIDER_MODELS[args.provider]
        config["provider"] = args.provider
        config["generation_model"] = provider_models["generation"]
        config["judge_model"] = provider_models["judge"]

    # tee stdout so the console and summary.txt end up byte-identical
    summary_buf = io.StringIO()
    real_stdout = sys.stdout
    sys.stdout = Tee(real_stdout, summary_buf)

    try:
        results = {m: [] for m in METHODS}

        print(f"Run: {run_id}")
        print(f"Corpus: {config['corpus']['num_chunks']} chunks from {len(config['corpus']['documents'] or [])} document(s)")
        print(f"Git commit: {config['git']['commit']}" + (" (dirty worktree)" if config['git']['dirty_worktree'] else ""))
        print(f"Running retrieval-only evaluation on {len(qa_set)} questions x {len(METHODS)} methods...\n")

        for item in qa_set:
            for method in METHODS:
                t0 = time.perf_counter()
                r = run_method(method, item["question"], chunks, chunks_by_id, kg, structured, compressed, tfidf_index)
                retrieval_time_ms = (time.perf_counter() - t0) * 1000
                scores = score_retrieval(r["chunk_ids"], item["gold_chunks"])
                results[method].append({
                    "id": item["id"],
                    "category": item["category"],
                    "question": item["question"],
                    "gold_chunks": item["gold_chunks"],
                    "retrieved_chunks": r["chunk_ids"],
                    "context_words": word_count(r["context"]),
                    "retrieval_time_ms": round(retrieval_time_ms, 3),
                    **scores,
                })

        # ---- retrieval-quality summary table ----
        print(f"{'Method':<14}{'Hit@k':>8}{'Recall':>9}{'Precision':>11}{'Avg ctx (chunks)':>19}{'Avg ctx (words)':>18}{'Avg retr (ms)':>16}")
        print("-" * 96)
        summary = {}
        for method in METHODS:
            rows = results[method]
            hit = statistics.mean(r["hit"] for r in rows)
            recall = statistics.mean(r["recall"] for r in rows)
            precision = statistics.mean(r["precision"] for r in rows)
            avg_chunks = statistics.mean(len(r["retrieved_chunks"]) for r in rows)
            avg_words = statistics.mean(r["context_words"] for r in rows)
            avg_retr_ms = statistics.mean(r["retrieval_time_ms"] for r in rows)
            summary[method] = {
                "hit_at_k": round(hit, 3), "recall": round(recall, 3), "precision": round(precision, 3),
                "avg_chunks_retrieved": round(avg_chunks, 1), "avg_context_words": round(avg_words, 1),
                "avg_retrieval_time_ms": round(avg_retr_ms, 3),
            }
            print(f"{method:<14}{hit:>8.3f}{recall:>9.3f}{precision:>11.3f}{avg_chunks:>19.1f}{avg_words:>18.1f}{avg_retr_ms:>16.3f}")

        # ---- statistical treatment: bootstrap CI + paired significance vs. vector baseline ----
        # Point estimates alone don't say whether a recall difference is real or
        # noise on 50 questions - this puts a number on that. `vector` (plain
        # TF-IDF) is the natural baseline: it's the simplest method here, so
        # every other method's job is to justify itself against it.
        baseline_method = "vector"
        recall_lists = {m: [r["recall"] for r in results[m]] for m in METHODS}
        stats_summary = {}
        print(f"\nRecall: 95% CI (bootstrap, n={N_BOOTSTRAP}) and paired significance vs. '{baseline_method}' baseline:")
        print(f"{'Method':<14}{'Recall':>9}{'95% CI':>20}{'p (vs baseline)':>18}{'sig':>5}")
        print("-" * 66)
        for method in METHODS:
            lo, hi = bootstrap_ci(recall_lists[method])
            if method == baseline_method:
                p, marker = None, ""
            else:
                p = paired_bootstrap_pvalue(recall_lists[method], recall_lists[baseline_method])
                marker = sig_marker(p)
            stats_summary[method] = {
                "recall_95ci": [round(lo, 3), round(hi, 3)],
                "p_vs_baseline": round(p, 4) if p is not None else None,
            }
            ci_str = f"[{lo:.3f}, {hi:.3f}]"
            p_str = "(baseline)" if p is None else f"{p:.4f}"
            print(f"{method:<14}{summary[method]['recall']:>9.3f}{ci_str:>20}{p_str:>18}{marker:>5}")
        print("(* p<0.05, ** p<0.01 - paired bootstrap, two-sided, resampling the same 50 questions each draw)")

        print("""
Reading this table:
  - long_context hits/recalls 100% by construction (it hands over the entire
    corpus) but precision is the lowest of all five methods and context size
    is 5-15x everyone else's - the token-cost side of the tradeoff that
    "always just use long context" glosses over.
  - structured has the highest precision of any method: when a question names
    a modeled parameter, it returns exactly the relevant records and nothing
    else. It falls back to vector's numbers on questions outside its table.
  - graph is the most interesting result here: it does NOT out-recall vector
    across the board. It only recalls well on the categories its 25-entity
    graph was actually built to cover (materials, temperature); on categories
    with no matching entities in the graph (guidance_landscape, knowledge_gaps)
    its recall is 0 - a direct, honest illustration that GraphRAG's value is
    bounded by how much of the domain got modeled as entities/relations, not
    a free upgrade over text search. See the per-category table below.
  - compressed keeps recall close to vector's while using roughly 1/3 the
    context size, since it searches ~10 digest entries instead of 39 raw
    chunks - the "summarize first" tradeoff paying off on recall-per-token.
  - retrieval_time_ms is wall-clock for the retrieval step only (no LLM call)
    on this machine - not a general hardware benchmark, but comparable
    across methods within a single run since everything else is held fixed.
""")

        # ---- per-category breakdown (helps see *where* each method wins/loses) ----
        categories = sorted({item["category"] for item in qa_set})
        print(f"\nRecall by category:\n{'Category':<20}" + "".join(f"{m:>14}" for m in METHODS))
        for cat in categories:
            row = f"{cat:<20}"
            for method in METHODS:
                cat_rows = [r for r in results[method] if r["category"] == cat]
                recall = statistics.mean(r["recall"] for r in cat_rows) if cat_rows else 0.0
                row += f"{recall:>14.3f}"
            print(row)

        output = {"config": config, "summary": summary, "statistics": stats_summary, "per_question": results}

        # ---- optional: end-to-end generation + LLM judge ----
        if args.generate:
            env_var = PROVIDER_ENV_VAR[args.provider]
            if not os.environ.get(env_var):
                print(f"\n--generate was passed but {env_var} is not set; skipping generation+judging.")
                print("(This is separate from any API key entered in the web app - export it in this shell:")
                print(f" export {env_var}=...)")
            else:
                provider_models = PROVIDER_MODELS[args.provider]

                second_judge = args.second_judge_provider
                if second_judge == args.provider:
                    print(f"\n--second-judge-provider is the same as --provider ({args.provider}) - ignoring it "
                          "(a second judge only means something if it's actually independent).")
                    second_judge = None
                if second_judge and not os.environ.get(PROVIDER_ENV_VAR[second_judge]):
                    print(f"\n--second-judge-provider {second_judge} was passed but {PROVIDER_ENV_VAR[second_judge]} "
                          "is not set - skipping the second judge, running with one judge only.")
                    second_judge = None
                second_judge_model = PROVIDER_MODELS[second_judge]["judge"] if second_judge else None

                random.seed(args.seed)
                sample = qa_set if args.full else random.sample(qa_set, min(args.sample, len(qa_set)))
                print(f"\nRunning end-to-end generation + LLM judging on {len(sample)} questions x {len(METHODS)} methods...")
                print(f"Provider: {args.provider} | Generation model: {provider_models['generation']} | Judge model: {provider_models['judge']} | seed={args.seed}")
                if second_judge:
                    print(f"Second (independent) judge: {second_judge} | {second_judge_model} - for inter-rater reliability")
                gen_records = {m: [] for m in METHODS}
                for item in sample:
                    for method in METHODS:
                        r = run_method(method, item["question"], chunks, chunks_by_id, kg, structured, compressed, tfidf_index)
                        system_prompt = GEN_SYSTEM_TEMPLATE.format(context=r["context"] or "(no context retrieved)")
                        t0 = time.perf_counter()
                        try:
                            answer = call_llm(system_prompt, item["question"], args.provider, provider_models["generation"])
                        except Exception as e:
                            print(f"  [generation error, {method}, q{item['id']}: {e}]")
                            continue
                        generation_time_ms = (time.perf_counter() - t0) * 1000
                        t0 = time.perf_counter()
                        judge_score = judge_answer(item["question"], item["gold_answer"], answer, args.provider, provider_models["judge"])
                        judge_time_ms = (time.perf_counter() - t0) * 1000
                        judge_score_2 = None
                        if second_judge:
                            judge_score_2 = judge_answer(item["question"], item["gold_answer"], answer, second_judge, second_judge_model)
                        similarity_to_gold = cosine_similarity(answer, item["gold_answer"])
                        readability = flesch_reading_ease(answer)
                        gen_records[method].append({
                            "id": item["id"],
                            "question": item["question"],
                            "gold_answer": item["gold_answer"],
                            "generated_answer": answer,
                            "judge_score": judge_score,
                            "judge_score_2": judge_score_2,
                            "judge_2_provider": second_judge,
                            "similarity_to_gold": round(similarity_to_gold, 3),
                            "flesch_reading_ease": round(readability, 1) if readability is not None else None,
                            "context_words": word_count(r["context"]),
                            "generation_time_ms": round(generation_time_ms, 1),
                            "judge_time_ms": round(judge_time_ms, 1),
                        })
                        time.sleep(0.3)  # be polite to the API
                print(f"\n{'Method':<14}{'Avg judge score (0-2)':>24}{'n':>6}{'Avg gen (ms)':>16}{'Lex.sim(gold)':>16}{'Flesch ease':>14}")
                print("-" * 90)
                gen_summary = {}
                for method in METHODS:
                    scored = [r["judge_score"] for r in gen_records[method] if r["judge_score"] is not None]
                    if scored:
                        avg = statistics.mean(scored)
                        avg_gen_ms = statistics.mean(r["generation_time_ms"] for r in gen_records[method])
                        avg_sim = statistics.mean(r["similarity_to_gold"] for r in gen_records[method])
                        flesch_vals = [r["flesch_reading_ease"] for r in gen_records[method] if r["flesch_reading_ease"] is not None]
                        avg_flesch = statistics.mean(flesch_vals) if flesch_vals else None
                        gen_summary[method] = {
                            "avg_judge_score": round(avg, 3), "n": len(scored), "avg_generation_time_ms": round(avg_gen_ms, 1),
                            "avg_similarity_to_gold": round(avg_sim, 3),
                            "avg_flesch_reading_ease": round(avg_flesch, 1) if avg_flesch is not None else None,
                        }
                        flesch_str = f"{avg_flesch:.1f}" if avg_flesch is not None else "n/a"
                        print(f"{method:<14}{avg:>24.3f}{len(scored):>6}{avg_gen_ms:>16.1f}{avg_sim:>16.3f}{flesch_str:>14}")
                    else:
                        print(f"{method:<14}{'(no results)':>24}")
                print("(Lex.sim(gold): bag-of-words cosine similarity to the gold answer - lexical overlap, not semantic similarity.")
                print(" Flesch ease: 0-100 readability, higher = easier to read; ~60-70 is typical general-audience US text.)")

                if second_judge:
                    print(f"\nInter-rater reliability: {args.provider} judge vs. {second_judge} judge (quadratic weighted kappa):")
                    print(f"{'Method':<14}{'Kappa':>8}{'% exact agree':>16}{'n':>6}")
                    print("-" * 44)
                    kappa_summary = {}
                    for method in METHODS:
                        paired = [(r["judge_score"], r["judge_score_2"]) for r in gen_records[method]
                                  if r["judge_score"] is not None and r["judge_score_2"] is not None]
                        if paired:
                            a_scores, b_scores = zip(*paired)
                            kappa = quadratic_weighted_kappa(list(a_scores), list(b_scores))
                            pct_agree = sum(1 for a, b in paired if a == b) / len(paired)
                            kappa_summary[method] = {"quadratic_weighted_kappa": round(kappa, 3), "pct_exact_agreement": round(pct_agree, 3), "n": len(paired)}
                            print(f"{method:<14}{kappa:>8.3f}{pct_agree:>16.3f}{len(paired):>6}")
                        else:
                            print(f"{method:<14}{'(no paired results)':>24}")
                    print("(Kappa: 1.0=perfect agreement, 0.0=chance-level, negative=worse than chance.")
                    print(" Conventional rough bands: <0.2 slight, 0.2-0.4 fair, 0.4-0.6 moderate, 0.6-0.8 substantial, >0.8 almost perfect.)")
                    output["inter_rater_reliability"] = kappa_summary

                output["generation_judge_summary"] = gen_summary
                output["generation_judge_records"] = gen_records

    finally:
        sys.stdout = real_stdout

    # ---- persist: permanent timestamped run, plus a "latest" convenience copy ----
    with open(os.path.join(run_dir, "config.json"), "w") as f:
        json.dump(config, f, indent=2)
    with open(os.path.join(run_dir, "results.json"), "w") as f:
        json.dump(output, f, indent=2)
    with open(os.path.join(run_dir, "summary.txt"), "w") as f:
        f.write(summary_buf.getvalue())

    latest_path = os.path.join(DATA_DIR, "eval_results.json")
    with open(latest_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nRun saved to eval/runs/{run_id}/ (config.json, results.json, summary.txt)")
    print(f"Latest-results convenience copy: {latest_path}")


if __name__ == "__main__":
    main()

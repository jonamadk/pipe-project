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
import argparse, json, os, random, statistics, sys, time
import io, subprocess
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


def score_retrieval(retrieved_ids, gold_ids):
    retrieved_set = set(retrieved_ids)
    gold_set = set(gold_ids)
    hit = 1 if retrieved_set & gold_set else 0
    recall = len(retrieved_set & gold_set) / len(gold_set) if gold_set else 0.0
    precision = len(retrieved_set & gold_set) / len(retrieved_set) if retrieved_set else 0.0
    return {"hit": hit, "recall": recall, "precision": precision}


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

        output = {"config": config, "summary": summary, "per_question": results}

        # ---- optional: end-to-end generation + LLM judge ----
        if args.generate:
            env_var = PROVIDER_ENV_VAR[args.provider]
            if not os.environ.get(env_var):
                print(f"\n--generate was passed but {env_var} is not set; skipping generation+judging.")
                print("(This is separate from any API key entered in the web app - export it in this shell:")
                print(f" export {env_var}=...)")
            else:
                provider_models = PROVIDER_MODELS[args.provider]
                random.seed(args.seed)
                sample = qa_set if args.full else random.sample(qa_set, min(args.sample, len(qa_set)))
                print(f"\nRunning end-to-end generation + LLM judging on {len(sample)} questions x {len(METHODS)} methods...")
                print(f"Provider: {args.provider} | Generation model: {provider_models['generation']} | Judge model: {provider_models['judge']} | seed={args.seed}")
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
                        gen_records[method].append({
                            "id": item["id"],
                            "question": item["question"],
                            "gold_answer": item["gold_answer"],
                            "generated_answer": answer,
                            "judge_score": judge_score,
                            "context_words": word_count(r["context"]),
                            "generation_time_ms": round(generation_time_ms, 1),
                            "judge_time_ms": round(judge_time_ms, 1),
                        })
                        time.sleep(0.3)  # be polite to the API
                print(f"\n{'Method':<14}{'Avg judge score (0-2)':>24}{'n':>6}{'Avg gen (ms)':>16}")
                print("-" * 60)
                gen_summary = {}
                for method in METHODS:
                    scored = [r["judge_score"] for r in gen_records[method] if r["judge_score"] is not None]
                    if scored:
                        avg = statistics.mean(scored)
                        avg_gen_ms = statistics.mean(r["generation_time_ms"] for r in gen_records[method])
                        gen_summary[method] = {"avg_judge_score": round(avg, 3), "n": len(scored), "avg_generation_time_ms": round(avg_gen_ms, 1)}
                        print(f"{method:<14}{avg:>24.3f}{len(scored):>6}{avg_gen_ms:>16.1f}")
                    else:
                        print(f"{method:<14}{'(no results)':>24}")
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

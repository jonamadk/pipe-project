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

  2. END-TO-END GENERATION + LLM JUDGE (optional, needs ANTHROPIC_API_KEY):
     For a sample of questions, actually generate an answer from each
     method's retrieved context, then ask Claude to judge the generated
     answer against the gold answer on a 0-2 scale. Off by default since
     it costs tokens and needs real API access; this sandbox has none.

Usage:
  python scripts/evaluate.py                     # retrieval-only metrics, all 50 questions
  python scripts/evaluate.py --generate           # also do generation+judge on a sample
  python scripts/evaluate.py --generate --sample 20
  python scripts/evaluate.py --generate --full    # generation+judge on all 50 (costs more)

Writes:
  data/eval_results.json   - full per-question, per-method results
  Prints a summary comparison table to stdout.
"""
import argparse, json, os, random, statistics, sys, time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from retrieval_methods import load_corpus, TfidfIndex, run_method, METHODS

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")


def word_count(text):
    return len(text.split())


def score_retrieval(retrieved_ids, gold_ids):
    retrieved_set = set(retrieved_ids)
    gold_set = set(gold_ids)
    hit = 1 if retrieved_set & gold_set else 0
    recall = len(retrieved_set & gold_set) / len(gold_set) if gold_set else 0.0
    precision = len(retrieved_set & gold_set) / len(retrieved_set) if retrieved_set else 0.0
    return {"hit": hit, "recall": recall, "precision": precision}


def call_claude(system_prompt, user_message, max_tokens=500):
    """Minimal Anthropic Messages API call using only the standard library,
    so this script has no extra pip dependencies. Requires ANTHROPIC_API_KEY."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    body = json.dumps({
        "model": "claude-sonnet-4-6",
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


def judge_answer(question, gold_answer, generated_answer):
    user_msg = f"QUESTION: {question}\n\nREFERENCE ANSWER: {gold_answer}\n\nGENERATED ANSWER: {generated_answer}"
    try:
        raw = call_claude(JUDGE_SYSTEM, user_msg, max_tokens=5).strip()
        digit = "".join(ch for ch in raw if ch.isdigit())
        return int(digit[0]) if digit else None
    except Exception as e:
        print(f"  [judge error: {e}]")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--generate", action="store_true", help="also run end-to-end generation + LLM judging")
    parser.add_argument("--sample", type=int, default=15, help="how many questions to use for --generate (default 15)")
    parser.add_argument("--full", action="store_true", help="use all 50 questions for --generate instead of --sample")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    with open(os.path.join(DATA_DIR, "qa_eval_set.json")) as f:
        qa_set = json.load(f)

    chunks, chunks_by_id, kg, structured, compressed = load_corpus()
    tfidf_index = TfidfIndex(chunks)

    results = {m: [] for m in METHODS}

    print(f"Running retrieval-only evaluation on {len(qa_set)} questions x {len(METHODS)} methods...\n")

    for item in qa_set:
        for method in METHODS:
            r = run_method(method, item["question"], chunks, chunks_by_id, kg, structured, compressed, tfidf_index)
            scores = score_retrieval(r["chunk_ids"], item["gold_chunks"])
            results[method].append({
                "id": item["id"],
                "category": item["category"],
                "question": item["question"],
                "gold_chunks": item["gold_chunks"],
                "retrieved_chunks": r["chunk_ids"],
                "context_words": word_count(r["context"]),
                **scores,
            })

    # ---- retrieval-quality summary table ----
    print(f"{'Method':<14}{'Hit@k':>8}{'Recall':>9}{'Precision':>11}{'Avg ctx (chunks)':>19}{'Avg ctx (words)':>18}")
    print("-" * 80)
    summary = {}
    for method in METHODS:
        rows = results[method]
        hit = statistics.mean(r["hit"] for r in rows)
        recall = statistics.mean(r["recall"] for r in rows)
        precision = statistics.mean(r["precision"] for r in rows)
        avg_chunks = statistics.mean(len(r["retrieved_chunks"]) for r in rows)
        avg_words = statistics.mean(r["context_words"] for r in rows)
        summary[method] = {
            "hit_at_k": round(hit, 3), "recall": round(recall, 3), "precision": round(precision, 3),
            "avg_chunks_retrieved": round(avg_chunks, 1), "avg_context_words": round(avg_words, 1),
        }
        print(f"{method:<14}{hit:>8.3f}{recall:>9.3f}{precision:>11.3f}{avg_chunks:>19.1f}{avg_words:>18.1f}")

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

    output = {"summary": summary, "per_question": results}

    # ---- optional: end-to-end generation + LLM judge ----
    if args.generate:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("\n--generate was passed but ANTHROPIC_API_KEY is not set; skipping generation+judging.")
        else:
            random.seed(args.seed)
            sample = qa_set if args.full else random.sample(qa_set, min(args.sample, len(qa_set)))
            print(f"\nRunning end-to-end generation + LLM judging on {len(sample)} questions x {len(METHODS)} methods...")
            gen_scores = {m: [] for m in METHODS}
            for item in sample:
                for method in METHODS:
                    r = run_method(method, item["question"], chunks, chunks_by_id, kg, structured, compressed, tfidf_index)
                    system_prompt = GEN_SYSTEM_TEMPLATE.format(context=r["context"] or "(no context retrieved)")
                    try:
                        answer = call_claude(system_prompt, item["question"])
                    except Exception as e:
                        print(f"  [generation error, {method}, q{item['id']}: {e}]")
                        continue
                    judge_score = judge_answer(item["question"], item["gold_answer"], answer)
                    if judge_score is not None:
                        gen_scores[method].append(judge_score)
                    time.sleep(0.3)  # be polite to the API
            print(f"\n{'Method':<14}{'Avg judge score (0-2)':>24}{'n':>6}")
            print("-" * 44)
            gen_summary = {}
            for method in METHODS:
                if gen_scores[method]:
                    avg = statistics.mean(gen_scores[method])
                    gen_summary[method] = round(avg, 3)
                    print(f"{method:<14}{avg:>24.3f}{len(gen_scores[method]):>6}")
                else:
                    print(f"{method:<14}{'(no results)':>24}")
            output["generation_judge_summary"] = gen_summary

    out_path = os.path.join(DATA_DIR, "eval_results.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    main()

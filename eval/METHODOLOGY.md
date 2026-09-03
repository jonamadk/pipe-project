# PIPE Evaluation Methodology

Living document. This is the Methods-section source of truth for the PIPE
evaluation — update it whenever a metric, dataset, or procedure changes, so
it always matches what `eval/runs/` actually contains. Everything here maps
back to the framework: quantitative (per-retrieval-mechanism metrics +
assessment-form comparison) and qualitative (usability/trust study).

## System under evaluation

PIPE is a retrieval-grounded Q&A prototype over guidance literature on
Legionella / premise plumbing water quality. Five retrieval strategies are
implemented against a single shared chunk corpus and compared head-to-head:

| Method | What it does |
|---|---|
| `vector` | TF-IDF vector search over all chunks |
| `graph` | GraphRAG — traversal over a hand-built knowledge graph of entities/relations |
| `long_context` | No retrieval — hands the entire corpus to the model as context |
| `compressed` | Memory-compression — searches a smaller set of pre-summarized digest entries, then expands |
| `structured` | Routes to an exact structured lookup table for modeled parameters; falls back to `vector` otherwise |

Implementation: `scripts/retrieval_methods.py`. Full descriptions in the
root `README.md`.

## Corpus versioning

The corpus (`data/chunks.json`) is not fixed — it grows as more guidance
documents are ingested (see `PAUSED_STATE.md` for the in-progress
ingestion). **Every run's `config.json` records exactly which documents and
how many chunks were evaluated against** (`corpus.documents`,
`corpus.num_chunks`), plus the exact git commit (`git.commit`) and whether
the worktree was dirty at run time (`git.dirty_worktree`). When comparing
two runs, always diff their `config.json` first — a metric change could be
a retrieval improvement, or just a bigger/different corpus.

As of the first run in this folder (`20260903T213015Z_baseline-2doc-corpus`),
the corpus is 2 documents / 39 chunks (Singh et al. 2020, 2022) — the
original seed corpus. The 13-document expansion described in
`PAUSED_STATE.md` is not yet registered, so all current numbers are a
baseline, not the target corpus.

## Ground-truth dataset

**Authors-led set** (built, in use): `data/qa_eval_set.json` — 50
questions across 8 categories (temperature, disinfection, flushing,
materials, features, guidance_landscape, survey_stats, knowledge_gaps),
each with a `gold_answer` and one or more `gold_chunks` (the chunk id(s) in
the corpus that support that answer). Written by the project author(s)
directly from the two source papers.

To add a question:
```json
{"id": 51, "category": "temperature", "question": "...", "gold_answer": "...", "gold_chunks": ["c15"]}
```
`gold_chunks` must reference real ids from `data/chunks.json` (regenerate
that file with `python scripts/chunk_documents.py` after adding source
documents, then look up the right chunk id(s) for the fact your question
targets).

**Expert-led set**: not yet built. Needs a subject-matter expert (plumbing
safety / water quality, or the Drexel PIPE team) to author or validate a
second, independent question set — this guards against the authors-led set
encoding the same blind spots as the system it's evaluating.

**LLM-generated-and-validated set**: not yet built. Proposed process: use a
model distinct from the ones under test (e.g. if evaluating
Claude/GPT-generated answers, use a third model, or a stronger tier, to
draft candidate Q&A pairs from the source documents), then have a human
expert validate/edit each pair before it counts as gold. Document the exact
generation prompt and validation criteria here once this is built, since
"LLM-generated" ground truth needs its provenance auditable for a reviewer.

## Quantitative metrics

Run: `python scripts/evaluate.py [--generate] [--sample N | --full] [--label ...]`

### Retrieval-quality layer (always runs, offline, deterministic, free)

Per method, per question: `Hit@k`, `Recall`, `Precision` against
`gold_chunks`, average context size (chunks and words handed to the LLM —
the token-cost side of the tradeoff), and **retrieval time** (wall-clock ms
for the retrieval step alone, no LLM call). Aggregated per-method and
per-category (category breakdown shows *where* each method wins/loses, not
just an average that can hide it — see `graph`'s 0-recall categories as the
motivating example).

### Generation-quality layer (`--generate`, needs `ANTHROPIC_API_KEY`)

For a sample (or all 50) questions: generate an answer per method from its
retrieved context, then have an LLM judge score it 0/1/2 against
`gold_answer` (rubric in `scripts/evaluate.py`'s `JUDGE_SYSTEM`). Also
records **generation time** and **judge time** per question, and — as of
this update — the full generated answer text, not just the score, so raw
outputs are auditable rather than just an aggregate number.

**Needs an `ANTHROPIC_API_KEY` exported in the shell** running the script —
this is separate from the API key entered into the web app UI (which is
never read by this script; the eval script calls the Anthropic API
directly).

**Model IDs used**: `GENERATION_MODEL` / `JUDGE_MODEL` constants at the top
of `scripts/evaluate.py`, also recorded in every run's `config.json`. Note
these are currently pinned independently of `backend/providers.py`'s
`ANTHROPIC_MODEL` (used by the live app) — confirm/reconcile before citing
generation-quality numbers as representative of the deployed app's output.

### Not yet built

- **Naturalness / coherence scoring.** The judge rubric only scores factual
  match (0-2), not fluency, sentence structure, or reading level. Needs
  either a second judge rubric dimension, or an automatic metric (e.g.
  embedding-based sentence similarity to the gold answer) — undecided.
- **Statistical treatment.** Current summary is point estimates only (means
  across 15-50 questions). For publication, decide whether to report
  confidence intervals or a significance test (e.g. paired test) when
  claiming one method beats another — especially relevant since some
  per-category recall comparisons above are on very few questions.
- **Inter-rater reliability.** The generation-quality judge is a single LLM
  call, once, per (question, method) pair — there is no second rater (human
  or model) to check agreement against. Worth deciding whether that's an
  acceptable limitation to state explicitly, or whether to add either a
  human-rated subsample or a second LLM judge to report agreement (e.g.
  Cohen's kappa) on.

### Assessment-form comparison against Drexel's original tool

Not yet built — needs input only you can supply: Drexel's original tool's
answers to the same building-intake questions. Template and instructions:
`eval/drexel_comparison_template.json`.

## Qualitative evaluation

Usability/trust study with real participants — not yet built. Protocol
skeleton and open decisions (including a likely IRB requirement): see
`eval/qualitative_study_protocol.md`.

## Run records

Every `python scripts/evaluate.py` run writes a permanent, timestamped,
never-overwritten folder to `eval/runs/<timestamp>_<label>/`:
- `config.json` — full provenance (see "Corpus versioning" above)
- `results.json` — full per-question, per-method results, plus (if
  `--generate`) every generated answer and judge score
- `summary.txt` — exact copy of what was printed to the console

`data/eval_results.json` is also written each run as a "latest results"
convenience copy, but only `eval/runs/` should be cited or diffed — that
copy gets overwritten on the next run.

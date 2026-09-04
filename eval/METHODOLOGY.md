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

**Expert-led set**: not yet built. Questions will come from domain experts
directly (pending, on the user's side — not blocked on any tooling here).
Once received, format them the same way as `data/qa_eval_set.json`
(question / gold_answer / gold_chunks) so they run through the same
`evaluate.py` pipeline as a separate, independently-sourced set — this
guards against the authors-led set encoding the same blind spots as the
system it's evaluating.

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

### Generation-quality layer (`--generate --provider {anthropic|openai}`)

For a sample (or all 50) questions: generate an answer per method from its
retrieved context, then have an LLM judge score it 0/1/2 against
`gold_answer` (rubric in `scripts/evaluate.py`'s `JUDGE_SYSTEM`). Also
records **generation time** and **judge time** per question, and the full
generated answer text, not just the score, so raw outputs are auditable
rather than just an aggregate number.

**Needs an API key exported in the shell** running the script — `ANTHROPIC_API_KEY`
for `--provider anthropic` (default), `OPENAI_API_KEY` for
`--provider openai`. Both are separate from the API key entered into the
web app UI (which is never read by this script — it calls the provider's
API directly).

**Model IDs used**: `PROVIDER_MODELS` dict at the top of `scripts/evaluate.py`
(one generation + judge model pair per provider), also recorded in every
run's `config.json`. These are pinned independently of
`backend/providers.py`'s model constants (used by the live app) — confirm/
reconcile before citing generation-quality numbers as representative of the
deployed app's output.

**First real run** (`20260903T234154Z_second-openai-generation-pass`, 10
questions, `--provider openai`, `gpt-5`): structured 1.6, compressed 1.3,
long_context 1.2, vector 0.9, graph 0.5 (avg judge score, 0-2 scale) —
consistent with the retrieval-quality ranking above. Sample size is small
(n=10) — treat as a first pass, not a final result; re-run with `--full`
before citing.

**Bug found and fixed during first evaluation attempt**: the judge call
originally used `max_tokens=5` (correct for older, non-reasoning models
where the whole response is just the digit). Current-generation models
(GPT-5, and likely Claude's newer models too) spend tokens on invisible
reasoning before any visible output — a 5-token cap truncated every judge
call before it could emit the digit, which silently returned empty text as
`judge_score: None` for 100% of records with only a generic "(no results)"
in the summary table — no exception, no visible error. Confirmed via
`eval/runs/20260903T233542Z_first-openai-generation-pass/results.json`
(kept as the record of the bug: real generated answers present, every
`judge_score` null). Fixed by raising `JUDGE_MAX_TOKENS` to 2000 and adding
an explicit warning print when a judge response has no digit in it, so this
particular failure mode can't go silent again. Worth deliberately noting in
a paper's methods/limitations section that this was caught and corrected,
since it's exactly the kind of silent-failure risk that undermines
generation-quality numbers if it goes unnoticed.

### Statistical treatment (built)

Every retrieval-only run now also prints/saves, per method: a 95% bootstrap
confidence interval on recall (2000 resamples, stdlib-only — no scipy/numpy
dependency), and a paired-bootstrap two-sided significance test against
`vector` (plain TF-IDF) as the baseline — `vector` is the natural baseline
since it's the simplest method here. Saved in each run's `results.json`
under `statistics`. Implementation: `bootstrap_ci` / `paired_bootstrap_pvalue`
in `scripts/evaluate.py`.

**First result with this** (`eval/runs/20260904T000711Z_with-statistics2/`,
39-chunk corpus, all 50 questions): `graph` is significantly worse than
`vector` on recall (p<0.01) and `long_context` is significantly better
(p<0.01, but recall it also has 5-15x the context size and worst precision —
recall alone isn't the full story). `compressed` (p=0.606) and `structured`
(p=0.128) are **not** statistically distinguishable from `vector` on recall
alone at this sample size, despite `structured`'s clearly higher precision
and generation-quality (accuracy) numbers — worth stating plainly in a
paper rather than letting the point-estimate table imply a bigger recall
gap than the data actually supports.

This currently only covers recall on the retrieval-quality layer.
Generation-quality (accuracy judge scores) has no CI/significance test yet —
same bootstrap approach would apply, just needs enough `--generate --full`
budget to make a 50-question paired comparison meaningful (currently only
tested at n=10).

### Naturalness / coherence — automatic proxies (built)

The LLM judge only scores factual match (0-2), not fluency or reading
level, so `--generate` now also computes two automatic, stdlib-only metrics
per generated answer (`scripts/evaluate.py`: `cosine_similarity`,
`flesch_reading_ease`):

- **Lexical similarity to gold** — bag-of-words cosine similarity between
  the generated answer and `gold_answer`. This is **lexical overlap (shared
  words), not semantic similarity** — report it as that, explicitly, in
  anything citing it. Two answers saying the same thing in different words
  will score low.
- **Flesch Reading Ease** — standard 0-100 readability formula (higher =
  easier; ~60-70 is typical general-audience US text). A syllable-counting
  approximation, not a validated coherence measure, but a standard, citable
  readability proxy — directly relevant to the framework's "user-friendly,
  accessible" qualitative goal as a quantitative check to run before the
  human study, not a replacement for it.

**First result** (computed retroactively on the cached GPT-5 answers from
`20260903T234154Z_second-openai-generation-pass`, n=10 per method):

| Method | Avg judge score | Lexical sim. to gold | Flesch ease |
|---|---|---|---|
| structured | 1.6 | **0.303** | 40.9 |
| compressed | 1.3 | 0.299 | **33.9** |
| long_context | 1.2 | 0.186 | 52.6 |
| vector | 0.9 | 0.128 | 54.8 |
| graph | 0.5 | 0.156 | 44.7 |

Real, worth flagging directly in the paper: **the two most accurate methods
(structured, compressed) are also the least readable** (34-41 = "difficult/
college level" on the Flesch scale) — denser, more numeric answers score
better on accuracy but worse on accessibility. All five methods fall in the
"difficult" band (30-50); none reach the ~60-70 general-audience range. This
is an accuracy-vs-accessibility tension the qualitative usability study
should probably probe directly (does a more accurate but denser answer
actually serve a homeowner reader worse?), not just something the
quantitative numbers alone resolve.

Not yet wired into `evaluate.py`'s automatic run: these numbers above were
computed by loading a saved run's `results.json` and calling the two
functions directly — future `--generate` runs compute and save them
automatically (`similarity_to_gold` / `flesch_reading_ease` per record,
`avg_similarity_to_gold` / `avg_flesch_reading_ease` in the summary), so
this table will populate itself from `eval/runs/` going forward without
needing to be assembled by hand again.

### Not yet built

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

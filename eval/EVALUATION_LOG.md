# PIPE Evaluation — Progress Log

Narrative record of what was built, found, fixed, and measured while setting
up the evaluation framework. This is the "what happened" companion to
`eval/METHODOLOGY.md` (the "how it works" reference) — read this for the
story and real numbers, read that for the definitions and how to reproduce
them. Last updated 2026-09-04.

## 1. What was built

Before this work, `scripts/evaluate.py` existed but had never been run
end-to-end with real API access, and every run silently overwrote the one
previous result. Added:

- **Permanent run records** (`eval/runs/<timestamp>_<label>/`): every run
  now saves its own `config.json` (git commit, corpus version, model IDs,
  args), `results.json` (full per-question data), and `summary.txt` — never
  overwritten, so results are diffable and citable.
- **Response-time tracking** — wall-clock ms for retrieval, generation, and
  judging, previously not measured at all.
- **Statistical treatment** — 95% bootstrap confidence intervals and paired
  significance tests (vs. `vector` as baseline) on recall, so "method A
  beats method B" claims have a p-value behind them, not just two numbers
  that happen to differ.
- **OpenAI provider support** — `evaluate.py` originally only called
  Anthropic; added `--provider openai` and `--second-judge-provider` so
  either/both providers can generate and judge answers.
- **Naturalness proxies** — bag-of-words lexical similarity to the gold
  answer, and Flesch Reading Ease (readability), computed automatically per
  generated answer.
- **Inter-rater reliability** — `--second-judge-provider` runs a second,
  independent judge and reports quadratic weighted kappa agreement between
  the two.
- **`eval/drexel_comparison_template.json`** — pre-filled with the real
  18-question assessment form, ready for scenario-by-scenario comparison
  against Drexel's original tool once that data is available.
- **`eval/qualitative_study_protocol.md`** — draft usability/trust study
  design, flagged as needing IRB review before recruiting participants.

## 2. Bugs found and fixed

Real defects caught while actually running things, not by inspection alone:

1. **Judge scoring was silently 100% broken.** The LLM-judge call used
   `max_tokens=5`, sized for older non-reasoning models where the whole
   response is just a digit. Current-generation models (GPT-5, and likely
   Claude's newer models) spend tokens on invisible reasoning before any
   visible output — the 5-token cap truncated every judge call before it
   could emit anything, returning empty text with `judge_score: None` for
   every single record and no visible error (just "(no results)" in the
   summary table). Caught by inspecting raw saved records after the summary
   looked suspiciously empty across all 5 methods at once.
   Fix: raised to `JUDGE_MAX_TOKENS = 2000`, plus an explicit warning print
   whenever a judge response has no digit in it, so this can't go silent
   again. Buggy run kept on record as evidence:
   `eval/runs/20260903T233542Z_first-openai-generation-pass/` (real
   generated answers present, every `judge_score` null). Working run:
   `eval/runs/20260903T234154Z_second-openai-generation-pass/`.

2. **VA 2008 directive: wrong expiration date.** `data/raw/doc14_raw.txt`
   said "expires February 28, 2013"; the actual source PDF's footer reads
   "EXPIRES ON JANUARY 31, 2013." Caught during a source-PDF fact-check
   pass, fixed in the raw text.

3. **Page-marker regex couldn't handle real lettered pagination.**
   `scripts/chunk_documents.py` only matched digit/dash page labels
   (`\[Page ([\d\-]+)\]`). VA 2008's appendices are genuinely labeled
   A-1 through E-3 in the source PDF (not sequential numbers) — the old
   regex couldn't match those markers at all, which meant roughly two-thirds
   of the document (including real numeric thresholds: the 30%
   positive-site remediation trigger, 160-170°F thermal eradication range,
   2 mg/L hyperchlorination level) would have been silently mis-cited as
   page "6". Fixed by widening the regex to `\[Page ([\w\-]+)\]`, preserving
   the document's real pagination instead of inventing a fake sequential
   one — checked first that nothing downstream treats `page` as numeric
   (it's only ever displayed as a string, `p.{page}`, in
   `frontend/src/components/SourcesPanel.jsx`).

4. **CMS 2017 — checked, no bug.** The pre-existing `data/raw/doc16_raw.txt`
   was compared word-for-word against the real PDF and matched exactly,
   including all 4 page breaks. Registered as-is.

5. **Frontend error message names the wrong provider (not yet fixed).**
   When a request fails with OpenAI selected, the shown error says "enter
   your Anthropic API key above first" regardless of which provider is
   actually selected — looks hardcoded. Flagged, left for later.

## 3. Corpus expansion

The user located and supplied the actual source PDFs for all documents
referenced in `PAUSED_STATE.md` directly (`data/source_pdfs/`, gitignored,
never pushed) — removing the dependency on Google Drive access that had
blocked ingestion. Of 17 PDFs available, 3 were ingested as a pilot before
committing to the rest:

| Document | Status |
|---|---|
| CMS 2017 | Registered as-is (already-correct pre-existing extraction, verified) |
| VA 2008 | Re-verified, 1 date fixed, page-marker bug fixed |
| ASHRAE 188-2018 | First-ever extraction (never previously downloaded) |
| 14 others | Saved locally in `data/source_pdfs/`, not yet ingested |

Corpus grew from **2 documents / 39 chunks → 5 documents / 174 chunks**.
Verified chunk-id stability before running anything: `c1`-`c39` (referenced
by all 50 existing gold answers) are byte-identical to before, since the
new documents were appended after Singh 2020/2022 in `manifest.json` and
`chunk_documents.py` assigns ids in manifest order — no silent breakage of
the existing gold set.

**Known gap, not yet closed**: `graph` (`data/kg.json`), `structured`
(`data/structured_facts.json`), and `compressed`
(`data/compressed_summary.json`) are hand-curated files built by separate
scripts that were not extended to cover the 3 new documents — rebuilding
`chunks.json` doesn't touch them. This is currently invisible (no existing
gold question references the new documents), but those 3 methods are
blind to CMS/VA/ASHRAE content until this is addressed.

## 4. Real evaluation numbers so far

### Retrieval quality (offline, 50 authors-led questions, all 5 methods)

**2-document baseline** (39 chunks — `eval/runs/20260903T213015Z_baseline-2doc-corpus/`):

| Method | Hit@k | Recall | Precision | Avg ctx (chunks/words) |
|---|---|---|---|---|
| vector | 0.960 | 0.903 | 0.237 | 4.9 / 726 |
| graph | 0.440 | 0.430 | 0.071 | 5.8 / 998 |
| long_context | 1.000 | 1.000 | 0.034 | 39.0 / 4973 |
| compressed | 0.940 | 0.930 | 0.134 | 9.6 / 258 |
| structured | 0.880 | 0.823 | 0.353 | 3.6 / 442 |

**5-document pilot** (174 chunks — `eval/runs/20260904T070750Z_5doc-corpus-pilot/`):

| Method | Hit@k | Recall | Precision | Avg ctx (chunks/words) |
|---|---|---|---|---|
| vector | 0.900 | 0.833 | 0.216 | 5.0 / 688 |
| graph | 0.440 | 0.430 | 0.071 | 5.8 / 998 (unchanged - data not extended) |
| long_context | 1.000 | 1.000 | **0.008** | 174.0 / **23,773** |
| compressed | 0.940 | 0.930 | 0.134 | 9.6 / 258 (unchanged - data not extended) |
| structured | 0.840 | 0.773 | 0.336 | 3.7 / 427 |

**Real, citable finding**: adding more (unrelated-to-the-gold-questions)
documents made `vector`'s recall measurably *worse* (0.903→0.833) — more
competing content means more distractors for TF-IDF — and made
`long_context`'s precision collapse further (already the weakest method,
now 0.008 while hauling in ~24,000 words per question). Neither the
questions nor their difficulty changed; only the amount of unrelated
content in the corpus did. Direct evidence against "just use long context /
just add more documents for free."

### Statistical significance (paired bootstrap, recall vs. `vector` baseline)

|  | 2-doc corpus | 5-doc corpus |
|---|---|---|
| graph | p=0.0000 ** | p=0.0000 ** |
| long_context | p=0.0010 ** | p=0.0000 ** |
| compressed | p=0.6060 (n.s.) | p=0.1240 (n.s.) |
| structured | p=0.1280 (n.s.) | p=0.3260 (n.s.) |

`graph` and `long_context` are significantly different from plain vector
search in both corpus states. `compressed` and `structured`'s recall is
**not** statistically distinguishable from vanilla `vector` at this sample
size, in either corpus — worth stating plainly rather than letting the
point-estimate table imply a bigger gap than the data supports.

### Generation accuracy — LLM judge, 0-2 scale

First real end-to-end run (`eval/runs/20260903T234154Z_second-openai-generation-pass/`,
n=10 questions, `--provider openai`, `gpt-5`, after the judge bug fix):

| Method | Avg judge score |
|---|---|
| structured | 1.6 |
| compressed | 1.3 |
| long_context | 1.2 |
| vector | 0.9 |
| graph | 0.5 |

Consistent with the retrieval-quality ranking. **Small sample (n=10)** —
not yet run at `--full` (all 50) scale, and not yet run with the second
Anthropic API key needed for the inter-rater reliability check.

### Naturalness / readability (same n=10 run, computed retroactively)

| Method | Lexical similarity to gold | Flesch Reading Ease |
|---|---|---|
| structured | 0.303 | 40.9 |
| compressed | 0.299 | 33.9 |
| long_context | 0.186 | 52.6 |
| vector | 0.128 | 54.8 |
| graph | 0.156 | 44.7 |

**Real, worth flagging directly**: the two most accurate methods
(`structured`, `compressed`) are also the *least* readable (34-41 =
"difficult/college level"). All five methods fall in the "difficult" band
(30-50 on the 0-100 scale); none reach the ~60-70 general-audience range.
An accuracy-vs-accessibility tension the qualitative usability study should
probably probe directly.

## 5. Framework coverage — where each planned piece stands

| Piece | Status |
|---|---|
| Retrieval Hit@k/Recall@k/Precision, per method | Built, run (2-doc and 5-doc) |
| Response time | Built, run |
| Statistical significance | Built, run |
| Accuracy (LLM judge) | Built, run once at n=10 — needs `--full` |
| Naturalness/readability proxies | Built, computed |
| Inter-rater reliability (kappa) | Built, **not yet run** — needs two provider keys simultaneously |
| Authors-led ground truth | Exists (50 questions) |
| Expert-led ground truth | Pending — coming from domain experts (user's side) |
| LLM-generated-and-validated ground truth | Designed (plan drafted), not yet built |
| Assessment-form vs. Drexel comparison | Template ready, no data yet |
| Qualitative usability/trust study | Protocol drafted, needs IRB + participants |
| Corpus completeness | 5 of 17 available source documents ingested |
| graph/structured/compressed data completeness | Covers only the original 2 documents |

## 6. Reproducibility notes

- All runs referenced above are permanently saved under `eval/runs/` —
  each folder's `config.json` records the exact git commit and corpus
  state that produced it.
- `data/eval_results.json` is a "latest run" convenience copy only — it
  gets overwritten on every run; cite `eval/runs/` folders, not that file.
- Source PDFs live in `data/source_pdfs/` (gitignored, local-only, per the
  user's instruction not to push them).

## 7. What's next (open decisions, not yet made)

- Ingest the remaining 14 source PDFs, or close the graph/structured/compressed
  data gap for the 3 already-ingested documents first?
- Run `--generate --full` (and with `--second-judge-provider`) once fresh
  API keys are available, for statistically solid accuracy + inter-rater
  numbers instead of the current n=10 smoke test.
- Build the LLM-generated-and-validated question set (plan already drafted:
  `/Users/medha/.claude/plans/scalable-roaming-lightning.md`).
- Fill in `eval/drexel_comparison_template.json` once Drexel's original
  tool's answers are available.
- Submit the qualitative study protocol for IRB review.

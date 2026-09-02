# Paused: Google Drive knowledge-base ingestion

Paused at the user's request while mid-ingestion. **Nothing further has been
run or changed since this file was written** — this is an accurate snapshot
to resume from, not a plan. All 8 ingestion sub-agents stopped because the
session hit its API rate limit (reset 3:40pm America/New_York) — not because
of any error in the approach.

## What's already live (done, don't redo)

These code changes are complete, deployed, and independent of the ingestion
below — they work with whatever corpus exists, small or large:

- `backend/prompts.py` — `build_assessment_prompt` restructured so each
  flagged factor in a PIPE assessment report gets a **Potential concerns**
  bullet list and a **Suggested remedial action** bullet list, each bullet
  ending in a citation like `(NASEM 2019)` plus document+page — matching the
  format the user asked for.
- `backend/main.py` — assessment retrieval bumped from k=12 to k=20 to cover
  a larger corpus.
- `backend/providers.py` — fixed a real bug where responses could come back
  empty ("Sorry, I couldn't generate a response") because reasoning models
  spent their whole token budget on invisible reasoning; `MAX_TOKENS` raised
  1000→4000 (chat) and 1600→6000 (assessment), and both providers now raise
  a clear error instead of masking failures.
- `backend/constants.py` — 5 conditional follow-up questions added to the
  PIPE assessment form (q1a mixing-valve type, q4a recirc loop temp, q5a/b/c
  disinfectant residual level branching on q5's answer), with frontend
  support for conditional visibility (`frontend/src/assessment.js`).
- `data/raw/manifest.json` + refactored `scripts/chunk_documents.py` — the
  document list is now manifest-driven, not hardcoded (see
  `.claude/skills/sync-pipe-drive/SKILL.md` for the sync procedure).

## Ingestion status: 13 new source PDFs from the Drive folder

Folder: https://drive.google.com/drive/folders/1BlwpAZjQfHkUkPoLQXEiFY5ugBCstdE8

**None of the 6 files below are registered in `data/raw/manifest.json` yet**,
so none of this new content is live in the app yet — `data/chunks.json` is
still just the original 2 papers (39 chunks). The raw `.txt` files exist on
disk but the manifest still only lists `singh2020`/`singh2022`.

### Written to data/raw/ but NOT yet in the manifest — needs review before registering

| File | Source | Status |
|---|---|---|
| `doc3_raw.txt` | OSHA Technical Manual §III Ch.7, 1999 | **Incomplete** — 0 `[Page N]` markers found (just prose + a `[Note: ...]` annotation). Was likely cut off before finishing page-marker normalization. Re-check against the skill's step 3 before registering. |
| `doc8_raw.txt` | CDC 2017, "Developing a Water Management Program to Reduce Legionella Growth & Spread in Buildings" | Looks complete — 23 page markers, 616 lines. Not yet skimmed for quality per the skill's own caveat. |
| `doc13_raw.txt` | MIAC / Government of Western Australia 2010, "Code of Practice: Prevention and Control of Legionnaires' Disease" | Looks complete — 19 page markers, 408 lines. Has a `[Note: ...]` about something (check it). Not yet skimmed. |
| `doc14_raw.txt` | Dept. of Veterans Affairs 2008, VHA Directive 2008-010 | Looks complete — 22 page markers, 446 lines. Written directly by the orchestrating agent (one of "the two smallest" it did itself), not yet skimmed. |
| `doc15_raw.txt` | Dept. of Veterans Affairs 2014, VHA Directive 1061 | Looks complete — 35 page markers, 647 lines. Has a `[Note: ...]` flagging that Appendix C flow-chart diagrams weren't transcribed (expected/acceptable — diagrams aren't prose). Not yet skimmed otherwise. |
| `doc16_raw.txt` | CMS 2017, S&C 17-30 memo | Looks complete — 4 page markers, 78 lines (short document, plausible). Written directly by the orchestrating agent (the other "smallest" doc). Not yet skimmed. |

### Not started at all — still only in the Drive folder, no local file yet

| Source | Drive file ID | Drive title | driveModifiedTime |
|---|---|---|---|
| USEPA 1985 | `1wg6-fnmAiyO9dCwmVpPRG6blS_-KHM4T` | USEPA, 1985.pdf | 2026-08-31T18:57:20Z |
| NASEM 2019 | `1CZ4ZMaAmZ3bTMmfvR_HVW7o5LgMAjKXq` | NASEM 2019.pdf | 2026-08-31T18:57:17Z |
| CDC MAHC annex 2016 | `1IMqU643j1r937dMISsvciZjF3HnhdIyE` | CDC, MAHC annex, 2016.pdf | 2026-08-31T18:57:02Z |
| European Guidelines Working Group 2017 | `1tW4ARUvt5_iAalNnRiFMR6aaNvbNOFCw` | European Guidelines Working Group, 2017.pdf | 2026-08-31T18:57:08Z |
| CDC 2003 | `1ybSc6Mqw4nknd6qqqm3FkpQVSNUjNtuB` | CDC, 2003.pdf | 2026-08-31T18:56:55Z |
| Bartram, Chartier, Lee, Pond & Surman-Lee 2007 | `1Af8x4SyxvTxLL8YJr1C3_bfCttpeTiFd` | Bartram,Chartier,Lee,Pond,&Surman-Lee,2007.pdf | 2026-08-31T18:56:53Z |
| Health Technical Memorandum 04-01 Addendum | `1nwQgXIb8_fGyT6StyGFi3cmdyrjPlqen` | Health_Technical_Memorandum_04-01_Addendum.pdf | 2026-08-31T18:57:12Z |
| ASHRAE 2018 | `1QGKeqkVb7WYlx18i5qzIMoFagHI_-bMw` | ASHRAE-2018.pdf | 2026-08-31T18:56:48Z |

(CDC MAHC 2016 was assigned to the same sub-agent as VA 2014; it wrote VA
2014's file — `doc15_raw.txt` — before failing, so CDC MAHC 2016 itself
never got written.)

## Already registered in the manifest (unaffected, still correct)

```json
"singh2020" -> data/raw/doc1_raw.txt  (driveFileId 1y07TLevbOK-W6IkoeAXXVY7xe9tDU4WM)
"singh2022" -> data/raw/doc2_raw.txt  (driveFileId 17DWhnrFAoYJe4ohuxXWDjOHFLTzr9HP1)
```

## To resume

1. Review `doc3_raw.txt` (OSHA 1999) and fix its missing page-marker
   normalization, or re-extract it, per `.claude/skills/sync-pipe-drive/SKILL.md` step 3.
2. Skim `doc8`, `doc13`, `doc14`, `doc15`, `doc16` against the skill's
   quality guidance before trusting them.
3. Add manifest entries for all 6 above (id/title/short/file/driveFileId/
   driveTitle/driveModifiedTime — the table above has the Drive-side fields
   for the ones still needed; the doc3/8/13/14/15/16 rows need their
   driveFileId/driveTitle/driveModifiedTime pulled from the "not started"
   table's siblings — i.e. OSHA 1999's Drive ID is
   `1eRNyUPq1gpWqkYSirJLYMr7CBdPHU0w-`, CDC 2017's is
   `12dIKd0jcbRaHwXz24qRtYWAbtBTZMszi`, MIAC 2010's is
   `1t5kGLEVWpwCYwt5ZxG1gZJaoisZtk8Nr`, VA 2008's is
   `1g2wLTBxRHUWgyIcCEk0QKQyBkC-XqY8Y`, VA 2014's is
   `1HrkZ65aYz-1TQFimdRCV4itxDuX2e0io`, CMS 2017's is
   `1NL-TQTUfUzy_yYoQ1B_1cHcseYj4fTj1`).
4. Ingest the remaining 8 documents in the "not started" table.
5. Run `python scripts/build_app.py` to rebuild `data/chunks.json` (and the
   legacy `dist/index.html`) from the completed manifest.
6. Restart the backend (`uvicorn main:app --reload --port 8000` picks up
   the new corpus on the reload after `chunks.json` changes, or just
   restart it).
7. Delete this file once the ingestion is actually finished — it's a
   resume note, not permanent documentation.

Given the scale (13 large PDFs) and the rate-limit hit doing it in one
batch of parallel sub-agents, next time this may go faster processed a
few documents at a time rather than all 8 in parallel at once.

# Qualitative Usability/Trust Study Protocol — Draft

Skeleton for the human-subjects half of the evaluation. Not run yet — this
is a starting structure to edit, not a finished protocol. Fill in the
brackets, cut what doesn't apply, and treat everything here as a draft
until you've reviewed it.

## ⚠️ Before recruiting anyone: check IRB requirements

This involves human participants reacting to a tool and giving feedback —
that is human-subjects research. If this is going toward a Drexel-affiliated
publication, it very likely needs review by Drexel's IRB (or your home
institution's) *before* you recruit or run a single session, even for a
small/informal-feeling study. Confirm this with your advisor/PI before
scheduling anything below — this is a determination only you and your
institution can make, not something to route around.

## Research questions (from your framework)

1. **User-friendliness** — can someone unfamiliar with the system get a
   correct, useful answer without help?
2. **STT accessibility** — does speech-to-text input work well enough to be
   a viable input method for this tool? (Note: current frontend build —
   confirm whether STT is actually implemented yet, or whether this study
   would be testing a feature that still needs to be built first.)
3. **Bolding/highlighting of critical info** — do participants actually
   notice and correctly interpret the bolded values and ⚠️ warnings, or do
   they scan past them?
4. **Citation/referencing quality** — do participants trust the answer more
   because of the citations, do they check them, and do they correctly
   understand what's being cited?

## Proposed design (edit before use)

- **Participants**: [n=? — usability studies commonly report meaningful
  findings from as few as 5-8 participants per condition, but confirm a
  target with your advisor given your specific research questions and
  timeline]
- **Population**: [who? facility managers / building owners — the actual
  target users — or a general/student proxy population? This materially
  changes what the results can claim.]
- **Format**: moderated, one-on-one, think-aloud protocol (participant
  narrates their reasoning while using the tool) — recommended for capturing
  *why* trust/confusion happens, not just whether it did.
- **Consent**: informed consent required before any session — your IRB
  application will specify the exact required language; don't draft
  placeholder consent text here that might diverge from what gets approved.

## Draft task list

Have each participant complete a small set of realistic tasks, e.g.:

1. Ask the tool a question about their own (or a hypothetical) building's
   water heater setting, using whichever input method they'd naturally
   reach for first (typed or voice, if STT is available).
2. Complete the assessment form for a given scenario (use one of the
   scenarios from `eval/drexel_comparison_template.json` for consistency
   with the quantitative comparison) and read the generated report.
3. [Add 1-2 more tasks probing citation-checking behavior specifically —
   e.g. ask them to verify one claim in the answer against its cited
   source.]

## Draft measures per task

- **Task success**: did they get a correct answer / complete the form? (binary or partial-credit rubric — define before running)
- **Trust rating**: post-task Likert scale (e.g. 1-5, "I trust this answer is accurate") — consider System Usability Scale (SUS) or Trust in Automation scale as an established instrument rather than inventing one from scratch, since a validated instrument is much easier to defend in review.
- **Noticing rate**: did they mention/act on a bolded ⚠️ warning without being prompted?
- **Citation behavior**: did they click/read a citation; when asked "how do you know this is right," did they reference the source?
- **Think-aloud notes**: qualitative coding of confusion points, verbatim quotes worth citing in the writeup.

## Open decisions to resolve before running this

- [ ] IRB status confirmed
- [ ] Target participant population and count
- [ ] Whether STT is implemented in the current build (check before writing an STT task)
- [ ] Which validated instrument(s) to use for trust/usability rating
- [ ] Recording/data retention plan (audio/video consent, anonymization, storage location)
- [ ] Compensation, if any

# Handoff brief — control testing findings analysis

Paste sections 1–7 as your **first message** in a new ChatGPT conversation, and
upload `analysis.py`, `code_issues.py` and `decision_record.md` alongside it.
Section 8 holds the prompts for each later phase — don't paste those up front.

---

## 1. What I'm doing

I work in internal audit. I own the redesign of our control test workpaper
template and the underlying testing methodology. Separately from the redesign
itself, I'm analysing our own findings data from the last two years to work out
whether the way we test controls should change — and to document the evidence
behind any change I make.

The specific question in front of us:

> Should the workpaper allow Test of Operating Effectiveness to proceed when the
> Test of Design has already concluded Ineffective?

I already know, roughly, that about 70% of controls that failed design went on to
OE testing anyway, and I found no evidence it changed the overall audit opinion
or the severity of the original finding. This analysis is to redo that properly
so I can rely on it and document it.

Act as an analyst working with me on this. Be direct about weaknesses in the data
and in my reasoning. If a result doesn't support the change I'm expecting, say so
plainly — the whole point is that the write-up has to survive scrutiny.

## 2. The framework the analysis is built around

Control design is evaluated across six dimensions — WHO, WHAT, WHEN, WHERE, WHY,
HOW. A design conclusion is binary: if any dimension is deficient, the design is
ineffective. Historical issues are **not** tagged to any dimension, so part of
this work is coding them retrospectively.

## 3. What's already settled — don't reopen

- The binary design conclusion stands
- The six-dimension framework stands
- Findings-only data is a biased sample and I know it
- Analysis is by control test, not by audit

## 4. Files

- `analysis.py` — joins the exports, computes the core statistics. Two modes:
  `profile` prints distinct values and completeness; `run` does the analysis.
  All column mapping is in the CONFIG block at the top.
- `code_issues.py` — prepares blind coding batches, reassembles the JSON
  responses, scores agreement against a hand-coded calibration set.
- `decision_record.md` — the write-up template this all has to fill.

Both scripts were written before I'd seen the real field names. Treat the CONFIG
blocks as assumptions to be corrected, not as a spec.

## 5. Data being pulled

**Control tests** (one row per test): test ID · audit ID · control ID · design
conclusion · OE conclusion · design conclusion rationale · OE conclusion
rationale · OE performed flag · sample size · population size · test completion
date · audit status · control type / automation / frequency / preventive-detective
as separate fields · control description · control risk rating · audit team ·
preparer · reviewer

**Audit header** (one row per audit): audit ID · overall opinion · status · start
date · report issue date · entity · audit type

**Issues** (one row per issue): issue ID · title · description · root cause text ·
root cause category · severity · status · date raised · date closed · category ·
group · issue source · issue type · repeat flag · related control ID · related
audit ID · severity change history if it exists

**Link table**: test ID · issue ID · relationship type

**Test procedures** (separate, phase 3 only): test ID · procedure text

Exports are flat and joined in pandas. They are **not** exported with related
records flattened — that duplicates parent rows and inflates every count.

## 6. Non-negotiables

1. **Denominators are distinct control tests, never row counts.** Failure rates
   by control type are meaningless without the count of controls of that type
   actually tested.
2. **Issue coding is blind to outcome.** The coding file contains issue ID, title,
   description and rationale text only. Severity and conclusions are withheld.
3. **The rubric is frozen** once calibration is done, and goes into the write-up
   verbatim. No mid-run tuning.
4. **NO_FIT is a valid result**, not a failure. A large NO_FIT pile means the
   six-dimension framework has a gap, which is itself a finding.
5. **Hand-coded calibration comes first**, before any model-assisted coding, and
   the agreement rate gets reported.
6. **Record what would have falsified the conclusion**, and whether it appeared.

## 7. Known traps

- Blank OE conclusion may mean "not performed" or may mean "performed but not
  recorded." This inference drives the headline number — verify it before relying
  on it.
- In-flight audits look like "stopped after design failure." Filter to completed
  audits or the 30% is overstated.
- Historical design conclusions may have a partial/exceptions value predating the
  binary rule. Where those land changes the result.
- If severity is never revised for *any* issue, then "OE didn't change severity"
  describes the workflow, not the value of OE testing. Test this explicitly.
- Self-identified and regulatory issues may have no control design dimension at
  all and will dilute the coding distribution. Check `issue source` before
  deciding whether to filter.
- Findings-raised date and test-completion date are different anchors for the
  two-year window. Pick one deliberately.

---

## 8. Phase prompts — use these as you go, not up front

### Phase 1 — profile the exports

> Here are the exports. Before any analysis: for each file tell me the row count
> vs distinct count of its ID column, the completeness of every field as a
> percentage, and the distinct values of every conclusion, status, type and
> severity field. Then tell me which of the assumptions in the CONFIG blocks are
> wrong, and specifically: does the grain match one row per control test, and how
> do issues actually relate to tests? Don't start analysing yet.

### Phase 2 — correct and run

> Update the CONFIG blocks in analysis.py to match the real fields and value
> sets, explain each change you made, then run it. Walk me through the results
> one question at a time rather than dumping all output. For the stop-rule number,
> show me how sensitive it is to the OE-performed inference and to excluding
> in-flight audits.

### Phase 3 — the rescue cases

> Pull the control tests where design concluded ineffective but OE concluded
> effective. Show me the design rationale and OE rationale text for each. I want
> to read these individually — they decide whether a hard gate is right or whether
> it needs an override path.

### Phase 4 — calibration

> Run code_issues.py calibrate to get my hand-coding sample. Then, while I code:
> read the rubric in the script and tell me where you think it will be ambiguous
> against this actual issue text. Suggest specific wording changes, but don't
> apply them until I've finished hand-coding.

### Phase 5 — batch coding

> Rubric is frozen. Run prepare, and I'll work through the batches. Then assemble
> and give me the agreement figure, the confusion matrix, and the NO_FIT items
> grouped by what they have in common.

### Phase 6 — write-up

> Fill in decision_record.md from the actual results. Write the limitations
> section honestly, including anything the data couldn't answer. In the section on
> what would have falsified the conclusion, state what I said I'd accept as
> contrary evidence and whether it turned up.

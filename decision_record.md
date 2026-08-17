# Decision Record: OE testing following a design failure

**Status:** draft · **Owner:** · **Date:**

## Question

Should the control test workpaper permit Test of Operating Effectiveness where
the Test of Design has concluded Ineffective?

## Population and scope

- Source records: control tests, issues, test–issue relationships
- Extract date:
- Date window:
- Distinct control tests in scope:
- Distinct issues in scope:
- Exclusions applied and why:

## Method

Three flat exports joined in `analysis.py`. Denominators are distinct control
tests, not exported rows. Conclusion values normalised to pass / fail / partial /
n-a via the mapping recorded in `CONFIG` — reproduced in Appendix A.

Issues coded to the 5Ws & H by `code_issues.py`. Coding was performed on issue
title, description and root cause text only; conclusion and severity fields were
withheld from the coder so the coding is blind to the outcome under test.

## Coding reliability

- Calibration set hand-coded first: n =
- Agreement between hand coding and assisted coding: %
- Codes with weakest agreement:
- Rubric version used (frozen at): see Appendix B

## Results

| Measure | Value |
|---|---|
| Control tests concluding design ineffective | |
| Of those, proceeded to OE testing | |
| Of those, OE concluded effective (possible rescue) | |
| Issues where severity was revised after OE completed | |
| Estimated testing effort on OE work that did not change a conclusion | |

Distribution across the Ws, and the NO_FIT share:

| Code | Count | % |
|---|---|---|
| WHO | | |
| WHAT | | |
| WHEN | | |
| WHERE | | |
| WHY | | |
| HOW | | |
| NO_FIT | | |

## Limitations

- Findings exist only where testing occurred and an issue was raised. Categories
  with no findings are not evidence of effective control.
- Root cause text is recorded at issue close and reflects the auditor's judgement
  at that point.
- *(If severity is never revised for any issue:)* The absence of severity change
  following OE testing describes the severity workflow rather than the
  information value of the OE work. State which of these the data supports.
- Assisted coding is not a substitute for a subject-matter read of the NO_FIT and
  low-confidence items; those were reviewed individually.

## What would have changed the conclusion

State plainly what result would have argued against the change — e.g. a material
count of controls where design failed and OE testing subsequently supported an
effective or downgraded conclusion. Record what was actually found.

## Decision

-
- Override path (if any) and what justification it requires:
- Effect on the workpaper:

## Appendix A — conclusion value mapping

## Appendix B — coding rubric as frozen

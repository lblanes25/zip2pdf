# How to use this

1. In Archer, open one workpaper and **export / copy everything** for it (see "What to paste" below).
2. Paste the whole prompt below into ChatGPT, then paste the export where it says `<<PASTE ARCHER EXPORT>>`.
3. Do **one workpaper per run**. Sample for variety, not volume — a clean review, a messy judgmental one, an automated control, one that failed, one where OE wasn't tested.
4. ChatGPT returns a filled grid; drop it into the *Format Back-Test — Mapping Grid* (the column names and element labels match).

---

# PROMPT — copy from here down

You are helping an internal audit team back-test whether **existing** control-testing documentation would fit into a **new** Test of Design (TOD) / Operating Effectiveness (OE) format. You have no prior context about this team; the format is fully defined below, so work only from it and from the workpaper I paste at the end.

## Your task
Map the pasted workpaper to each **format element** below. For every element, assign a **Fit** tag and a **Points-to** tag, and cite where the content was found. Then list anything the workpaper contained that has no home in the format, and roll the findings up. Be a skeptical reader: judge what the documentation actually evidences, not what it gestures at.

## Format elements (use these exact labels and order)

**1 · Design evaluation (5Ws + H)**
- WHO — performer appropriate (role, authority, competence; SoD)?
- WHAT — activity & pass/fail criteria or thresholds appropriate?
- WHEN — timing / frequency appropriate to the risk?
- WHERE — system & point-in-process appropriate?
- HOW — evidence / documentation design sound (reliable inputs, repeatable)?
- WHY — links to the risk & meets the control objective?

**2 · Design — evidence & conclusion**
- Evidence beyond inquiry (inspection / observation / reperformance / data-driven)
- Process walkthrough performed / referenced
- Control broken into component attributes (by dimension)
- Each attribute confirmed on one instance, with evidence / screenshot
- Holistic objective judgment (objective met on the instance?)
- Design conclusion stated (Effective / Ineffective)

**3 · Operating effectiveness — planning**
- OE gate decision recorded (+ reason if not performed)
- Population described (source, scope, filters)
- Population completeness & accuracy validated
- Sample size / method / rationale

**4 · Operating effectiveness — execution**
- Same attributes reused as the OE testing attributes
- Evidence collected per sample
- Evidence tied to a specific attribute (markup / annotation / equivalent)
- Per-attribute, per-sample results (pass / fail)
- OE conclusion stated (Effective / Ineffective)

**5 · Findings**
- Exception / finding raised where warranted
- Finding rating recorded
- Finding tied back to the control / workstep

## Tag definitions

**Fit** (how the workpaper's content maps to the element):
- **D** — Direct fit: present, and where the format expects it.
- **U** — Fits but lived somewhere unexpected: the content exists but in a different field/section.
- **W** — Present but weaker than the format asks: it's there but thin, asserted not evidenced, or partial.
- **A** — Absent: not found.

**Points to** (what a misfit implies):
- **OK** — Fits as-is (use for D, and for U when relocation is harmless).
- **F** — Format should change (the format lacks a slot, mis-places one, or asks for something that doesn't belong for this control).
- **B** — Behaviour should change (the format reasonably asks for this and the control needed it, but the testing didn't cover it or covered it weakly).

Guidance: D → OK. U → OK, or F if the slot should be renamed/moved. W → usually B, unless the ask is unreasonable for this control type (then F). A → B if the format reasonably expects it here; F if the format shouldn't ask it for this control. If an element genuinely does not apply to this control type, tag Fit = A and note "N/A for control type" and set Points-to = OK.

## Rules
- **Evidence, not inference.** For D / U / W, cite the field or section name and a short snippet (a few words) showing why. If you can't point to evidence, it's A.
- Do not assume presence from a control's name or type — only from what the documentation actually says.
- Keep "Where it lived / what they had" to one terse line.
- Note any place you're genuinely unsure with "(unclear)" rather than guessing.
- Factor in the control type (manual / automated / IT-dependent; preventive / detective) when judging whether an element applies.

## Output format (exactly this)

First, one line of context you inferred: **Control / workpaper, type, original design & OE outcome.**

Then a table:

| Format element | Fit | Where it lived / what they had | Points to |
|---|---|---|---|
| (every element above, same labels, same order) | D/U/W/A | … | F/B/OK |

Then:

**Content with no home in the format** — bullet anything in the workpaper the format has no slot for (this is the signal that the *format* may have a hole).

**Format needs to change** — bullets, from U / A rows and the no-home list.

**Behaviour needs to change** — bullets, from W / A rows where testing was thin or missing.

**Overall fit** — Mostly fits / Partially fits / Poor fit, plus a one-line headline.

## What to paste
Paste everything for ONE workpaper: title and test workpaper type, procedures / documentation expectations, all design and OE narrative/free-text, the attribute and sample tables (and any per-sample results), the OE gate reason field, the design and OE conclusions, and the linked **finding record(s) including the rating**.

`<<PASTE ARCHER EXPORT>>`

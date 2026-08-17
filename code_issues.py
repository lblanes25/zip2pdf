"""
Code issues to the 5Ws & H, blind to outcome.

Workflow:
  1. python code_issues.py calibrate
        -> calibration_to_code.csv  (50 issues, hand-code these yourself first)
        Fill in the primary_w / secondary_w / no_fit columns by hand, save as
        calibration_coded.csv. Do this BEFORE looking at any model output.

  2. python code_issues.py prepare
        -> batches/batch_01.txt ... each file is a complete, copy-pasteable prompt.
        The calibration issues are included again in the batches on purpose --
        that is how you measure agreement.

  3. Paste each batch. Save each reply as responses/response_01.json (etc).

  4. python code_issues.py assemble
        -> coded_issues.csv, plus an agreement report against your hand codes.

Dependencies: pandas
"""

import sys
import os
import json
import glob
import pandas as pd

CONFIG = {
    "issues_file": "data/issues.csv",
    "cols": {
        "issue_id":    "Issue ID",
        "title":       "Issue Title",
        "description": "Issue Description",
        "root_cause":  "Root Cause",
    },
    "batch_size": 25,
    "calibration_n": 50,
    "seed": 42,
    "batch_dir": "batches",
    "response_dir": "responses",
}

VALID_CODES = ["WHO", "WHAT", "WHEN", "WHERE", "WHY", "HOW", "NO_FIT"]

# --------------------------------------------------------------------------
# The rubric. Edit this to match your own definitions -- then keep it FROZEN
# for the whole run, and paste it into the write-up verbatim.
# --------------------------------------------------------------------------

RUBRIC = """\
You are coding internal audit issues against a control design framework. For each
issue, identify which design dimension was deficient -- that is, what was missing
or inadequate about how the control was DESIGNED. Do not code the business topic
of the issue, and do not code how the control performed in operation.

The dimensions:

WHO   - the person or role performing the control. Ownership undefined or wrong,
        insufficient authority, competence, or independence, segregation-of-duties
        problems, reliance on an individual rather than a role.

WHAT  - the control activity itself. The action performed is not specified, is the
        wrong action, or does not actually examine the thing that matters. Includes
        controls that check that something happened but not whether it was correct.

WHEN  - timing and frequency relative to the risk. Control operates too late to
        prevent or detect the exposure, runs at a cadence that leaves gaps, or has
        no defined trigger.

WHERE - the system, source, population, or scope the control operates over. Includes
        incomplete population coverage, unreliable source data, wrong system of
        record, gaps between in-scope and out-of-scope entities.

WHY   - whether the control, as designed, mitigates its intended part of the
        identified risk. Use this when the control is coherent in itself but is
        aimed at the wrong risk or does not address the exposure it is mapped to.

HOW   - the method and procedure. No documented procedure, thresholds or criteria
        undefined, no evidence retained, exceptions not escalated or resolved,
        review performed without defined review criteria.

NO_FIT - the deficiency does not correspond to any dimension above. Use this
        genuinely and readily. Do not force a fit. Examples that often land here:
        pure operating failures with no design flaw, control absent entirely,
        governance or culture findings, issues about remediation of a prior issue.

Rules:
- primary_w is the single dimension that best explains the deficiency.
- secondary_w only if a second dimension is clearly and separately deficient;
  otherwise null. Do not pad.
- If the text is too thin to judge, set primary_w to "NO_FIT" and confidence "low".
- rationale must be one short sentence quoting or paraphrasing the specific words
  in the issue that drove the code.
- Judge only from the text given. Do not infer facts that are not present.

Return ONLY a JSON array. No prose before or after. No markdown code fences.
One object per issue, in the same order given, with exactly these keys:

[
  {
    "issue_id": "<the id exactly as given>",
    "primary_w": "WHO|WHAT|WHEN|WHERE|WHY|HOW|NO_FIT",
    "secondary_w": "WHO|WHAT|WHEN|WHERE|WHY|HOW|null",
    "confidence": "high|medium|low",
    "rationale": "<one short sentence>"
  }
]
"""


def load_issues():
    path = CONFIG["issues_file"]
    if not os.path.exists(path):
        sys.exit(f"Missing input file: {path}")
    df = (pd.read_excel(path, dtype=str) if path.lower().endswith((".xlsx", ".xlsm"))
          else pd.read_csv(path, dtype=str))
    cols = CONFIG["cols"]
    missing = [c for c in cols.values() if c not in df.columns]
    if missing:
        sys.exit(f"Columns not found: {missing}\nAvailable: {list(df.columns)}")
    out = df[list(cols.values())].rename(columns={v: k for k, v in cols.items()})
    out = out.drop_duplicates(subset=["issue_id"])
    # Blind by construction: severity, conclusions and dates are never loaded.
    return out.fillna("")


def calibrate():
    df = load_issues()
    n = min(CONFIG["calibration_n"], len(df))
    sample = df.sample(n=n, random_state=CONFIG["seed"]).copy()
    sample["primary_w"] = ""
    sample["secondary_w"] = ""
    sample["notes"] = ""
    sample.to_csv("calibration_to_code.csv", index=False)
    print(f"Wrote calibration_to_code.csv ({n} issues).")
    print("Hand-code primary_w and secondary_w, save as calibration_coded.csv.")
    print(f"Valid codes: {', '.join(VALID_CODES)}")
    print("\nWhile coding, note anything the rubric handles badly and revise RUBRIC")
    print("before running prepare. After that, freeze it.")


def format_issue(row, n):
    return (f"--- ISSUE {n} ---\n"
            f"issue_id: {row['issue_id']}\n"
            f"title: {row['title']}\n"
            f"description: {row['description']}\n"
            f"root_cause: {row['root_cause']}\n")


def prepare():
    df = load_issues()
    os.makedirs(CONFIG["batch_dir"], exist_ok=True)
    for f in glob.glob(f"{CONFIG['batch_dir']}/batch_*.txt"):
        os.remove(f)

    size = CONFIG["batch_size"]
    batches = [df.iloc[i:i + size] for i in range(0, len(df), size)]

    for i, batch in enumerate(batches, start=1):
        body = "\n".join(format_issue(r, j)
                         for j, (_, r) in enumerate(batch.iterrows(), start=1))
        text = (f"{RUBRIC}\n"
                f"There are {len(batch)} issues in this batch. Return exactly "
                f"{len(batch)} objects.\n\n{body}")
        path = f"{CONFIG['batch_dir']}/batch_{i:02d}.txt"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    print(f"Wrote {len(batches)} batch files to ./{CONFIG['batch_dir']}/")
    print(f"({len(df)} issues, {size} per batch)")
    print(f"\nPaste each into a FRESH chat -- do not continue one conversation")
    print("across batches, or earlier batches will bias later coding.")
    print(f"Save each reply as {CONFIG['response_dir']}/response_NN.json")


def parse_response(path):
    raw = open(path, encoding="utf-8").read().strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1:
        print(f"  ! {os.path.basename(path)}: no JSON array found, skipped")
        return []
    try:
        return json.loads(raw[start:end + 1])
    except json.JSONDecodeError as e:
        print(f"  ! {os.path.basename(path)}: invalid JSON ({e}), skipped")
        return []


def assemble():
    files = sorted(glob.glob(f"{CONFIG['response_dir']}/response_*.json"))
    if not files:
        sys.exit(f"No files in ./{CONFIG['response_dir']}/")

    records = []
    for f in files:
        records.extend(parse_response(f))
    if not records:
        sys.exit("Nothing parsed.")

    coded = pd.DataFrame(records)
    coded["issue_id"] = coded["issue_id"].astype(str).str.strip()
    for c in ["primary_w", "secondary_w"]:
        if c in coded:
            coded[c] = (coded[c].astype(str).str.strip().str.upper()
                        .replace({"NONE": "", "NULL": "", "NAN": ""}))

    bad = coded[~coded["primary_w"].isin(VALID_CODES)]
    if not bad.empty:
        print(f"  ! {len(bad)} rows with an invalid primary_w: "
              f"{bad['primary_w'].unique().tolist()}")

    dupes = coded["issue_id"].duplicated().sum()
    if dupes:
        print(f"  ! {dupes} duplicate issue_id in responses -- keeping first")
        coded = coded.drop_duplicates(subset=["issue_id"])

    issues = load_issues()
    missed = set(issues["issue_id"]) - set(coded["issue_id"])
    if missed:
        print(f"  ! {len(missed)} issues have no code. Re-run those batches.")
        pd.Series(sorted(missed)).to_csv("uncoded_issue_ids.csv",
                                         index=False, header=["issue_id"])

    coded.to_csv("coded_issues.csv", index=False)
    print(f"\nWrote coded_issues.csv ({len(coded)} rows)")

    print("\n=== DISTRIBUTION ===")
    print(coded["primary_w"].value_counts().to_string())
    nofit = (coded["primary_w"] == "NO_FIT").mean()
    print(f"\nNO_FIT: {nofit:.1%}")
    print("This is the headline number. A large NO_FIT pile means the framework")
    print("has a gap -- read those issues to find the missing question.")
    if "confidence" in coded:
        print("\n=== CONFIDENCE ===")
        print(coded["confidence"].value_counts().to_string())

    agreement(coded)


def agreement(coded=None):
    if coded is None:
        coded = pd.read_csv("coded_issues.csv", dtype=str)
    if not os.path.exists("calibration_coded.csv"):
        print("\n  ! calibration_coded.csv not found -- agreement not measured.")
        print("    Without it the coding has no defensible accuracy figure.")
        return

    hand = pd.read_csv("calibration_coded.csv", dtype=str)
    hand["issue_id"] = hand["issue_id"].astype(str).str.strip()
    hand["primary_w"] = hand["primary_w"].fillna("").str.strip().str.upper()
    hand = hand[hand["primary_w"] != ""]

    m = hand[["issue_id", "primary_w"]].merge(
        coded[["issue_id", "primary_w"]], on="issue_id",
        suffixes=("_hand", "_model"))
    if m.empty:
        print("\n  ! No overlap between calibration set and coded issues.")
        return

    match = m["primary_w_hand"] == m["primary_w_model"]
    print("\n=== AGREEMENT vs HAND CODING ===")
    print(f"  compared: {len(m)}")
    print(f"  agreement: {match.mean():.1%}")
    print("\n  by hand-assigned code:")
    per = m.assign(match=match).groupby("primary_w_hand")["match"].agg(["size", "mean"])
    per["mean"] = (per["mean"] * 100).round(1)
    print(per.to_string())

    dis = m[~match]
    if not dis.empty:
        dis.to_csv("disagreements.csv", index=False)
        print(f"\n  {len(dis)} disagreements -> disagreements.csv")
        print("\n  confusion (hand rows x model cols):")
        print(pd.crosstab(m["primary_w_hand"], m["primary_w_model"]).to_string())

    print("\n  Report the agreement figure in the write-up. Below roughly 70%,")
    print("  the rubric is the problem, not the coder -- tighten the definitions")
    print("  that show up in disagreements.csv and re-run rather than hand-fixing.")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    fn = {"calibrate": calibrate, "prepare": prepare,
          "assemble": assemble, "agreement": agreement}.get(mode)
    if not fn:
        sys.exit("Usage: python code_issues.py [calibrate|prepare|assemble|agreement]")
    fn()

"""
Control testing analysis: does OE testing after a design failure change anything?

Run in two passes:
    python analysis.py profile    # prints distinct values so you can fill in the maps
    python analysis.py run        # runs the analysis, writes ./output/

Inputs are three FLAT exports. Do not export related records flattened into one
file -- Archer duplicates the parent row once per relationship and every count
downstream inflates.

Dependencies: pandas (openpyxl too, if your exports are .xlsx)
"""

import sys
import os
import pandas as pd

# --------------------------------------------------------------------------
# CONFIG -- edit everything in this block, nothing below it
# --------------------------------------------------------------------------

CONFIG = {
    "files": {
        "tests":  "data/control_tests.csv",
        "issues": "data/issues.csv",
        "links":  "data/test_issue_links.csv",
    },

    # Map your export's column names onto the names this script uses.
    # Set optional ones to None if the field doesn't exist in your export.
    "tests_cols": {
        "test_id":            "Test ID",
        "audit_id":           "Audit ID",
        "entity":             "Auditable Entity",
        "control_id":         "Control ID",
        "control_type":       "Control Type",
        "design_conclusion":  "Design Conclusion",
        "oe_conclusion":      "OE Conclusion",
        "oe_performed":       None,          # explicit Y/N flag, if you have one
        "sample_size":        "Sample Size",
        "audit_team":         "Audit Team",  # used for the "who stopped" cut
        "risk_rating":        None,          # control or audit risk rating, if available
        "test_date":          "Test Completed Date",
    },

    "issues_cols": {
        "issue_id":          "Issue ID",
        "title":             "Issue Title",
        "description":       "Issue Description",
        "root_cause":        "Root Cause",
        "category":          "Issue Category",
        "group":             "Group",
        "severity":          "Severity",
        "severity_original": None,  # if severity was ever versioned, map both
        "severity_final":    None,
        "raised_date":       "Date Raised",
    },

    "links_cols": {
        "test_id":  "Test ID",
        "issue_id": "Issue ID",
    },

    # Normalise messy conclusion text to: "pass" | "fail" | "partial" | "na"
    # Run `profile` first -- it prints every distinct value it finds.
    # Comparison is case-insensitive and whitespace-stripped.
    "design_map": {
        "effective":            "pass",
        "adequate":             "pass",
        "design effective":     "pass",
        "ineffective":          "fail",
        "inadequate":           "fail",
        "design ineffective":   "fail",
        "not applicable":       "na",
        "n/a":                  "na",
    },

    "oe_map": {
        "effective":            "pass",
        "operating effectively": "pass",
        "ineffective":          "fail",
        "partially effective":  "partial",
        "not applicable":       "na",
        "n/a":                  "na",
        "not tested":           "na",
    },

    # Date window for the population
    "date_from": "2024-08-01",
    "date_to":   "2026-08-01",

    "output_dir": "output",
}


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def read_any(path):
    if not os.path.exists(path):
        sys.exit(f"Missing input file: {path}")
    if path.lower().endswith((".xlsx", ".xlsm")):
        return pd.read_excel(path, dtype=str)
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])


def apply_cols(df, colmap, label):
    """Rename mapped columns to canonical names; drop the rest."""
    missing = [src for src in colmap.values() if src and src not in df.columns]
    if missing:
        print(f"  ! {label}: columns not found in export: {missing}")
        print(f"    available: {list(df.columns)}")
        sys.exit(1)
    rename = {src: dst for dst, src in colmap.items() if src}
    out = df[list(rename.keys())].rename(columns=rename)
    for dst, src in colmap.items():
        if not src:
            out[dst] = pd.NA
    return out


def norm(series, mapping):
    key = series.fillna("").astype(str).str.strip().str.lower()
    return key.map(mapping).fillna("unmapped")


def load():
    tests = apply_cols(read_any(CONFIG["files"]["tests"]),
                       CONFIG["tests_cols"], "tests")
    issues = apply_cols(read_any(CONFIG["files"]["issues"]),
                        CONFIG["issues_cols"], "issues")
    links = apply_cols(read_any(CONFIG["files"]["links"]),
                       CONFIG["links_cols"], "links")
    return tests, issues, links


# --------------------------------------------------------------------------
# Profile pass
# --------------------------------------------------------------------------

def profile():
    tests, issues, links = load()

    print("\n=== ROW COUNTS vs DISTINCT IDS ===")
    print(f"tests:  {len(tests):>6} rows, {tests['test_id'].nunique():>6} distinct test_id")
    print(f"issues: {len(issues):>6} rows, {issues['issue_id'].nunique():>6} distinct issue_id")
    print(f"links:  {len(links):>6} rows, "
          f"{links.drop_duplicates().shape[0]:>6} distinct pairs")
    if len(tests) != tests["test_id"].nunique():
        print("  ! tests has duplicate test_id -- likely a flattened export. Fix before running.")
    if len(issues) != issues["issue_id"].nunique():
        print("  ! issues has duplicate issue_id -- likely a flattened export. Fix before running.")

    print("\n=== DISTINCT VALUES (copy into design_map / oe_map) ===")
    for col in ["design_conclusion", "oe_conclusion", "control_type"]:
        print(f"\n-- tests.{col}")
        print(tests[col].fillna("(blank)").value_counts().to_string())
    for col in ["severity", "category", "group"]:
        if issues[col].notna().any():
            print(f"\n-- issues.{col}")
            print(issues[col].fillna("(blank)").value_counts().head(25).to_string())

    print("\n=== COMPLETENESS ===")
    for name, df in [("tests", tests), ("issues", issues)]:
        pct = (df.notna().mean() * 100).round(1).sort_values()
        print(f"\n-- {name} (% populated)")
        print(pct.to_string())

    sev_versioned = (CONFIG["issues_cols"]["severity_original"]
                     and CONFIG["issues_cols"]["severity_final"])
    print("\n=== SEVERITY REVISION ===")
    if sev_versioned:
        print("  Two severity columns mapped -- the revision test can run.")
    else:
        print("  Only one severity column. You cannot test whether OE testing changed")
        print("  severity, only whether severity correlates with it. Record this as a")
        print("  limitation in the write-up, or source a revision history.")


# --------------------------------------------------------------------------
# Analysis pass
# --------------------------------------------------------------------------

def prepare(tests, issues, links):
    tests = tests.drop_duplicates(subset=["test_id"]).copy()
    issues = issues.drop_duplicates(subset=["issue_id"]).copy()
    links = links.drop_duplicates().copy()

    tests["design"] = norm(tests["design_conclusion"], CONFIG["design_map"])
    tests["oe"] = norm(tests["oe_conclusion"], CONFIG["oe_map"])

    for col, label in [("design", "design_conclusion"), ("oe", "oe_conclusion")]:
        n = (tests[col] == "unmapped").sum()
        if n:
            vals = tests.loc[tests[col] == "unmapped", label].dropna().unique()[:10]
            print(f"  ! {n} rows unmapped on {label}: {list(vals)}")

    # Did OE testing happen? Explicit flag wins; otherwise infer from the conclusion.
    if CONFIG["tests_cols"]["oe_performed"]:
        flag = tests["oe_performed"].fillna("").astype(str).str.strip().str.lower()
        tests["oe_done"] = flag.isin(["y", "yes", "true", "1", "performed"])
    else:
        tests["oe_done"] = tests["oe"].isin(["pass", "fail", "partial"])
        print("  i oe_performed not mapped -- inferring from a non-blank OE conclusion.")

    if CONFIG["tests_cols"]["test_date"]:
        d = pd.to_datetime(tests["test_date"], errors="coerce")
        before = len(tests)
        tests = tests[d.between(CONFIG["date_from"], CONFIG["date_to"])]
        print(f"  i date filter: {before} -> {len(tests)} tests")

    return tests, issues, links


def q1_stop_rule(tests):
    """Of design failures, how many went on to OE testing?"""
    failed = tests[tests["design"] == "fail"]
    n = len(failed)
    if n == 0:
        print("No design failures in scope -- check design_map.")
        return None, failed
    went_on = int(failed["oe_done"].sum())
    print("\n=== Q1: DESIGN FAILURE -> OE TESTING ===")
    print(f"  design failures:            {n}")
    print(f"  went on to OE testing:      {went_on}  ({went_on / n:.1%})")
    print(f"  stopped after design:       {n - went_on}  ({(n - went_on) / n:.1%})")

    print("\n  OE outcome where OE was performed after a design failure:")
    print(failed[failed["oe_done"]]["oe"].value_counts().to_string())
    print("\n  ^ any 'pass' here is a case where OE arguably rescued the control.")
    print("    Read those individually -- they decide whether the gate needs an override.")
    return went_on / n, failed


def q2_who_stopped(failed):
    """The 30% already have an informal rule. Find it."""
    print("\n=== Q2: WHO STOPPED AFTER DESIGN FAILURE ===")
    for dim in ["audit_team", "control_type", "risk_rating", "entity"]:
        if failed[dim].isna().all():
            continue
        g = failed.groupby(failed[dim].fillna("(blank)")).agg(
            tests=("test_id", "nunique"),
            went_on=("oe_done", "sum"),
        )
        g = g[g["tests"] >= 5]
        if g.empty:
            continue
        g["pct_went_on"] = (g["went_on"] / g["tests"] * 100).round(1)
        print(f"\n-- by {dim} (n >= 5)")
        print(g.sort_values("pct_went_on").to_string())


def q3_severity(failed, issues, links):
    """Did the OE work move severity?"""
    print("\n=== Q3: SEVERITY ===")
    linked = (links.merge(failed[["test_id", "oe_done", "oe", "control_type"]], on="test_id")
                   .merge(issues, on="issue_id"))
    if linked.empty:
        print("  No issues linked to design failures -- check the link table keys.")
        return linked

    print(f"  issues linked to a design-failed control: {linked['issue_id'].nunique()}")
    ct = pd.crosstab(linked["severity"].fillna("(blank)"), linked["oe_done"])
    print("\n  severity x whether OE was performed:")
    print(ct.to_string())

    if linked["severity_original"].notna().any() and linked["severity_final"].notna().any():
        changed = linked["severity_original"].str.strip().str.lower() != \
                  linked["severity_final"].str.strip().str.lower()
        print(f"\n  severity revised at all: {int(changed.sum())} of {len(linked)}")
        print("\n  revised, split by whether OE was performed:")
        print(pd.crosstab(changed, linked["oe_done"]).to_string())
        if changed.sum() == 0:
            print("\n  ! Severity is never revised for anyone. That means 'OE didn't change")
            print("    severity' describes the workflow, not the value of OE testing.")
    else:
        print("\n  ! No severity revision history mapped. The strongest version of this")
        print("    test cannot be run -- record it as a limitation.")
    return linked


def q4_rates_by_type(tests):
    """Failure rates need distinct-control-test denominators."""
    print("\n=== Q4: RATES BY CONTROL TYPE ===")
    if tests["control_type"].isna().all():
        print("  control_type not mapped.")
        return None
    g = tests.groupby(tests["control_type"].fillna("(blank)")).agg(
        tested=("test_id", "nunique"),
        design_fail=("design", lambda s: (s == "fail").sum()),
        oe_fail=("oe", lambda s: (s == "fail").sum()),
        oe_tested=("oe_done", "sum"),
    )
    g["design_fail_rate"] = (g["design_fail"] / g["tested"] * 100).round(1)
    g["oe_fail_rate"] = (g["oe_fail"] / g["oe_tested"].replace(0, pd.NA) * 100).round(1)
    print(g.sort_values("tested", ascending=False).to_string())
    print("\n  ^ oe_fail_rate is over controls actually OE-tested, not all controls.")
    return g


def q5_effort(failed):
    """Rough size of the work that changed nothing."""
    print("\n=== Q5: EFFORT ===")
    wasted = failed[failed["oe_done"] & (failed["oe"] != "pass")]
    print(f"  design-failed controls OE-tested that still concluded fail/partial: {len(wasted)}")
    s = pd.to_numeric(wasted["sample_size"], errors="coerce")
    if s.notna().any():
        print(f"  total sampled items across those tests: {int(s.sum())}")
        print(f"  median sample size: {s.median():.0f}")
        print("\n  Multiply by your own per-item testing time for the hours figure.")
    else:
        print("  sample_size not usable -- substitute an average hours-per-test estimate.")


def run():
    tests, issues, links = load()
    tests, issues, links = prepare(tests, issues, links)

    os.makedirs(CONFIG["output_dir"], exist_ok=True)

    _, failed = q1_stop_rule(tests)
    if failed is None or failed.empty:
        return
    q2_who_stopped(failed)
    linked = q3_severity(failed, issues, links)
    q4_rates_by_type(tests)
    q5_effort(failed)

    out = CONFIG["output_dir"]
    tests.to_csv(f"{out}/tests_clean.csv", index=False)
    failed.to_csv(f"{out}/design_failures.csv", index=False)
    if linked is not None and not linked.empty:
        linked.to_csv(f"{out}/design_failure_issues.csv", index=False)
        # Hand-read these; they decide whether the gate needs an override path.
        rescued = linked[linked["oe_done"] & (linked["oe"] == "pass")]
        if not rescued.empty:
            rescued.to_csv(f"{out}/possible_oe_rescues.csv", index=False)
    print(f"\nWrote CSVs to ./{out}/")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "profile"
    if mode == "profile":
        profile()
    elif mode == "run":
        run()
    else:
        sys.exit("Usage: python analysis.py [profile|run]")

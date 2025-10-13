# scorer.py
# Aligns with Chap 3: Bloom-based Dependency Score, Over-reliance logic (freq=5 & bloom=6 & diff=5),
# Strategic vs Regular classification, Confidence & Productivity composites (with reverse-coded items),
# and adds live cohort P75 tagging for total dependency.

import pandas as pd
import numpy as np
import re
from typing import Dict, Tuple, List

# ----------------------------
# Helpers: parsing & mappings
# ----------------------------

FREQ_MAP = {
    "Never": 1,
    "Occasionally": 2,
    "Sometimes": 3,
    "Often": 4,
    "Always": 5
}

LIKERT_MAP = {
    "Strongly Disagree": 1,
    "Disagree": 2,
    "Neutral": 3,
    "Agree": 4,
    "Strongly Agree": 5
}

def to_num_freq(x):
    if pd.isna(x):
        return np.nan
    if isinstance(x, (int, float)):
        return int(x)
    x = str(x).strip()
    return FREQ_MAP.get(x, pd.to_numeric(x, errors="coerce"))

def to_num_likert(x):
    if pd.isna(x):
        return np.nan
    if isinstance(x, (int, float)):
        return int(x)
    x = str(x).strip()
    return LIKERT_MAP.get(x, pd.to_numeric(x, errors="coerce"))

def to_num_difficulty(x):
    # Linear scale 1–5; Google Forms usually exports as numbers or strings "1".."5"
    return pd.to_numeric(x, errors="coerce")

def col_like(df: pd.DataFrame, pattern: str) -> str:
    """Find first column whose name fuzzy-matches the pattern (case-insensitive)."""
    pat = re.compile(pattern, re.IGNORECASE)
    for c in df.columns:
        if re.search(pat, c):
            return c
    raise KeyError(f"Column not found for pattern: {pattern}")

# ---------------------------------------------------
# Task blueprint: question text patterns + Bloom L
# ---------------------------------------------------
# We use regex snippets that should match your Google Form question headers.
# Adjust patterns only if your exact headers differ.

TASKS = [
    # name, freq_pattern, diff_pattern, bloom_level
    ("grammar_spelling", r"How often.*grammar.*spelling", r"How difficult.*grammar.*spelling", 1),
    ("rephrase_clarity", r"How often.*rephrase.*clarity", r"How difficult.*rephrasing", 2),
    ("summarize", r"How often.*summarize", r"How difficult.*summarizing", 3),
    ("find_cite_sources", r"How often.*find.*cite.*sources", r"How difficult.*finding.*citing.*sources", 3),  # kept at 3 (mid-level)
    ("brainstorm", r"How often.*brainstorm", r"How difficult.*brainstorm", 4),
    ("outline_structure", r"How often.*generate.*outline|How often.*outlines|How often.*structures", r"How difficult.*outline|How difficult.*structures", 5),
    ("explain_multistep", r"How often.*explain.*multi-step|How often.*multi[- ]?step", r"How difficult.*multi[- ]?step|How difficult.*explaining", 5),
    ("solve_complex", r"How often.*solve.*complex|How often.*original.*problems", r"How difficult.*complex|How difficult.*original.*problems", 6),
]

# Confidence (Q24–Q28), reverse Q27
CONF_PATTERNS = [
    (r"I feel confident using AI tools", False),
    (r"I can figure out how to use new AI features", False),
    (r"I can complete most academic tasks successfully when I use AI", False),
    (r"I often feel unsure about the right way to use AI", True),  # reverse
    (r"I can troubleshoot basic AI issues", False),
]

# Productivity (Q29–Q33), reverse Q32
PROD_PATTERNS = [
    (r"AI helps me finish academic work more efficiently", False),
    (r"Using AI allows me to accomplish more", False),
    (r"AI reduces time spent on low-level steps", False),
    (r"Using AI usually slows me down", True),  # reverse
    (r"With AI, I can focus more on higher-level thinking", False),
]

# Overall use (Q34) & scenario (Q37)
OVERALL_USE_PATTERN = r"Overall, how often do you use any AI tool for schoolwork"
SCENARIO_OUTLINE_PATTERN = r"How likely.*generate the outline"  # 1,500-word outline scenario


# ----------------------------
# Core computations per row
# ----------------------------

def compute_dependency_and_flags(row: pd.Series,
                                 task_cols: Dict[str, Tuple[str, str, int]]) -> Dict[str, any]:
    """Compute task-level & total dependency + over-reliance flags."""
    task_scores = {}
    over_reliant_hits = []

    for name, (freq_col, diff_col, bloom) in task_cols.items():
        freq = to_num_freq(row.get(freq_col))
        diff = to_num_difficulty(row.get(diff_col))

        # task-level dependency = freq * bloom (if freq exists)
        if pd.notna(freq):
            dep = freq * bloom
        else:
            dep = np.nan

        task_scores[f"{name}_freq"] = freq
        task_scores[f"{name}_diff"] = diff
        task_scores[f"{name}_bloom"] = bloom
        task_scores[f"{name}_dep"] = dep

        # Over-reliance rule: freq=5 AND bloom=6 AND diff=5
        if pd.notna(freq) and pd.notna(diff):
            if (freq == 5) and (bloom == 6) and (int(diff) == 5):
                over_reliant_hits.append(name)

    # Total dependency (sum of task deps ignoring NaN)
    dep_cols = [k for k in task_scores.keys() if k.endswith("_dep")]
    total_dependency = pd.Series([task_scores[c] for c in dep_cols], dtype="float").sum(skipna=True)

    return {
        "task_scores": task_scores,
        "total_dependency": total_dependency,
        "over_reliant": len(over_reliant_hits) > 0,
        "over_reliant_tasks": ";".join(over_reliant_hits) if over_reliant_hits else ""
    }

def compute_confidence(row: pd.Series, conf_cols: List[Tuple[str, bool]]) -> float:
    vals = []
    for col, rev in conf_cols:
        v = to_num_likert(row.get(col))
        if pd.notna(v):
            vals.append(6 - v if rev else v)  # reverse-code if needed
    return float(np.mean(vals)) if vals else np.nan

def compute_productivity(row: pd.Series, prod_cols: List[Tuple[str, bool]]) -> float:
    vals = []
    for col, rev in prod_cols:
        v = to_num_likert(row.get(col))
        if pd.notna(v):
            vals.append(6 - v if rev else v)
    return float(np.mean(vals)) if vals else np.nan

def classify_strategic(row: pd.Series, task_cols: Dict[str, Tuple[str, str, int]]) -> str:
    """
    Strategic if BOTH:
      A) High AI on simple & easy tasks: any task with bloom 1–3, diff ≤3, freq ≥4
      B) Low AI on complex & difficult tasks: any task with bloom 4–6, diff ≥4, freq ≤2
    Over-reliant has priority and is handled separately.
    """
    simple_easy_high = False
    complex_diff_low = False

    for name, (freq_col, diff_col, bloom) in task_cols.items():
        freq = to_num_freq(row.get(freq_col))
        diff = to_num_difficulty(row.get(diff_col))
        if pd.isna(freq) or pd.isna(diff):
            continue

        if bloom <= 3 and diff <= 3 and freq >= 4:
            simple_easy_high = True
        if bloom >= 4 and diff >= 4 and freq <= 2:
            complex_diff_low = True

    if simple_easy_high and complex_diff_low:
        return "Strategic"
    return "Regular"

# ----------------------------
# Main pipeline
# ----------------------------

def build_column_index(df: pd.DataFrame):
    # Map each task to actual column headers found in the dataframe.
    task_cols = {}
    for name, freq_pat, diff_pat, bloom in TASKS:
        fcol = col_like(df, freq_pat)
        dcol = col_like(df, diff_pat)
        task_cols[name] = (fcol, dcol, bloom)

    # Confidence & Productivity columns
    conf_cols = []
    for pat, rev in CONF_PATTERNS:
        conf_cols.append((col_like(df, pat), rev))

    prod_cols = []
    for pat, rev in PROD_PATTERNS:
        prod_cols.append((col_like(df, pat), rev))

    # Overall & scenario (optional; won't error if missing—wrapped with try)
    try:
        overall_col = col_like(df, OVERALL_USE_PATTERN)
    except KeyError:
        overall_col = None

    try:
        scenario_col = col_like(df, SCENARIO_OUTLINE_PATTERN)
    except KeyError:
        scenario_col = None

    return task_cols, conf_cols, prod_cols, overall_col, scenario_col

def score_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    task_cols, conf_cols, prod_cols, overall_col, scenario_col = build_column_index(df)

    out_rows = []
    for _, row in df.iterrows():
        dep = compute_dependency_and_flags(row, task_cols)
        conf = compute_confidence(row, conf_cols)
        prod = compute_productivity(row, prod_cols)

        overall_use = pd.to_numeric(row.get(overall_col), errors="coerce") if overall_col else np.nan
        scenario_outline = pd.to_numeric(row.get(scenario_col), errors="coerce") if scenario_col else np.nan

        # Classification
        if dep["over_reliant"]:
            profile = "Over-reliant"
        else:
            profile = classify_strategic(row, task_cols)

        flat = {
            "total_dependency": dep["total_dependency"],
            "profile": profile,
            "over_reliant": dep["over_reliant"],
            "over_reliant_tasks": dep["over_reliant_tasks"],
            "confidence_mean": conf,
            "productivity_mean": prod,
            "overall_ai_use": overall_use,
            "scenario_outline_likelihood": scenario_outline
        }
        flat.update(dep["task_scores"])
        out_rows.append(flat)

    scored = pd.DataFrame(out_rows)

    # P75 tagging
    p75 = np.nanpercentile(scored["total_dependency"].values.astype(float), 75)
    scored["p75_threshold"] = p75
    scored["high_dependency_p75"] = (scored["total_dependency"] >= p75).astype(int)

    return scored

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Score AI-nalysis survey CSV export and tag P75.")
    parser.add_argument("--input", "-i", required=True, help="Path to Google Forms CSV export")
    parser.add_argument("--output", "-o", default="scored_output.csv", help="Path to write scored CSV")
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    scored = score_dataframe(df)

    out = pd.concat([df.reset_index(drop=True), scored.reset_index(drop=True)], axis=1)
    out.to_csv(args.output, index=False)
    print(f"Done. Rows: {len(out)} | P75(total_dependency) = {out['p75_threshold'].iloc[0]:.2f}")
    print(f"Output -> {args.output}")

if __name__ == "__main__":
    main()

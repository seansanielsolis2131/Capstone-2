import argparse
import os
import math
import numpy as np
import pandas as pd

def norm_text(x):
    if pd.isna(x):
        return ""
    return str(x).strip().lower()

def find_col(df, startswith_text):
    """Fuzzy find a column by its starting text (case/space tolerant)."""
    sw = norm_text(startswith_text)
    for c in df.columns:
        if norm_text(c).startswith(sw):
            return c
    return None

def map_freq(val):
    FREQ_MAP = {"never":1, "occasionally":2, "sometimes":3, "often":4, "always":5}
    if isinstance(val, (int, float)) and not pd.isna(val):
        v = int(val)
        return min(max(v,1),5)
    key = norm_text(val)
    return FREQ_MAP.get(key, np.nan)

def map_likert(val):
    LIKERT_MAP = {
        "strongly disagree":1, "disagree":2, "neutral":3, "agree":4, "strongly agree":5
    }
    if isinstance(val, (int, float)) and not pd.isna(val):
        v = int(val)
        return min(max(v,1),5)
    key = norm_text(val)
    return LIKERT_MAP.get(key, np.nan)

def reverse_code(x):
    if pd.isna(x):
        return np.nan
    return 6 - int(x) 

def safe_mean_list(vals):
    clean = [v for v in vals if not pd.isna(v)]
    return float(np.mean(clean)) if clean else np.nan


# ========= Config =========

TASKS = ["grammar","rephrase","summarize","sources","brainstorm","outline","multistep","complex"]

BLOOM = {
    "grammar": 1,
    "rephrase": 2,
    "summarize": 2,
    "sources": 3,
    "brainstorm": 3,
    "outline": 3,
    "multistep": 5,
    "complex": 6,
}

# Reverse-coded items
REVERSE_CONF = {"conf_q4": True}
REVERSE_PROD = {"prod_q4": True}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path", help="Path to raw CSV (Google Form responses).")
    ap.add_argument("--out", default="out", help="Output folder (default: out)")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    # Load CSV
    df = pd.read_csv(args.csv_path)

    # Meta
    META_COLS = {
        "school_type": find_col(df, "School Type"),
        "program": find_col(df, "Program/Course"),
        "discipline": find_col(df, "Discipline"),
        "year_level": find_col(df, "Year Level"),
        "gwa_range": find_col(df, "What is your current General Weighted Average"),
    }

    # Frequency / Difficulty per task
    FREQ_COLS = {
        "grammar":    find_col(df, "How often do you use AI to correct grammar and spelling"),
        "rephrase":   find_col(df, "How often do you use AI to rephrase sentences"),
        "summarize":  find_col(df, "How often do you use AI to summarize"),
        "sources":    find_col(df, "How often do you use AI to find or cite sources"),
        "brainstorm": find_col(df, "How often do you use AI to brainstorm ideas"),
        "outline":    find_col(df, "How often do you use AI to generate outlines"),
        "multistep":  find_col(df, "How often do you use AI to help you explain multi-step solutions"),
        "complex":    find_col(df, "How often do you use AI to solve complex or original problems"),
    }

    DIFF_COLS = {
        "grammar":    find_col(df, "How difficult is correcting grammar and spelling"),
        "rephrase":   find_col(df, "How difficult is rephrasing sentences"),
        "summarize":  find_col(df, "How difficult is summarizing"),
        "sources":    find_col(df, "How difficult is finding and citing sources"),
        "brainstorm": find_col(df, "How difficult is brainstorming ideas"),
        "outline":    find_col(df, "How difficult is making outlines or structures"),
        "multistep":  find_col(df, "How difficult is explaining multi-step solutions"),
        "complex":    find_col(df, "How difficult are complex or original problems"),
    }

    CONF_HEADERS = [
        "I feel confident using AI tools to support my schoolwork.",
        "I can figure out how to use new AI features on my own.",
        "I can complete most academic tasks successfully when I use AI.",
        "I often feel unsure about the right way to use AI for my tasks.",
        "I can troubleshoot basic AI issues (prompts, settings, exporting) without help.",
    ]
    CONF_ACTUAL = [find_col(df, h) for h in CONF_HEADERS]
    CONF_SHORT = ["conf_q1","conf_q2","conf_q3","conf_q4","conf_q5"]
    conf_map = dict(zip(CONF_SHORT, CONF_ACTUAL))

    PROD_HEADERS = [
        "AI helps me finish academic work more efficiently.",
        "Using AI allows me to accomplish more in the same amount of time.",
        "AI reduces time spent on low-level steps",
        "Using AI usually slows me down.",
        "With AI, I can focus more on higher-level thinking.",
    ]
    PROD_ACTUAL = [find_col(df, h) for h in PROD_HEADERS]
    PROD_SHORT = ["prod_q1","prod_q2","prod_q3","prod_q4","prod_q5"]
    prod_map = dict(zip(PROD_SHORT, PROD_ACTUAL))

    # Crosscheck
    CROSS_COLS = {
        "overall_freq":         find_col(df, "Overall, how often do you use any AI tool"),
        "task_straightforward": find_col(df, "Using AI for class tasks feels straightforward to me."),
        "study_effective":      find_col(df, "Overall, AI makes my study time more effective"),
        "outline_likelihood":   find_col(df, "You must draft a 1,500-word essay"),
    }

    # ---- Normalize Discipline ----
    disc_col = META_COLS.get("discipline")
    if disc_col and disc_col in df.columns:
        def map_discipline(val):
            txt = norm_text(val)
            if txt.startswith("stem"):
                return "STEM"
            if txt.startswith("non-stem"):
                return "Non-STEM"
            return val
        df[disc_col] = df[disc_col].apply(map_discipline)

    # ---- Map Frequency text → numbers (1–5) ----
    for t in TASKS:
        fcol = FREQ_COLS.get(t)
        if fcol and fcol in df.columns:
            df[fcol] = df[fcol].apply(map_freq)

    # ---- Difficulty to numeric (1–5) ----
    for t in TASKS:
        dcol = DIFF_COLS.get(t)
        if dcol and dcol in df.columns:
            df[dcol] = pd.to_numeric(df[dcol], errors="coerce")

    # ---- Confidence (map + reverse) ----
    for short, col in conf_map.items():
        if col and col in df.columns:
            df[short] = df[col].apply(map_likert)
        else:
            df[short] = np.nan
        if short in REVERSE_CONF:
            df[short] = df[short].apply(reverse_code)
    CONF_COLS = list(conf_map.keys())

    # ---- Productivity (map + reverse) ----
    for short, col in prod_map.items():
        if col and col in df.columns:
            df[short] = df[col].apply(map_likert)
        else:
            df[short] = np.nan
        if short in REVERSE_PROD:
            df[short] = df[short].apply(reverse_code)
    PROD_COLS = list(prod_map.keys())

    # ---- Compute dependency totals ----
    totals, pcts = [], []
    total_max = sum(5 * BLOOM[t] for t in TASKS) 
    for _, row in df.iterrows():
        total = 0
        for t in TASKS:
            fcol = FREQ_COLS.get(t)
            if fcol and fcol in df.columns and not pd.isna(row.get(fcol)):
                total += int(row[fcol]) * BLOOM[t]
        totals.append(total)
        pcts.append(round((total/total_max)*100, 2) if total_max else np.nan)

    df["total_dependency"] = totals
    df["total_dependency_pct"] = pcts

    # ---- High-dependency threshold = 75th percentile of actual totals ----
    dep_vals = pd.Series([v for v in totals if not pd.isna(v)])
    high_dep_threshold = float(np.percentile(dep_vals, 75)) if len(dep_vals) > 0 else np.nan
    df["high_dependency"] = df["total_dependency"] >= high_dep_threshold if not math.isnan(high_dep_threshold) else False

    # ---- Over-reliance flag: F=5 & Bloom=6 & Difficulty=5 on complex task ----
    f_complex = FREQ_COLS["complex"]
    d_complex = DIFF_COLS["complex"]
    def over_reliance_row(row):
        f = row.get(f_complex, np.nan)
        d = row.get(d_complex, np.nan)
        return (not pd.isna(f) and not pd.isna(d) and int(f)==5 and int(d)==5)
    df["over_reliance_flag"] = df.apply(over_reliance_row, axis=1)

    # ---- Confidence & Productivity means ----
    df["confidence_mean"] = df[CONF_COLS].apply(lambda r: safe_mean_list(r.values), axis=1)
    df["productivity_mean"] = df[PROD_COLS].apply(lambda r: safe_mean_list(r.values), axis=1)

    # ---- clusters ----
    def assign_cluster(row):
        if row["over_reliance_flag"]:
            return "Over-reliant"
        
        gc = FREQ_COLS["grammar"]; cc = FREQ_COLS["complex"]
        g = row.get(gc, np.nan); c = row.get(cc, np.nan)
        if not pd.isna(g) and not pd.isna(c):
            if int(c) <= 2 and int(g) >= 3:
                return "Strategic"
        return "Regular"
    df["cluster"] = df.apply(assign_cluster, axis=1)

    # ---- Export row-level cleaned data ----
    cleaned_path = os.path.join(args.out, "cleaned_with_scores.csv")
    df.to_csv(cleaned_path, index=False, encoding="utf-8-sig")

    group_cols = [col for col in [
        META_COLS.get("school_type"),
        META_COLS.get("discipline"),
        META_COLS.get("year_level"),
        META_COLS.get("gwa_range"),
    ] if col in df.columns and col is not None]

    summary_frames = []

    if group_cols:
        agg = {
            "total_dependency": ["mean"],
            "confidence_mean": ["mean"],
            "productivity_mean": ["mean"],
            "over_reliance_flag": ["mean"],
            "high_dependency": ["mean"],
        }
        g = df.groupby(group_cols).agg(agg)
        g.columns = ["_".join(c).strip() for c in g.columns.values]
        summary_frames.append(g.reset_index())

    cluster_counts = df["cluster"].value_counts(dropna=False).rename_axis("cluster").reset_index(name="count")
    summary_frames.append(cluster_counts)

    disc_col = META_COLS.get("discipline")
    if disc_col and disc_col in df.columns:
        piv = pd.pivot_table(
            df,
            index=disc_col,
            values=["total_dependency","confidence_mean","productivity_mean","over_reliance_flag","high_dependency"],
            aggfunc={"total_dependency":"mean","confidence_mean":"mean",
                     "productivity_mean":"mean","over_reliance_flag":"mean","high_dependency":"mean"}
        ).reset_index()
        summary_frames.append(piv)

    summary = pd.concat(summary_frames, axis=0, ignore_index=True, sort=False)
    summary_path = os.path.join(args.out, "chapter4_summary.csv")
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

    # Console info
    print("\n==== Processing done ====")
    print(f"Rows processed: {len(df)}")
    print(f"75th percentile threshold (Total Dependency): {high_dep_threshold if not math.isnan(high_dep_threshold) else 'NA'}")
    print(f"Outputs:\n - {cleaned_path}\n - {summary_path}\n")


if __name__ == "__main__":
    main()

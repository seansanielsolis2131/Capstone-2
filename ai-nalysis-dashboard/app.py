from flask import Flask, render_template, jsonify, request
import pandas as pd
import numpy as np
import os
import re

# --- JSON sanitizer: replace NaN/Inf with None so JSON is valid ---
import math

def _json_sanitize(x):
    if isinstance(x, float):
        if math.isnan(x) or math.isinf(x):
            return None
        return x
    if isinstance(x, dict):
        return {k: _json_sanitize(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_json_sanitize(v) for v in x]
    return x


def normalize_discipline(x: str):
    if pd.isna(x):
        return np.nan
    s = str(x).strip().lower()
    s = re.sub(r"\s+", " ", s)
    if s.startswith("non-stem") or s.startswith("non stem") or "non-stem" in s:
        return "Non-STEM"
    if s.startswith("stem") or " stem" in s or s == "stem":
        return "STEM"
    return np.nan

app = Flask(__name__)

DATA_PATH = os.path.join("data", "scored_with_clusters.csv")

def load_data():
    df = pd.read_csv(DATA_PATH)
    disc_col = next((c for c in df.columns if "Discipline" in c or "discipline" in c), None)
    if disc_col:
        df["Discipline_norm"] = df[disc_col].apply(normalize_discipline)
    else:
        df["Discipline_norm"] = np.nan
    return df

df = load_data()

def apply_filters(df):
    stem = request.args.get("stem")
    school_type = request.args.get("school_type")
    year = request.args.get("year")
    p75_only = request.args.get("p75_only")
    school_col = next((c for c in df.columns if "School Type" in c), None)
    year_col = next((c for c in df.columns if "Year Level" in c), None)
    if stem:
        df = df[df["Discipline_norm"] == stem]
    if school_type and school_col in df.columns:
        df = df[df[school_col].str.contains(school_type, case=False, na=False)]
    if year and year_col in df.columns:
        df = df[df[year_col].astype(str) == str(year)]
    if p75_only == "1" and "high_dependency_p75" in df.columns:
        df = df[df["high_dependency_p75"] == 1]
    return df

# ---- REPLACE your existing compute_outcome_mapping with this ----
def compute_outcome_mapping(df: pd.DataFrame):
    import numpy as np
    import pandas as pd
    import re
    import math

    d = df.copy()

    # 1) Cluster/profile prep
    if 'cluster_label' not in d.columns:
        raise ValueError("Missing 'cluster_label' in data.")
    d['cluster_label'] = pd.to_numeric(d['cluster_label'], errors='coerce')
    label_map = {0: "Regular", 1: "Over-reliant", 2: "Strategic"}
    d['profile'] = d['cluster_label'].map(label_map)

    # 2) Ensure total_dependency exists
    if 'total_dependency' not in d.columns:
        dep_cols = [c for c in d.columns if c.endswith('_dep')]
        if dep_cols:
            for c in dep_cols:
                d[c] = pd.to_numeric(d[c], errors='coerce')
            d['total_dependency'] = d[dep_cols].sum(axis=1)
        else:
            d['total_dependency'] = np.nan

    # 3) Numeric coercions
    for col in ['confidence_mean', 'productivity_mean', 'total_dependency']:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors='coerce')

    # 4) high_dependency_p75 normalization
    if 'high_dependency_p75' in d.columns:
        hd = d['high_dependency_p75']
        if hd.dtype == bool:
            d['high_dependency_p75'] = hd.astype(int)
        else:
            d['high_dependency_p75'] = (
                hd.astype(str).str.strip().str.lower()
                  .map({'1':1,'true':1,'yes':1,'0':0,'false':0,'no':0})
                  .fillna(pd.to_numeric(hd, errors='coerce'))
            ).fillna(0).astype(int)
    else:
        d['high_dependency_p75'] = 0

    # 5) GWA parsing
    #    - keep a clean bucket text (e.g., "1.51-1.75")
    #    - compute midpoint number for stats (but we'll chart the mode bucket)
    gwa_col = next((c for c in d.columns if "gwa" in c.lower()), None)

    def _normalize_dashes(s: str) -> str:
        # replace any dash-like char with simple hyphen
        return re.sub(r'[–—−‒]', '-', s)

    def _bucket_str(v):
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        s = str(v).strip()
        s = _normalize_dashes(s).replace(' to ', '-')
        nums = re.findall(r'\d+(?:\.\d+)?', s)
        if len(nums) >= 2:
            return f"{nums[0]}-{nums[1]}"
        if len(nums) == 1:
            # single value given; treat as a "bucket" with itself
            return nums[0]
        return None

    def _bucket_mid(v):
        """Return midpoint of bucket; fallback to single number; else NaN."""
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return float('nan')
        s = str(v).strip()
        s = _normalize_dashes(s).replace(' to ', '-')
        m = re.match(r'^\s*([0-9]+(?:\.[0-9]+)?)\s*-\s*([0-9]+(?:\.[0-9]+)?)\s*$', s)
        if m:
            lo, hi = float(m.group(1)), float(m.group(2))
            return round((lo + hi) / 2.0, 2)
        nums = re.findall(r'\d+(?:\.\d+)?', s)
        if len(nums) == 1:
            return float(nums[0])
        return float('nan')

    if gwa_col:
        d['gwa_bucket'] = d[gwa_col].apply(_bucket_str)
        d['gwa_num'] = d[gwa_col].apply(_bucket_mid)
    else:
        d['gwa_bucket'] = np.nan
        d['gwa_num'] = np.nan

    d['gwa_num'] = pd.to_numeric(d['gwa_num'], errors='coerce')
    d.loc[(d['gwa_num'] < 1) | (d['gwa_num'] > 5), 'gwa_num'] = np.nan

    # 6) Group snapshot (per profile)
    g = d.groupby('profile', dropna=False)
    snapshot = g.agg(
        mean_confidence=('confidence_mean', 'mean') if 'confidence_mean' in d.columns else ('cluster_label','size'),
        mean_productivity=('productivity_mean', 'mean') if 'productivity_mean' in d.columns else ('cluster_label','size'),
        pct_high_dependency=('high_dependency_p75', lambda s: float(np.mean(s)) * 100 if s.size else np.nan),
        median_gwa=('gwa_num', 'median')
    ).reset_index()

    # 7) Add mode GWA bucket + percent share per profile
    vc = d[['profile','gwa_bucket']].dropna(subset=['profile'])
    if not vc.empty:
        # exclude null buckets when computing mode/percent
        vc_non = vc.dropna(subset=['gwa_bucket'])
        if not vc_non.empty:
            counts = vc_non.value_counts().rename('count').reset_index()  # cols: profile, gwa_bucket, count
            # pick top bucket per profile
            idx = counts.groupby('profile')['count'].idxmax()
            mode_df = counts.loc[idx].copy()
            totals = vc_non.groupby('profile')['gwa_bucket'].count()  # total non-null per profile
            mode_df['mode_gwa_bucket'] = mode_df['gwa_bucket']
            mode_df['mode_gwa_pct'] = mode_df.apply(
                lambda r: float(r['count']) / float(totals.loc[r['profile']]) * 100.0, axis=1
            )
            mode_df = mode_df[['profile','mode_gwa_bucket','mode_gwa_pct']]
            snapshot = snapshot.merge(mode_df, on='profile', how='left')
        else:
            snapshot['mode_gwa_bucket'] = None
            snapshot['mode_gwa_pct'] = np.nan
    else:
        snapshot['mode_gwa_bucket'] = None
        snapshot['mode_gwa_pct'] = np.nan

    # rounding
    for c in ['mean_confidence','mean_productivity','pct_high_dependency','median_gwa','mode_gwa_pct']:
        if c in snapshot.columns:
            snapshot[c] = snapshot[c].astype(float).round(2)

    # 8) Correlation matrix (only for available numeric fields)
    corr_fields = [c for c in ['total_dependency','confidence_mean','productivity_mean','gwa_num'] if c in d.columns]
    corr_matrix = None
    if len(corr_fields) >= 2:
        corr_df = d[corr_fields].corr().round(2)
        corr_matrix = {'fields': corr_df.columns.tolist(), 'matrix': corr_df.values.tolist()}

    # 9) Scatter points (unchanged)
    def pack_points(x_col, y_col):
        if x_col in d.columns and y_col in d.columns:
            sub = d[['profile', x_col, y_col]].dropna()
            return [
                {'x': float(rx), 'y': float(ry), 'profile': p}
                for p, rx, ry in sub[['profile', x_col, y_col]].itertuples(index=False, name=None)
            ]
        return []

    pts_dep_conf = pack_points('total_dependency', 'confidence_mean')
    pts_conf_prod = pack_points('confidence_mean', 'productivity_mean')

    return {
        'snapshot': snapshot.to_dict(orient='records'),
        'correlation': corr_matrix,
        'points': {'dep_vs_conf': pts_dep_conf, 'conf_vs_prod': pts_conf_prod}
    }
# ---- END replacement ----


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/summary")
def summary():
    df = apply_filters(load_data())
    total_students = int(len(df))
    high_dep = int(df["high_dependency_p75"].sum()) if "high_dependency_p75" in df else 0
    p75 = float(df["p75_threshold"].iloc[0]) if "p75_threshold" in df and len(df) else None
    clusters = {}
    if "cluster_label" in df.columns:
        counts = df["cluster_label"].value_counts(dropna=False)
        for k, v in counts.items():
            key = "NaN" if pd.isna(k) else int(k)
            clusters[str(key)] = int(v)
    payload = {
        "total_students": total_students,
        "high_dependency": high_dep,
        "p75_threshold": p75,
        "clusters": clusters
    }
    return jsonify(payload)

@app.route("/api/cluster_counts")
def cluster_counts():
    df = apply_filters(load_data())
    result = []
    if "cluster_label" in df.columns:
        counts = df["cluster_label"].value_counts(dropna=False).sort_index()
        for label, cnt in counts.items():
            result.append({
                "cluster": "NaN" if pd.isna(label) else int(label),
                "count": int(cnt)
            })
    return jsonify({"data": result})

@app.route("/api/distribution")
def distribution():
    df = apply_filters(load_data())
    values = df["total_dependency"].dropna().astype(float).values if "total_dependency" in df else np.array([])
    if values.size == 0:
        return jsonify({"bins": [], "counts": [], "p75": None})
    bins = 15
    hist_counts, bin_edges = np.histogram(values, bins=bins)
    bin_centers = ((bin_edges[:-1] + bin_edges[1:]) / 2.0).tolist()
    p75 = float(np.percentile(values, 75))
    return jsonify({
        "bins": bin_centers,
        "counts": hist_counts.tolist(),
        "p75": p75
    })

@app.route("/api/scatter")
def scatter():
    df = apply_filters(load_data())
    needed = {"total_dependency", "productivity_mean", "cluster_label"}
    if not needed.issubset(set(df.columns)):
        return jsonify({"points": []})
    sub = df[list(needed)].dropna()
    if len(sub) > 200:
        sub = sub.sample(n=200, random_state=42)
    def norm_cluster(v):
        if pd.isna(v):
            return "NaN"
        try:
            return int(v)
        except Exception:
            return str(v)
    points = []
    for _, r in sub.iterrows():
        points.append({
            "x": float(r["total_dependency"]),
            "y": float(r["productivity_mean"]),
            "cluster": norm_cluster(r["cluster_label"])
        })
    return jsonify({"points": points})

@app.route("/api/profile_mix")
def profile_mix():
    df = apply_filters(load_data())
    if "profile" not in df.columns or "Discipline_norm" not in df.columns:
        return jsonify({"groups": []})
    grouped = df.groupby(["Discipline_norm", "profile"]).size().reset_index(name="count")
    results = []
    for disc in grouped["Discipline_norm"].unique():
        subset = grouped[grouped["Discipline_norm"] == disc]
        total = subset["count"].sum()
        for _, row in subset.iterrows():
            results.append({
                "discipline": row["Discipline_norm"],
                "profile": row["profile"],
                "count": int(row["count"]),
                "percent": (row["count"] / total * 100) if total > 0 else 0
            })
    return jsonify({"groups": results})

@app.route("/api/year_breakdown")
def year_breakdown():
    df = apply_filters(load_data())
    if "Year Level" not in df.columns or "total_dependency" not in df.columns:
        return jsonify({"groups": []})
    grouped = df.groupby("Year Level")["total_dependency"].mean().reset_index()
    results = []
    for _, row in grouped.iterrows():
        results.append({
            "year": str(row["Year Level"]),
            "avg_dependency": float(row["total_dependency"])
        })
    return jsonify({"groups": results})

@app.route("/api/confidence_distribution")
def confidence_distribution():
    df = apply_filters(load_data())
    if "confidence_mean" not in df.columns:
        return jsonify({"bins": [], "counts": []})
    values = df["confidence_mean"].dropna().astype(float).values
    if values.size == 0:
        return jsonify({"bins": [], "counts": []})
    hist_counts, bin_edges = np.histogram(values, bins=10, range=(1, 5))
    bin_centers = ((bin_edges[:-1] + bin_edges[1:]) / 2.0).tolist()
    return jsonify({
        "bins": bin_centers,
        "counts": hist_counts.tolist()
    })

@app.route("/api/productivity_distribution")
def productivity_distribution():
    df = apply_filters(load_data())
    if "productivity_mean" not in df.columns:
        return jsonify({"bins": [], "counts": []})
    values = df["productivity_mean"].dropna().astype(float).values
    if values.size == 0:
        return jsonify({"bins": [], "counts": []})
    hist_counts, bin_edges = np.histogram(values, bins=10, range=(1, 5))
    bin_centers = ((bin_edges[:-1] + bin_edges[1:]) / 2.0).tolist()
    return jsonify({
        "bins": bin_centers,
        "counts": hist_counts.tolist()
    })

@app.route("/api/confidence_by_cluster")
def confidence_by_cluster():
    df = apply_filters(load_data())
    if "confidence_mean" not in df.columns or "cluster_label" not in df.columns:
        return jsonify({"groups": []})
    grouped = df.groupby("cluster_label")["confidence_mean"].mean().reset_index()
    results = []
    for _, row in grouped.iterrows():
        cluster = "NaN" if pd.isna(row["cluster_label"]) else str(int(row["cluster_label"]))
        results.append({
            "cluster": cluster,
            "avg_confidence": float(row["confidence_mean"])
        })
    return jsonify({"groups": results})

@app.route("/api/productivity_by_cluster")
def productivity_by_cluster():
    df = apply_filters(load_data())
    if "productivity_mean" not in df.columns or "cluster_label" not in df.columns:
        return jsonify({"groups": []})
    grouped = df.groupby("cluster_label")["productivity_mean"].mean().reset_index()
    results = []
    for _, row in grouped.iterrows():
        cluster = "NaN" if pd.isna(row["cluster_label"]) else str(int(row["cluster_label"]))
        results.append({
            "cluster": cluster,
            "avg_productivity": float(row["productivity_mean"])
        })
    return jsonify({"groups": results})

@app.route("/api/confidence_by_discipline")
def confidence_by_discipline():
    df = apply_filters(load_data())
    if "confidence_mean" not in df.columns or "Discipline_norm" not in df.columns:
        return jsonify({"groups": []})
    grouped = df.groupby("Discipline_norm")["confidence_mean"].mean().reset_index()
    results = []
    for _, row in grouped.iterrows():
        results.append({
            "discipline": row["Discipline_norm"],
            "avg_confidence": float(row["confidence_mean"])
        })
    return jsonify({"groups": results})

@app.route("/api/productivity_by_discipline")
def productivity_by_discipline():
    df = apply_filters(load_data())
    if "productivity_mean" not in df.columns or "Discipline_norm" not in df.columns:
        return jsonify({"groups": []})
    grouped = df.groupby("Discipline_norm")["productivity_mean"].mean().reset_index()
    results = []
    for _, row in grouped.iterrows():
        results.append({
            "discipline": row["Discipline_norm"],
            "avg_productivity": float(row["productivity_mean"])
        })
    return jsonify({"groups": results})

# ---- ADD THIS NEW ROUTE NEAR YOUR OTHER /api/... ROUTES ----
@app.route('/api/outcome-mapping')
def api_outcome_mapping():
    try:
        dff = apply_filters(load_data())   # same filter path as other routes
        data = compute_outcome_mapping(dff)

        # 🔒 make JSON-safe (convert NaN/Inf -> None)
        data = _json_sanitize(data)

        print("OM snapshot rows:", len(data['snapshot']),
              "dep_conf pts:", len(data['points']['dep_vs_conf']),
              "conf_prod pts:", len(data['points']['conf_vs_prod']))
        return jsonify({'ok': True, 'data': data})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 400



@app.route("/api/cluster_centroids")
def cluster_centroids():
    df = apply_filters(load_data())
    needed = {"cluster_label", "total_dependency", "confidence_mean", "productivity_mean"}
    if not needed.issubset(set(df.columns)):
        return jsonify({"clusters": []})
    grouped = df.groupby("cluster_label")[["total_dependency", "confidence_mean", "productivity_mean"]].mean().reset_index()
    results = []
    for _, row in grouped.iterrows():
        cluster = "NaN" if pd.isna(row["cluster_label"]) else str(int(row["cluster_label"]))
        results.append({
            "cluster": cluster,
            "dependency": float(row["total_dependency"]),
            "confidence": float(row["confidence_mean"]),
            "productivity": float(row["productivity_mean"])
        })
    return jsonify({"clusters": results})

if __name__ == "__main__":
    app.run(debug=True)

print(app.url_map)


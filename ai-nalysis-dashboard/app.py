from flask import Flask, render_template, jsonify, request
import pandas as pd
import numpy as np
import os
import re

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
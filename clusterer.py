import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
import argparse

def run_clustering(input_path: str, output_path: str, n_clusters: int = 3):
    df = pd.read_csv(input_path)

    features = ["total_dependency", "confidence_mean", "productivity_mean"]

    X = df[features].dropna()

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)

    df.loc[X.index, "cluster_label"] = labels

    centroids_scaled = kmeans.cluster_centers_
    centroids = scaler.inverse_transform(centroids_scaled)
    for i, center in enumerate(centroids):
        print(f"Cluster {i} centroid:", dict(zip(features, center)))

    df.to_csv(output_path, index=False)
    print(f"Done. Clustered dataset saved to {output_path}")
    print("Cluster counts:\n", df["cluster_label"].value_counts(dropna=False))


def main():
    parser = argparse.ArgumentParser(description="Run K-Means clustering on scored survey data.")
    parser.add_argument("--input", "-i", required=True, help="Path to scored_output.csv from scorer.py")
    parser.add_argument("--output", "-o", default="scored_with_clusters.csv", help="Path to write clustered CSV")
    parser.add_argument("--clusters", "-k", type=int, default=3, help="Number of clusters (default=3)")
    args = parser.parse_args()

    run_clustering(args.input, args.output, args.clusters)

if __name__ == "__main__":
    main()

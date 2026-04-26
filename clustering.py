from typing import Tuple

import folium
import pandas as pd
import plotly.express as px
from folium.plugins import MarkerCluster
from sklearn.cluster import DBSCAN, KMeans

from utils import plotly_palette


def _coords(df: pd.DataFrame) -> pd.DataFrame:
    return df[["Latitude", "Longitude"]].copy()


def run_kmeans(df: pd.DataFrame, n_clusters: int = 4) -> Tuple[pd.DataFrame, KMeans]:
    if df.empty:
        raise ValueError("Cannot run clustering on an empty dataset.")
    if len(df) < n_clusters:
        raise ValueError("Number of clusters cannot exceed number of rows.")

    model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = model.fit_predict(_coords(df))
    result = df.copy()
    result["kmeans_cluster"] = labels
    return result, model


def run_dbscan(df: pd.DataFrame, eps: float = 0.01, min_samples: int = 5) -> Tuple[pd.DataFrame, DBSCAN]:
    if df.empty:
        raise ValueError("Cannot run clustering on an empty dataset.")

    model = DBSCAN(eps=eps, min_samples=min_samples)
    labels = model.fit_predict(_coords(df))
    result = df.copy()
    result["dbscan_cluster"] = labels
    return result, model


def plot_cluster_scatter(df: pd.DataFrame, label_col: str, title: str):
    clusters = sorted(df[label_col].astype(int).unique().tolist())
    ordered = [-1] + [c for c in clusters if c != -1] if -1 in clusters else clusters

    colors = plotly_palette(len(ordered))
    color_map = {str(cluster): color for cluster, color in zip(ordered, colors)}
    if "-1" in color_map:
        color_map["-1"] = "#000000"

    plot_df = df.copy()
    plot_df[f"{label_col}_str"] = plot_df[label_col].astype(int).astype(str)

    fig = px.scatter(
        plot_df,
        x="Longitude",
        y="Latitude",
        color=f"{label_col}_str",
        color_discrete_map=color_map,
        hover_data=["Crime ID", "Month", "Location", "Outcome type"],
        title=title,
    )
    fig.update_layout(template="plotly_dark", height=540, legend_title_text="Cluster")
    return fig


def create_cluster_map(df: pd.DataFrame, label_col: str) -> folium.Map:
    if df.empty:
        return folium.Map(location=[20.0, 0.0], zoom_start=2, tiles="CartoDB dark_matter")

    center = [df["Latitude"].mean(), df["Longitude"].mean()]
    fmap = folium.Map(location=center, zoom_start=11, tiles="CartoDB dark_matter")
    marker_cluster = MarkerCluster(name="Clustered Points").add_to(fmap)

    labels = sorted(df[label_col].astype(int).unique().tolist())
    palette = plotly_palette(len(labels))
    color_map = {label: palette[idx] for idx, label in enumerate(labels)}
    if -1 in color_map:
        color_map[-1] = "#111111"

    for _, row in df.iterrows():
        label = int(row[label_col])
        folium.CircleMarker(
            location=[row["Latitude"], row["Longitude"]],
            radius=7 if label != -1 else 4,
            color=color_map[label],
            fill=True,
            fill_opacity=0.8,
            popup=(
                f"Crime ID: {row['Crime ID']}<br>"
                f"Cluster: {label}<br>"
                f"Outcome: {row['Outcome type']}"
            ),
        ).add_to(marker_cluster)

    folium.LayerControl().add_to(fmap)
    return fmap

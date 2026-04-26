from typing import Dict

import pandas as pd
import plotly.express as px


def build_analytics(df: pd.DataFrame) -> Dict[str, object]:
    if df.empty:
        return {}

    monthly = (
        df.groupby("Month", as_index=False)
        .size()
        .rename(columns={"size": "Crime Count"})
        .sort_values("Month")
    )

    outcomes = (
        df.groupby("Outcome type", as_index=False)
        .size()
        .rename(columns={"size": "Crime Count"})
        .sort_values("Crime Count", ascending=False)
    )

    locations = (
        df.groupby("Location", as_index=False)
        .size()
        .rename(columns={"size": "Crime Count"})
        .sort_values("Crime Count", ascending=False)
        .head(15)
    )

    top_lsoa = (
        df.groupby(["LSOA code", "LSOA name"], as_index=False)
        .size()
        .rename(columns={"size": "Crime Count"})
        .sort_values("Crime Count", ascending=False)
        .head(10)
    )

    fig_monthly = px.line(
        monthly,
        x="Month",
        y="Crime Count",
        markers=True,
        title="Monthly Crime Trend",
        template="plotly_dark",
    )

    fig_outcomes = px.bar(
        outcomes,
        x="Outcome type",
        y="Crime Count",
        title="Crimes by Outcome Type",
        template="plotly_dark",
    )

    fig_locations = px.bar(
        locations,
        x="Crime Count",
        y="Location",
        orientation="h",
        title="Top Crime Locations",
        template="plotly_dark",
    )

    fig_density = px.density_heatmap(
        df,
        x="Longitude",
        y="Latitude",
        nbinsx=30,
        nbinsy=30,
        title="Crime Density Heatmap (Longitude vs Latitude)",
        template="plotly_dark",
    )

    fig_top_lsoa = px.bar(
        top_lsoa,
        x="Crime Count",
        y="LSOA name",
        orientation="h",
        title="Top LSOA Crime Areas",
        template="plotly_dark",
    )

    for fig in [fig_monthly, fig_outcomes, fig_locations, fig_density, fig_top_lsoa]:
        fig.update_layout(height=420, margin=dict(l=20, r=20, t=60, b=20))

    return {
        "monthly": fig_monthly,
        "outcomes": fig_outcomes,
        "locations": fig_locations,
        "density": fig_density,
        "top_lsoa": fig_top_lsoa,
        "top_lsoa_table": top_lsoa,
    }

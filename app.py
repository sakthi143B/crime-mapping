import os

import streamlit as st
from streamlit_folium import st_folium

from analytics import build_analytics
from clustering import create_cluster_map, plot_cluster_scatter, run_dbscan, run_kmeans
from utils import (
    REQUIRED_COLUMNS,
    apply_filters,
    create_crime_map,
    create_point_options,
    create_road_route_map,
    create_route_map,
    load_crime_data,
    to_csv_bytes,
)

st.set_page_config(page_title="Crime Mapping and Clustering Analytics System", layout="wide")

APP_USERNAME = "admin"
APP_PASSWORD = "crime@123"


def load_css(path: str) -> None:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def card(title: str) -> None:
    st.markdown(f"<div class='card'><h3>{title}</h3></div>", unsafe_allow_html=True)


def render_map(fmap, height: int, key: str) -> None:
    try:
        st_folium(fmap, use_container_width=True, height=height, key=key)
    except Exception as exc:
        if not st.session_state.get("map_fallback_warned", False):
            st.warning(
                "Map rendered in compatibility mode because of a streamlit-folium serialization issue."
            )
            st.caption(f"Details: {exc}")
            st.session_state["map_fallback_warned"] = True
        st.components.v1.html(fmap.get_root().render(), height=height + 10, scrolling=False)


load_css(os.path.join("assets", "style.css"))

st.title("Crime Mapping and Clustering Analytics System")
st.caption("Interactive geospatial crime exploration, clustering, analytics, and route tracing")

for key, default in {
    "authenticated": False,
    "base_df": None,
    "filtered_df": None,
    "kmeans_df": None,
    "dbscan_df": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

if not st.session_state.authenticated:
    card("Login")
    st.caption("Sign in to access the dashboard.")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login", type="primary", use_container_width=True):
        if username == APP_USERNAME and password == APP_PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Invalid username or password.")
    st.stop()

with st.sidebar:
    st.header("Navigation")
    if st.button("Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.kmeans_df = None
        st.session_state.dbscan_df = None
        st.rerun()
    menu = st.radio(
        "Go to",
        [
            "Upload Data",
            "Crime Map",
            "Routing",
            "Clustering",
            "Analytics Dashboard",
            "Download Filtered Data",
        ],
    )

    st.divider()
    st.subheader("Upload Data")
    uploaded_file = st.file_uploader("Upload crime .xlsx file", type=["xlsx"])

if uploaded_file is not None:
    try:
        base_df, warnings = load_crime_data(uploaded_file)
        st.session_state.base_df = base_df
        for warning in warnings:
            st.warning(warning)
    except Exception as exc:
        st.error(f"Data loading failed: {exc}")
        st.stop()
elif st.session_state.base_df is None and os.path.exists("sample_data.xlsx"):
    try:
        base_df, warnings = load_crime_data("sample_data.xlsx")
        st.session_state.base_df = base_df
        for warning in warnings:
            st.warning(warning)
        st.info("Loaded `sample_data.xlsx` by default.")
    except Exception as exc:
        st.error(f"Sample data load failed: {exc}")

base_df = st.session_state.base_df

if base_df is None:
    st.error("No dataset loaded. Upload an Excel file with the required columns.")
    st.code("\n".join(REQUIRED_COLUMNS))
    st.stop()

with st.sidebar:
    st.divider()
    st.subheader("Filters")

    month_options = sorted(base_df["Month"].dropna().astype(str).unique().tolist())
    location_options = sorted(base_df["Location"].dropna().astype(str).unique().tolist())
    junction_options = sorted(base_df["Key Junction"].dropna().astype(str).unique().tolist())
    lsoa_options = sorted(base_df["LSOA name"].dropna().astype(str).unique().tolist())
    outcome_options = sorted(base_df["Outcome type"].dropna().astype(str).unique().tolist())

    months = st.multiselect("Month", month_options, default=month_options)
    locations = st.multiselect("Location", location_options, default=location_options)
    junctions = st.multiselect("Key Junction", junction_options, default=junction_options)
    lsoas = st.multiselect("LSOA", lsoa_options, default=lsoa_options)
    outcomes = st.multiselect("Outcome Type", outcome_options, default=outcome_options)

filtered_df = apply_filters(base_df, months, locations, lsoas, outcomes).reset_index(drop=True)
if junctions:
    filtered_df = filtered_df[filtered_df["Key Junction"].isin(junctions)].reset_index(drop=True)
st.session_state.filtered_df = filtered_df

if filtered_df.empty:
    st.warning("No rows match current filters. Adjust sidebar filters.")
    st.stop()

st.markdown(
    "<div class='metric-strip'>"
    f"<div class='metric-card'><h4>Total Crimes</h4><p>{len(filtered_df):,}</p></div>"
    f"<div class='metric-card'><h4>Months</h4><p>{filtered_df['Month'].nunique()}</p></div>"
    f"<div class='metric-card'><h4>Junctions</h4><p>{filtered_df['Key Junction'].nunique()}</p></div>"
    f"<div class='metric-card'><h4>Outcomes</h4><p>{filtered_df['Outcome type'].nunique()}</p></div>"
    "</div>",
    unsafe_allow_html=True,
)

if menu == "Upload Data":
    card("Dataset Preview")
    st.dataframe(filtered_df.head(200), use_container_width=True)
    st.caption("Required columns validated, invalid coordinates removed, and a derived `Key Junction` was added for reference.")

elif menu == "Crime Map":
    card("Crime Point Mapping")
    render_map(create_crime_map(filtered_df), height=700, key="crime_map")

elif menu == "Routing":
    card("Point-to-Point Routing")
    st.caption("Select any two filtered crime points to compute a road route similar to map navigation.")

    if len(filtered_df) < 2:
        st.warning("At least two filtered crime points are required to create a route.")
    else:
        point_options = create_point_options(filtered_df)
        default_destination = 1 if len(point_options) > 1 else 0
        profile_labels = {
            "Driving": "driving",
            "Walking": "foot",
            "Cycling": "bike",
        }

        travel_mode = st.selectbox("Travel mode", list(profile_labels.keys()), index=0)

        col1, col2 = st.columns(2)
        with col1:
            origin_label = st.selectbox("Origin point", point_options, index=0)
        with col2:
            destination_label = st.selectbox(
                "Destination point",
                point_options,
                index=default_destination,
            )

        origin_index = point_options.index(origin_label)
        destination_index = point_options.index(destination_label)

        try:
            route_map, distance_km, duration_minutes = create_road_route_map(
                filtered_df,
                origin_index,
                destination_index,
                profile=profile_labels[travel_mode],
            )
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            with metric_col1:
                st.metric("Road Distance", f"{distance_km:.2f} km")
            with metric_col2:
                st.metric("Estimated Time", f"{duration_minutes:.1f} min")
            with metric_col3:
                st.metric("Selected Points", "2")
            render_map(route_map, height=700, key="route_map")
        except ValueError as exc:
            st.warning(str(exc))
        except Exception:
            st.info("Road routing is unavailable for these points right now, so the app is showing a direct fallback route.")
            route_map, distance_km = create_route_map(filtered_df, origin_index, destination_index)
            metric_col1, metric_col2 = st.columns(2)
            with metric_col1:
                st.metric("Direct Distance", f"{distance_km:.2f} km")
            with metric_col2:
                st.metric("Selected Points", "2")
            render_map(route_map, height=700, key="route_map_fallback")

elif menu == "Clustering":
    card("Clustering Workspace")
    tab1, tab2 = st.tabs(["K-Means", "DBSCAN"])

    with tab1:
        k = st.slider("Number of clusters", min_value=2, max_value=12, value=4, step=1)
        if st.button("Run K-Means", type="primary"):
            try:
                km_df, _ = run_kmeans(filtered_df, n_clusters=k)
                st.session_state.kmeans_df = km_df
                st.success("K-Means clustering completed.")
            except Exception as exc:
                st.error(f"K-Means failed: {exc}")

        if st.session_state.kmeans_df is not None:
            km_current = st.session_state.kmeans_df
            st.plotly_chart(
                plot_cluster_scatter(km_current, "kmeans_cluster", "K-Means Cluster Scatter"),
                use_container_width=True,
            )
            render_map(create_cluster_map(km_current, "kmeans_cluster"), height=560, key="kmeans_map")

    with tab2:
        eps = st.slider("eps", min_value=0.001, max_value=0.1, value=0.01, step=0.001, format="%.3f")
        min_samples = st.slider("min_samples", min_value=2, max_value=20, value=5, step=1)
        if st.button("Run DBSCAN", type="primary"):
            try:
                db_df, _ = run_dbscan(filtered_df, eps=eps, min_samples=min_samples)
                st.session_state.dbscan_df = db_df
                st.success("DBSCAN clustering completed.")
            except Exception as exc:
                st.error(f"DBSCAN failed: {exc}")

        if st.session_state.dbscan_df is not None:
            db_current = st.session_state.dbscan_df
            st.plotly_chart(
                plot_cluster_scatter(db_current, "dbscan_cluster", "DBSCAN Cluster Scatter"),
                use_container_width=True,
            )
            render_map(create_cluster_map(db_current, "dbscan_cluster"), height=560, key="dbscan_map")

elif menu == "Analytics Dashboard":
    card("Crime Analytics Dashboard")
    artifacts = build_analytics(filtered_df)
    if not artifacts:
        st.warning("Not enough data to build analytics.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(artifacts["monthly"], use_container_width=True)
            st.plotly_chart(artifacts["locations"], use_container_width=True)
        with col2:
            st.plotly_chart(artifacts["outcomes"], use_container_width=True)
            st.plotly_chart(artifacts["density"], use_container_width=True)

        st.plotly_chart(artifacts["top_lsoa"], use_container_width=True)
        st.dataframe(artifacts["top_lsoa_table"], use_container_width=True)

elif menu == "Download Filtered Data":
    card("Download Data")
    st.download_button(
        "Download Filtered CSV",
        data=to_csv_bytes(filtered_df),
        file_name="filtered_crime_data.csv",
        mime="text/csv",
        use_container_width=True,
    )

    if st.session_state.kmeans_df is not None:
        st.download_button(
            "Download K-Means Clustered CSV",
            data=to_csv_bytes(st.session_state.kmeans_df),
            file_name="kmeans_clustered_crime_data.csv",
            mime="text/csv",
            use_container_width=True,
        )

    if st.session_state.dbscan_df is not None:
        st.download_button(
            "Download DBSCAN Clustered CSV",
            data=to_csv_bytes(st.session_state.dbscan_df),
            file_name="dbscan_clustered_crime_data.csv",
            mime="text/csv",
            use_container_width=True,
        )

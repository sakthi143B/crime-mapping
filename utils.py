import io
import math
from typing import Dict, Iterable, List, Tuple

import folium
import pandas as pd
import plotly.express as px
import requests
from folium.plugins import MarkerCluster

REQUIRED_COLUMNS: List[str] = [
    "Crime ID",
    "Month",
    "Reported by",
    "Longitude",
    "Latitude",
    "Location",
    "LSOA code",
    "LSOA name",
    "Outcome type",
]

FOLIUM_ICON_COLORS: List[str] = [
    "red",
    "blue",
    "green",
    "purple",
    "orange",
    "darkred",
    "lightred",
    "beige",
    "darkblue",
    "darkgreen",
    "cadetblue",
    "darkpurple",
    "white",
    "pink",
    "lightblue",
    "lightgreen",
    "gray",
    "black",
    "lightgray",
]


def validate_columns(df: pd.DataFrame) -> List[str]:
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    return missing


def load_crime_data(uploaded_file) -> Tuple[pd.DataFrame, List[str]]:
    """Load Excel data, validate schema, and clean coordinate values."""
    df = pd.read_excel(uploaded_file, engine="openpyxl")
    missing_cols = validate_columns(df)
    if missing_cols:
        raise ValueError(f"Missing required columns: {', '.join(missing_cols)}")

    cleaned = df.copy()
    cleaned["Latitude"] = pd.to_numeric(cleaned["Latitude"], errors="coerce")
    cleaned["Longitude"] = pd.to_numeric(cleaned["Longitude"], errors="coerce")

    warnings: List[str] = []
    invalid_coord_mask = (
        cleaned["Latitude"].isna()
        | cleaned["Longitude"].isna()
        | ~cleaned["Latitude"].between(-90, 90)
        | ~cleaned["Longitude"].between(-180, 180)
    )

    invalid_count = int(invalid_coord_mask.sum())
    if invalid_count > 0:
        warnings.append(
            f"Removed {invalid_count} rows with invalid or missing Latitude/Longitude values."
        )
        cleaned = cleaned.loc[~invalid_coord_mask].copy()

    cleaned["Month"] = cleaned["Month"].astype(str)
    cleaned["Outcome type"] = cleaned["Outcome type"].fillna("Unknown").astype(str)
    cleaned["Location"] = cleaned["Location"].fillna("Unknown").astype(str)
    cleaned["LSOA name"] = cleaned["LSOA name"].fillna("Unknown").astype(str)
    cleaned = add_key_junctions(cleaned)

    if cleaned.empty:
        warnings.append("All rows were removed after validation. Upload a valid dataset.")

    return cleaned, warnings


def add_key_junctions(df: pd.DataFrame, precision: int = 3) -> pd.DataFrame:
    enriched = df.copy()
    enriched["_lat_bin"] = enriched["Latitude"].round(precision)
    enriched["_lon_bin"] = enriched["Longitude"].round(precision)

    junction_lookup = (
        enriched.groupby(["_lat_bin", "_lon_bin"])["Location"]
        .agg(lambda values: values.mode().iloc[0] if not values.mode().empty else "Unknown")
        .rename("Key Junction")
        .reset_index()
    )

    enriched = enriched.merge(junction_lookup, on=["_lat_bin", "_lon_bin"], how="left")
    enriched["Key Junction"] = enriched["Key Junction"].fillna(enriched["Location"]).astype(str)
    enriched["Key Junction"] = enriched["Key Junction"].where(
        enriched["Key Junction"].str.lower() != "unknown",
        enriched["Location"],
    )
    return enriched.drop(columns=["_lat_bin", "_lon_bin"])


def apply_filters(
    df: pd.DataFrame,
    months: Iterable[str],
    locations: Iterable[str],
    lsoas: Iterable[str],
    outcomes: Iterable[str],
) -> pd.DataFrame:
    filtered = df.copy()
    if months:
        filtered = filtered[filtered["Month"].isin(months)]
    if locations:
        filtered = filtered[filtered["Location"].isin(locations)]
    if lsoas:
        filtered = filtered[filtered["LSOA name"].isin(lsoas)]
    if outcomes:
        filtered = filtered[filtered["Outcome type"].isin(outcomes)]
    return filtered


def build_outcome_color_map(outcomes: Iterable[str]) -> Dict[str, str]:
    unique_outcomes = sorted(set(outcomes))
    color_map: Dict[str, str] = {}
    for idx, outcome in enumerate(unique_outcomes):
        color_map[outcome] = FOLIUM_ICON_COLORS[idx % len(FOLIUM_ICON_COLORS)]
    return color_map


def create_crime_map(df: pd.DataFrame) -> folium.Map:
    if df.empty:
        return folium.Map(location=[20.0, 0.0], zoom_start=2, tiles="CartoDB dark_matter")

    center = [df["Latitude"].mean(), df["Longitude"].mean()]
    fmap = folium.Map(location=center, zoom_start=11, tiles="CartoDB dark_matter")
    marker_cluster = MarkerCluster(name="Crime Points").add_to(fmap)

    color_map = build_outcome_color_map(df["Outcome type"].unique())

    for _, row in df.iterrows():
        popup = folium.Popup(
            (
                f"<b>Crime ID:</b> {row['Crime ID']}<br>"
                f"<b>Month:</b> {row['Month']}<br>"
                f"<b>Location:</b> {row['Location']}<br>"
                f"<b>Key Junction:</b> {row['Key Junction']}<br>"
                f"<b>Outcome:</b> {row['Outcome type']}"
            ),
            max_width=350,
        )

        folium.Marker(
            location=[row["Latitude"], row["Longitude"]],
            popup=popup,
            tooltip=row["Outcome type"],
            icon=folium.Icon(color=color_map.get(row["Outcome type"], "blue"), icon="info-sign"),
        ).add_to(marker_cluster)

    folium.LayerControl().add_to(fmap)
    return fmap


def create_point_options(df: pd.DataFrame) -> List[str]:
    options: List[str] = []
    for _, row in df.iterrows():
        options.append(
            f"{row['Crime ID']} | {row['Key Junction']} | {row['Month']} | "
            f"{row['Latitude']:.5f}, {row['Longitude']:.5f}"
        )
    return options


def haversine_distance_km(
    origin_lat: float,
    origin_lon: float,
    destination_lat: float,
    destination_lon: float,
) -> float:
    earth_radius_km = 6371.0
    lat1 = math.radians(origin_lat)
    lon1 = math.radians(origin_lon)
    lat2 = math.radians(destination_lat)
    lon2 = math.radians(destination_lon)

    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1

    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius_km * c


def create_route_map(df: pd.DataFrame, origin_index: int, destination_index: int) -> Tuple[folium.Map, float]:
    if df.empty:
        raise ValueError("Cannot create a route map from an empty dataset.")
    if origin_index == destination_index:
        raise ValueError("Origin and destination must be different points.")

    origin = df.iloc[origin_index]
    destination = df.iloc[destination_index]

    route_points = [
        [origin["Latitude"], origin["Longitude"]],
        [destination["Latitude"], destination["Longitude"]],
    ]

    center_lat = (origin["Latitude"] + destination["Latitude"]) / 2
    center_lon = (origin["Longitude"] + destination["Longitude"]) / 2
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="CartoDB dark_matter")

    distance_km = haversine_distance_km(
        origin["Latitude"],
        origin["Longitude"],
        destination["Latitude"],
        destination["Longitude"],
    )

    folium.Marker(
        location=route_points[0],
        popup=(
            f"<b>Origin</b><br>"
            f"Crime ID: {origin['Crime ID']}<br>"
            f"Location: {origin['Location']}<br>"
            f"Key Junction: {origin['Key Junction']}<br>"
            f"Month: {origin['Month']}"
        ),
        tooltip="Origin",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(fmap)

    folium.Marker(
        location=route_points[1],
        popup=(
            f"<b>Destination</b><br>"
            f"Crime ID: {destination['Crime ID']}<br>"
            f"Location: {destination['Location']}<br>"
            f"Key Junction: {destination['Key Junction']}<br>"
            f"Month: {destination['Month']}"
        ),
        tooltip="Destination",
        icon=folium.Icon(color="red", icon="stop"),
    ).add_to(fmap)

    folium.PolyLine(
        route_points,
        color="#43b0ff",
        weight=5,
        opacity=0.9,
        tooltip=f"Direct route: {distance_km:.2f} km",
    ).add_to(fmap)

    fmap.fit_bounds(route_points, padding=(30, 30))
    return fmap, distance_km


def get_osrm_route(
    origin_lat: float,
    origin_lon: float,
    destination_lat: float,
    destination_lon: float,
    profile: str = "driving",
) -> Tuple[List[List[float]], float, float]:
    coordinates = f"{origin_lon},{origin_lat};{destination_lon},{destination_lat}"
    url = f"https://router.project-osrm.org/route/v1/{profile}/{coordinates}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
    }

    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    payload = response.json()

    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise ValueError(payload.get("message", "No road route could be found for the selected points."))

    route = payload["routes"][0]
    geometry = route["geometry"]["coordinates"]
    route_points = [[lat, lon] for lon, lat in geometry]
    distance_km = route["distance"] / 1000
    duration_minutes = route["duration"] / 60
    return route_points, distance_km, duration_minutes


def create_road_route_map(
    df: pd.DataFrame,
    origin_index: int,
    destination_index: int,
    profile: str = "driving",
) -> Tuple[folium.Map, float, float]:
    if df.empty:
        raise ValueError("Cannot create a route map from an empty dataset.")
    if origin_index == destination_index:
        raise ValueError("Origin and destination must be different points.")

    origin = df.iloc[origin_index]
    destination = df.iloc[destination_index]

    route_points, distance_km, duration_minutes = get_osrm_route(
        origin["Latitude"],
        origin["Longitude"],
        destination["Latitude"],
        destination["Longitude"],
        profile=profile,
    )

    center_lat = (origin["Latitude"] + destination["Latitude"]) / 2
    center_lon = (origin["Longitude"] + destination["Longitude"]) / 2
    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="CartoDB dark_matter")

    folium.Marker(
        location=[origin["Latitude"], origin["Longitude"]],
        popup=(
            f"<b>Origin</b><br>"
            f"Crime ID: {origin['Crime ID']}<br>"
            f"Location: {origin['Location']}<br>"
            f"Key Junction: {origin['Key Junction']}<br>"
            f"Month: {origin['Month']}"
        ),
        tooltip="Origin",
        icon=folium.Icon(color="green", icon="play"),
    ).add_to(fmap)

    folium.Marker(
        location=[destination["Latitude"], destination["Longitude"]],
        popup=(
            f"<b>Destination</b><br>"
            f"Crime ID: {destination['Crime ID']}<br>"
            f"Location: {destination['Location']}<br>"
            f"Key Junction: {destination['Key Junction']}<br>"
            f"Month: {destination['Month']}"
        ),
        tooltip="Destination",
        icon=folium.Icon(color="red", icon="stop"),
    ).add_to(fmap)

    folium.PolyLine(
        route_points,
        color="#43b0ff",
        weight=5,
        opacity=0.9,
        tooltip=f"Road route: {distance_km:.2f} km, {duration_minutes:.1f} min",
    ).add_to(fmap)

    fmap.fit_bounds(route_points, padding=(30, 30))
    return fmap, distance_km, duration_minutes


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8")


def plotly_palette(n: int) -> List[str]:
    palette = px.colors.qualitative.Safe + px.colors.qualitative.Bold + px.colors.qualitative.Dark24
    if n <= len(palette):
        return palette[:n]
    repeats = (n // len(palette)) + 1
    return (palette * repeats)[:n]

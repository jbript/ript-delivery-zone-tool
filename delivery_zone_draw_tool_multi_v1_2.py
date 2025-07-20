# Filename: delivery_zone_draw_tool_multi_v1_3.py
import streamlit as st
from streamlit_folium import st_folium
import folium
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, shape, mapping
import json

# App Version
VERSION = "v1.3"

st.set_page_config(page_title=f"Delivery Planner {VERSION}", layout="wide")
st.title(f"📦 Multi-Zone Delivery Planner ({VERSION})")

# Load customer data
df = pd.read_csv("Consolidated_Customer_Geocoded_List.csv")
gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["Longitude"], df["Latitude"]), crs="EPSG:4326")

# Initialize session state for zones
if "zones" not in st.session_state:
    st.session_state.zones = {}

# Layout: Map on left, controls on right
col1, col2 = st.columns([2, 1])

with col1:
    m = folium.Map(location=[gdf["Latitude"].mean(), gdf["Longitude"].mean()], zoom_start=12)
    # Draw saved zones
    for label, zone in st.session_state.zones.items():
        folium.GeoJson(
            mapping(zone["geometry"]),
            name=label,
            style_function=lambda feature, col=zone["color"]: {
                'color': col,
                'fillColor': col,
                'fillOpacity': 0.2,
                'weight': 2
            }
        ).add_to(m)
    # Plot customer points
    for _, row in gdf.iterrows():
        folium.CircleMarker(
            location=(row["Latitude"], row["Longitude"]),
            radius=2,
            color="blue",
            fill=True,
            fill_opacity=0.5
        ).add_to(m)
    # Add drawing tools
    draw = folium.plugins.Draw(
        export=True,
        draw_options={"polyline": False, "polygon": True, "rectangle": True, "circle": False},
        edit_options={"edit": False}
    )
    draw.add_to(m)
    output = st_folium(m, width=700, height=600)

with col2:
    st.markdown("**🖊️ Draw a zone on the map, then label and save it below**")
    st.markdown("---")
    ie_col1, ie_col2 = st.columns(2)
    with ie_col1:
        uploaded = st.file_uploader("Import Zones (JSON or GeoJSON)", type=["json", "geojson"])
        if uploaded:
            try:
                raw = uploaded.read()
                text = raw.decode("utf-8")
                data = json.loads(text)
                # GeoJSON FeatureCollection
                if isinstance(data, dict) and data.get("type") == "FeatureCollection":
                    imported = 0
                    for feat in data["features"]:
                        geom = shape(feat.get("geometry", {}))
                        props = feat.get("properties", {})
                        label = props.get("name", f"Zone {len(st.session_state.zones) + 1}")
                        color = props.get("color", "red")
                        inside = gdf[gdf.geometry.within(geom)].copy()
                        st.session_state.zones[label] = {"geometry": geom, "data": inside, "count": len(inside), "color": color}
                        imported += 1
                    st.success(f"Imported {imported} zones from GeoJSON.")
                else:
                    # legacy JSON export
                    for label, info in data.items():
                        geom = shape(info.get("geometry", {}))
                        color = info.get("color", "red")
                        inside = gdf[gdf.geometry.within(geom)].copy()
                        st.session_state.zones[label] = {"geometry": geom, "data": inside, "count": len(inside), "color": color}
                    st.success(f"Imported {len(data)} zones from JSON.")
            except Exception as e:
                st.error(f"Failed to import zones: {e}")
    with ie_col2:
        if st.session_state.zones:
            export_data = {label: {"geometry": mapping(zone["geometry"]), "color": zone["color"]} for label, zone in st.session_state.zones.items()}
            js = json.dumps(export_data)
            st.download_button(
                "Export Zones JSON",
                data=js,
                file_name=f"zones_export_{VERSION}.json",
                mime="application/json"
            )
    st.markdown("---")
    if output and output.get("last_active_drawing"):
        new_geo = output["last_active_drawing"]["geometry"]
        new_poly = shape(new_geo)
        if not any(new_poly.equals(z["geometry"]) for z in st.session_state.zones.values()):
            label = st.text_input("Zone Label", value=f"Zone {len(st.session_state.zones) + 1}")
            if st.button("Save Zone"):
                inside = gdf[gdf.geometry.within(new_poly)].copy()
                palette = ["red", "blue", "green", "purple", "orange"]
                color = palette[len(st.session_state.zones) % len(palette)]
                st.session_state.zones[label] = {"geometry": new_poly, "data": inside, "count": len(inside), "color": color}
                st.success(f"Saved zone '{label}' with {len(inside)} customers.")
    if st.session_state.zones:
        st.header("📊 Saved Zones Summary")
        for label, zone in st.session_state.zones.items():
            st.subheader(f"{label} – {zone['count']} customers")
            st.dataframe(zone["data"][['Customer ID','Street Address','Lifetime Net Sales','Lifetime Avg Order Value']])
            csv = zone["data"].to_csv(index=False)
            st.download_button(
                f"⬇️ Download {label} Customers",
                data=csv,
                file_name=f"{label}_Customers_{VERSION}.csv",
                mime="text/csv"
            )
    else:
        st.info("No saved zones yet. Draw a shape and label it to begin.")

import streamlit as st
from streamlit_folium import st_folium
import folium
import pandas as pd
import geopandas as gpd
from shapely.geometry import shape, mapping
import json

# ------------------------------------------------------------------ #
#  App Version
# ------------------------------------------------------------------ #
VERSION = "v1.4"     # <— bump only this string for future releases

# ------------------------------------------------------------------ #
#  Page config & title
# ------------------------------------------------------------------ #
st.set_page_config(page_title=f"Delivery Planner {VERSION}", layout="wide")
st.title(f"📦 Multi-Zone Delivery Planner ({VERSION})")

# ------------------------------------------------------------------ #
#  Load customer data
# ------------------------------------------------------------------ #
df  = pd.read_csv("Consolidated_Customer_Geocoded_List.csv")
gdf = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df["Longitude"], df["Latitude"]),
        crs="EPSG:4326",
      )

# ------------------------------------------------------------------ #
#  Session-state container for zones
# ------------------------------------------------------------------ #
if "zones" not in st.session_state:
    st.session_state.zones = {}          # label → {geometry, data, count, color}
if "last_upload_hash" not in st.session_state:
    st.session_state.last_upload_hash = None

# ------------------------------------------------------------------ #
#  Layout
# ------------------------------------------------------------------ #
col1, col2 = st.columns([2, 1])

# -----------------------  MAP (left column) ----------------------- #
with col1:
    m = folium.Map(
        location=[gdf["Latitude"].mean(), gdf["Longitude"].mean()],
        zoom_start=12
    )

    # draw saved zones
    for label, zone in st.session_state.zones.items():
        folium.GeoJson(
            mapping(zone["geometry"]),
            name=label,
            style_function=lambda _, col=zone["color"]: {
                "color": col,
                "fillColor": col,
                "fillOpacity": 0.2,
                "weight"     : 2,
            },
        ).add_to(m)

    # customer dots
    for _, row in gdf.iterrows():
        folium.CircleMarker(
            location=(row["Latitude"], row["Longitude"]),
            radius=2,
            color="blue",
            fill=True,
            fill_opacity=0.5,
        ).add_to(m)

    # draw tool
    draw = folium.plugins.Draw(
        export=True,
        draw_options={
            "polyline" : False,
            "polygon"  : True,
            "rectangle": True,
            "circle"   : False,
        },
        edit_options={"edit": False},
    )
    draw.add_to(m)

    # render map
    output = st_folium(m, width=700, height=600)

# --------------------  CONTROLS (right column) -------------------- #
with col2:
    st.markdown("**🖊️ Draw a zone on the map, then label & save it below**")
    st.markdown("---")

    # ---------- Import / Export ----------
    c_import, c_export = st.columns(2)

    # ---------- Import ----------
    with c_import:
        uploaded = st.file_uploader(
            "Import zones (JSON or GeoJSON)",
            type=["json", "geojson"],
        )
        if uploaded:
            # guard: process each file only once
            file_bytes = uploaded.getvalue()
            file_hash  = hash(file_bytes)
            if file_hash != st.session_state.last_upload_hash:
                st.session_state.last_upload_hash = file_hash
                try:
                    data = json.loads(file_bytes.decode("utf-8"))

                    # GeoJSON FeatureCollection
                    if isinstance(data, dict) and data.get("type") == "FeatureCollection":
                        imported = 0
                        for feat in data["features"]:
                            geom  = shape(feat.get("geometry", {}))
                            props = feat.get("properties", {})
                            label = props.get("name", f"Zone {len(st.session_state.zones)+1}")
                            color = props.get("color", "red")
                            inside = gdf[gdf.geometry.within(geom)].copy()
                            st.session_state.zones[label] = {
                                "geometry": geom,
                                "data"    : inside,
                                "count"   : len(inside),
                                "color"   : color,
                            }
                            imported += 1
                        st.success(f"Imported {imported} zones from GeoJSON.")
                    else:
                        # legacy JSON export
                        for label, info in data.items():
                            geom  = shape(info.get("geometry", {}))
                            color = info.get("color", "red")
                            inside = gdf[gdf.geometry.within(geom)].copy()
                            st.session_state.zones[label] = {
                                "geometry": geom,
                                "data"    : inside,
                                "count"   : len(inside),
                                "color"   : color,
                            }
                        st.success(f"Imported {len(data)} zones from JSON.")
                except Exception as e:
                    st.error(f"Failed to import zones: {e}")
            else:
                st.info("This file has already been imported.")

    # ---------- Export ----------
    with c_export:
        if st.session_state.zones:
            export_data = {
                label: {
                    "geometry": mapping(zone["geometry"]),
                    "color"   : zone["color"],
                }
                for label, zone in st.session_state.zones.items()
            }
            js = json.dumps(export_data)
            st.download_button(
                "Export Zones JSON",
                data      = js,
                file_name = f"zones_export_{VERSION}.json",
                mime      = "application/json",
            )

    st.markdown("---")

    # ---------- Save newly drawn polygon ----------
    if output and output.get("last_active_drawing"):
        new_poly = shape(output["last_active_drawing"]["geometry"])
        if not any(new_poly.equals(z["geometry"]) for z in st.session_state.zones.values()):
            label = st.text_input("Zone Label", value=f"Zone {len(st.session_state.zones)+1}")
            if st.button("Save Zone"):
                inside  = gdf[gdf.geometry.within(new_poly)].copy()
                palette = ["red","blue","green","purple","orange"]
                color   = palette[len(st.session_state.zones) % len(palette)]
                st.session_state.zones[label] = {
                    "geometry": new_poly,
                    "data"    : inside,
                    "count"   : len(inside),
                    "color"   : color,
                }
                st.success(f"Saved {label} with {len(inside)} customers.")

    # ---------- Summary table ----------
    if st.session_state.zones:
        st.header("📊 Saved Zones Summary")
        for label, zone in st.session_state.zones.items():
            st.subheader(f"{label} – {zone['count']} customers")
            st.dataframe(
                zone["data"][['Customer ID','Street Address','Lifetime Net Sales','Lifetime Avg Order Value']]
            )
            csv = zone["data"].to_csv(index=False)
            st.download_button(
                f"⬇️ Download {label} Customers",
                data      = csv,
                file_name = f"{label}_Customers_{VERSION}.csv",
                mime      = "text/csv",
            )
    else:
        st.info("No saved zones yet. Draw a shape and label it to begin.")

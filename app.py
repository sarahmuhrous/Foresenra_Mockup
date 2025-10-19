import os
import glob
import streamlit as st
import geopandas as gpd
import folium
from folium.plugins import HeatMap
from streamlit_folium import folium_static
import pandas as pd
import numpy as np

# Optional libraries (used if available)
try:
    import mercantile
except Exception:
    mercantile = None

try:
    import h3
except Exception:
    h3 = None

# -----------------------------
# Helper functions
# -----------------------------
def quadkey_to_tilexy(quadkey):
    x = 0
    y = 0
    level = len(quadkey)
    for i in range(level, 0, -1):
        mask = 1 << (i - 1)
        digit = int(quadkey[level - i])
        if digit == 0:
            pass
        elif digit == 1:
            x |= mask
        elif digit == 2:
            y |= mask
        elif digit == 3:
            x |= mask
            y |= mask
    return x, y, level

def tilexy_to_latlon(x, y, level):
    n = 2 ** level
    lon_deg = x / n * 360.0 - 180.0
    lat_rad = np.arctan(np.sinh(np.pi * (1 - 2 * y / n)))
    lat_deg = np.degrees(lat_rad)
    return lat_deg, lon_deg

# -----------------------------
# Page setup
# -----------------------------
st.set_page_config(page_title="Foresentra Dashboard", layout="wide", page_icon="🌍")
st.markdown("<style>body{background-color:white;}</style>", unsafe_allow_html=True)

st.markdown(
    "<h1 style='text-align:center; color:#2c3e50;'>🌍 Foresentra</h1>"
    "<h3 style='text-align:center; color:#34495e;'>Qina Internet Coverage Dashboard</h3>",
    unsafe_allow_html=True
)
st.write("")

# -----------------------------
# Load base geographic data
# -----------------------------
data_folder = "data"
shp_path = os.path.join(data_folder, "ne_110m_admin_0_countries.shp")
gadm_path = os.path.join(data_folder, "gadm41_EGY_1.json")
gdf_qena_speed_path = os.path.join(data_folder, "gdf_qena_speed.geojson")

try:
    world = gpd.read_file(shp_path)
    gdf_admin1 = gpd.read_file(gadm_path)
except Exception as e:
    st.error(f"⚠️ حدث خطأ أثناء قراءة ملفات الحدود. تأكدي إن الملفات موجودة في مجلد 'data'.\n{e}")
    st.stop()

# extract Egypt and Qina
try:
    egypt = world[world["NAME"].str.contains("Egypt", case=False)]
    Qina = gdf_admin1[gdf_admin1["NAME_1"] == "Qina"]
    if Qina.empty:
        raise ValueError("لم يتم العثور على صف خاص بقنا في gadm41_EGY_1.json")
except Exception as e:
    st.error(f"⚠️ لم يتم العثور على حدود مصر أو قنا: {e}")
    st.stop()

# -----------------------------
# Prepare/generate gdf_qena_speed if missing
# -----------------------------
gdf_qena_speed = None
if os.path.exists(gdf_qena_speed_path):
    try:
        gdf_qena_speed = gpd.read_file(gdf_qena_speed_path)
    except Exception as e:
        st.warning(f"وجدت الملف {gdf_qena_speed_path} لكن حدث خطأ أثناء قراءته: {e}. سأحاول إعادة توليده.")
        gdf_qena_speed = None

if gdf_qena_speed is None:
    st.info("لم يتم العثور على ملف 'gdf_qena_speed.geojson'. سأحاول توليده من ملفات Ookla الموجودة في مجلد data/ (إن وُجدت).")
    # search for parquet or csv files in data folder that look like Ookla exports
    parquet_files = glob.glob(os.path.join(data_folder, "**", "*.parquet"), recursive=True)
    csv_files = glob.glob(os.path.join(data_folder, "**", "*.csv"), recursive=True)
    found = False
    df = None

    # Prefer parquet (Ookla open data often in parquet)
    for p in parquet_files:
        try:
            # try to read parquet with pandas (if s3 path, pandas will error; we only read local files here)
            df = pd.read_parquet(p)
            found = True
            st.info(f"تم العثور على ملف parquet: {p}")
            break
        except Exception:
            continue

    # fallback to CSV
    if not found:
        for c in csv_files:
            try:
                df = pd.read_csv(c)
                found = True
                st.info(f"تم العثور على ملف csv: {c}")
                break
            except Exception:
                continue

    if not found or df is None:
        st.warning("لم أعثر على ملفات بيانات Ookla داخل مجلد data/. يمكنك رفع ملفات parquet/csv الخاصة بالسرعات إلى مجلد data/ ثم إعادة التشغيل.")
    else:
        # process dataframe to get lat/lon and avg_d_kbps
        try:
            # If GeoParquet/has geometry, try to read as geodataframe
            if {"geometry", "avg_d_kbps"}.issubset(df.columns):
                gdf_temp = gpd.GeoDataFrame(df, geometry=df["geometry"])
            else:
                # Try quadkey -> lat/lon
                if "quadkey" in df.columns:
                    df = df[df["quadkey"].notnull()].copy()
                    coords = df["quadkey"].apply(lambda q: tilexy_to_latlon(*quadkey_to_tilexy(str(q))))
                    df["lat"] = coords.apply(lambda t: t[0])
                    df["lon"] = coords.apply(lambda t: t[1])
                # Try tile_x/tile_y/tile
                elif {"tile_x", "tile_y", "tile"}.issubset(df.columns) and mercantile is not None:
                    pts = []
                    for x, y, z in zip(df["tile_x"], df["tile_y"], df["tile"]):
                        try:
                            b = mercantile.bounds(int(x), int(y), int(z))
                            lon = (b.west + b.east) / 2
                            lat = (b.north + b.south) / 2
                        except Exception:
                            lon = np.nan
                            lat = np.nan
                        pts.append((lon, lat))
                    df["lon"] = [p[0] for p in pts]
                    df["lat"] = [p[1] for p in pts]
                # If lat/lon exist already
                elif {"lat", "lon"}.issubset(df.columns):
                    pass
                else:
                    # try columns with similar names
                    possible_lon = [c for c in df.columns if "lon" in c.lower() or "longitude" in c.lower()]
                    possible_lat = [c for c in df.columns if "lat" in c.lower() or "latitude" in c.lower()]
                    if possible_lon and possible_lat:
                        df["lon"] = df[possible_lon[0]]
                        df["lat"] = df[possible_lat[0]]
                    else:
                        raise ValueError("لا أستطيع إيجاد أعمدة الإحداثيات (lat/lon/quadkey/tile_x...).")

                # create GeoDataFrame
                gdf_temp = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326")

            # spatial join with Qina to keep only points inside Qina
            try:
                gdf_temp = gdf_temp.set_crs("EPSG:4326", allow_override=True)
            except Exception:
                pass

            gdf_qena_speed = gpd.sjoin(gdf_temp, Qina, how="inner", predicate="within")
            # keep needed columns
            if "avg_d_kbps" not in gdf_qena_speed.columns and "avg_d_kbps" in df.columns:
                gdf_qena_speed["avg_d_kbps"] = df["avg_d_kbps"]

            # save geojson
            try:
                out_path = gdf_qena_speed_path
                gdf_qena_speed.to_file(out_path, driver="GeoJSON")
                st.success(f"✅ تم توليد وحفظ ملف '{out_path}'.")
            except Exception as e:
                st.warning(f"توليد الملف نجح لكن حدث خطأ أثناء الحفظ: {e}")

        except Exception as e:
            st.error(f"⚠️ خطأ أثناء معالجة ملفات Ookla: {e}")

# -----------------------------
# KPIs (use values from data if available)
# -----------------------------
dead_zones = 0
complaints = 0
high_demand = 0
total_revenue = 0

if gdf_qena_speed is not None:
    try:
        # complaints: count points with avg_d_kbps < 2000
        complaints = int((gdf_qena_speed["avg_d_kbps"] < 2000).sum()) if "avg_d_kbps" in gdf_qena_speed.columns else 0
        high_demand = int((gdf_qena_speed["avg_d_kbps"] >= 8000).sum()) if "avg_d_kbps" in gdf_qena_speed.columns else 0
        # dead zones via H3 if library available and Qina polygon exists
        if h3 is not None:
            try:
                # generate H3 cells for Qina at res 7
                def get_hexes_in_geometry(geometry, res):
                    all_hexes = set()
                    if geometry is None:
                        return all_hexes
                    if geometry.geom_type == 'Polygon':
                        polygons = [geometry]
                    elif geometry.geom_type == 'MultiPolygon':
                        polygons = list(geometry.geoms)
                    else:
                        return all_hexes
                    for poly in polygons:
                        geojson = poly.__geo_interface__
                        outer = [(coord[1], coord[0]) for coord in geojson['coordinates'][0]]
                        h3_poly = [outer]
                        hexes = h3.polygon_to_cells(h3_poly, res=res)
                        all_hexes.update(hexes)
                    return all_hexes
                all_qina_hexes = get_hexes_in_geometry(Qina.geometry.iloc[0], res=7)
                speed_hexes = set()
                for _, row in gdf_qena_speed.iterrows():
                    g = row.geometry
                    if g.geom_type != "Point":
                        g = g.centroid
                    speed_hexes.add(h3.latlng_to_cell(g.y, g.x, 7))
                dead_hexes = all_qina_hexes - speed_hexes
                dead_zones = len(dead_hexes)
            except Exception:
                dead_zones = 0
        else:
            dead_zones = 0

        # revenue simple estimate
        revenue_per_area = 7500
        total_revenue = high_demand * revenue_per_area
    except Exception:
        pass

# -----------------------------
# Render KPIs
# -----------------------------
col1, col2, col3, col4 = st.columns(4)

cards = [
    ("#ffe6e6", "#c0392b", "🕳️ Dead Zones", dead_zones),
    ("#e8f4fd", "#2980b9", "📢 Complaints", complaints),
    ("#eafbea", "#27ae60", "📈 High Demand", high_demand),
    ("#fff9e6", "#f39c12", "💰 Total Revenue", f"{total_revenue:,.0f} EGP")
]

for col, (bg, color, title, value) in zip([col1, col2, col3, col4], cards):
    col.markdown(
        f"""
        <div style='background-color:{bg}; border-radius:15px; padding:20px;
                    text-align:center; box-shadow:2px 2px 8px rgba(0,0,0,0.1);'>
            <h3 style='color:{color};'>{title}</h3>
            <h1 style='color:{color};'>{value}</h1>
        </div>
        """, unsafe_allow_html=True
    )

st.markdown("---")

# -----------------------------
# Map with Heatmap and markers
# -----------------------------
try:
    m = folium.Map(location=[26.2, 32.7], zoom_start=7, tiles="cartodbpositron")
    folium.GeoJson(egypt.geometry, name="Egypt").add_to(m)
    folium.GeoJson(Qina.geometry, name="Qina", style_function=lambda x: {'color': 'green', 'weight': 2}).add_to(m)

    if gdf_qena_speed is not None and "avg_d_kbps" in gdf_qena_speed.columns and len(gdf_qena_speed) > 0:
        # prepare heatmap data
        gdf_qena_speed = gdf_qena_speed.dropna(subset=["avg_d_kbps"])
        gdf_qena_speed["lat"] = gdf_qena_speed.geometry.y
        gdf_qena_speed["lon"] = gdf_qena_speed.geometry.x
        heat_data = gdf_qena_speed[["lat", "lon", "avg_d_kbps"]].values.tolist()
        HeatMap(heat_data, radius=12, blur=25, min_opacity=0.3, max_zoom=13).add_to(m)

        # add circle markers colored by speed
        def color(speed):
            if speed < 2000:
                return "red"
            elif speed < 8000:
                return "orange"
            else:
                return "green"

        for _, row in gdf_qena_speed.iterrows():
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x],
                radius=4,
                color=color(row["avg_d_kbps"]),
                fill=True,
                fill_opacity=0.7
            ).add_to(m)

    st.success("✅ تم تحميل البيانات ورسم الخريطة مع Heatmap بنجاح!")
    folium_static(m, width=1100, height=650)

except Exception as e:
    st.error(f"⚠️ حدث خطأ أثناء رسم الخريطة: {e}")

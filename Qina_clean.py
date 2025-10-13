# -*- coding: utf-8 -*-
# ✅ نسخة نظيفة جاهزة لرفعها على Streamlit Cloud

import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import folium_static
from folium.plugins import HeatMap
from shapely.geometry import Polygon
import numpy as np
import h3
import rasterio
from rasterio.mask import mask

# ===========================
# 🗺️ إعداد الصفحة
# ===========================
st.set_page_config(page_title="Qina Dashboard", layout="wide")
st.markdown("<h1 style='text-align:center; color:#2c3e50;'>📊 Qina Internet Coverage Dashboard</h1>", unsafe_allow_html=True)
st.write("")

# ===========================
# 📂 تحميل البيانات
# ===========================
# تأكدي إن الملفات دي موجودة في نفس مجلد المشروع على GitHub
gdf_admin1 = gpd.read_file("gadm41_EGY_1.json")
Qina = gdf_admin1[gdf_admin1["NAME_1"] == "Qina"]

# ملف السرعات (ناتج من الكود في كولاب)
gdf_qena_speed = gpd.read_file("gdf_qena_speed.geojson")

# ===========================
# ⚙️ دوال مساعدة
# ===========================
def get_hexes_in_geometry(geometry, res):
    all_hexes = set()
    if geometry.geom_type == 'Polygon':
        polygons = [geometry]
    elif geometry.geom_type == 'MultiPolygon':
        polygons = geometry.geoms
    else:
        return all_hexes
    for poly in polygons:
        geojson = poly.__geo_interface__
        try:
            outer = [(coord[1], coord[0]) for coord in geojson['coordinates'][0]]
            hexes = h3.polygon_to_cells(outer, res=res)
            all_hexes.update(hexes)
        except Exception as e:
            print("Error:", e)
    return all_hexes


def color(speed):
    if speed < 2000:
        return "red"
    elif speed < 8000:
        return "orange"
    else:
        return "green"

# ===========================
# 📊 KPIs
# ===========================
# حساب خلايا قنا و Dead Zones
all_qina_hexes = get_hexes_in_geometry(Qina.geometry.iloc[0], res=7)

speed_hexes = set()
for _, row in gdf_qena_speed.iterrows():
    hex_id = h3.latlng_to_cell(row.geometry.y, row.geometry.x, 7)
    speed_hexes.add(hex_id)

dead_hexes = all_qina_hexes - speed_hexes
dead_zones_count = len(dead_hexes)
complaints = int((gdf_qena_speed["avg_d_kbps"] < 2000).sum())
high_demand = 304  # مؤقتًا ثابت
revenue_per_area = 7500
total_revenue = high_demand * revenue_per_area

# KPIs عرضها على الشاشة
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("🕳️ Dead Zones", dead_zones_count)
with col2:
    st.metric("📢 Complaints", complaints)
with col3:
    st.metric("📈 High Demand", high_demand)
with col4:
    st.metric("💰 Total Revenue (EGP)", f"{total_revenue:,}")

st.markdown("---")

# ===========================
# 🗺️ إنشاء الخريطة
# ===========================
map_center = [26.2, 32.7]
m = folium.Map(location=map_center, zoom_start=8)

# حدود المحافظة
folium.GeoJson(Qina.geometry, name="Qina boundary").add_to(m)

# النقاط حسب السرعة
for _, row in gdf_qena_speed.iterrows():
    folium.CircleMarker(
        location=[row.geometry.y, row.geometry.x],
        radius=4,
        color=color(row["avg_d_kbps"]),
        fill=True,
        fill_opacity=0.7
    ).add_to(m)

# HeatMap
heat_data = [[row.geometry.y, row.geometry.x, row["avg_d_kbps"]] for _, row in gdf_qena_speed.iterrows()]
HeatMap(heat_data, radius=15).add_to(m)

# Dead Zones
dead_zone_polygons = [Polygon(h3.h3_to_geo_boundary(hex_id, geo_json=True)) for hex_id in dead_hexes]
gdf_dead_zones = gpd.GeoDataFrame({'geometry': dead_zone_polygons}, crs="EPSG:4326")

folium.GeoJson(
    gdf_dead_zones.geometry,
    style_function=lambda x: {'fillColor': 'gray', 'color': 'gray', 'weight': 1, 'fillOpacity': 0.3}
).add_to(m)

# ===========================
# 👥 توزيع السكان
# ===========================
try:
    pop_path = "egy_pop_2025_CN_100m_R2024B_v1.tif"
    with rasterio.open(pop_path) as src:
        out_image, out_transform = mask(src, Qina.geometry, crop=True)
        array = out_image[0]
        array[array <= 0] = np.nan
        rows, cols = np.where(array > 500)
        coords = [src.xy(r, c) for r, c in zip(rows, cols)]
        for lon, lat in coords[::200]:
            folium.CircleMarker(location=[lat, lon], radius=2, color="black", fill=True).add_to(m)
except Exception as e:
    st.warning("⚠️ ملف السكان غير موجود أو به مشكلة، يمكن تجاهله مؤقتًا.")

# ===========================
# 📍 عرض الخريطة
# ===========================
folium_static(m)

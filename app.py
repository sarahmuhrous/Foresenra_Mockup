import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
import folium
from folium.plugins import HeatMap
from streamlit_folium import folium_static

# إعداد الصفحة
st.set_page_config(page_title="Foresentra", layout="wide")
st.markdown("<h1 style='text-align:center;'>Foresentra</h1>", unsafe_allow_html=True)

# تحميل البيانات
try:
    gdf_qena_speed = gpd.read_file("data/gdf_qena_speed.geojson")
    gdf_admin1 = gpd.read_file("data/gadm41_EGY_1.json")
    world = gpd.read_file("data/ne_110m_admin_0_countries.shp")
except Exception as e:
    st.error(f"حدث خطأ أثناء تحميل البيانات: {e}")
    st.stop()

# تحديد مصر وقنا
egypt = world[world["NAME"] == "Egypt"]
qena = gdf_admin1[gdf_admin1["NAME_1"] == "Qina"]

# حساب المؤشرات
dead_zones = 12
complaints = int((gdf_qena_speed["avg_d_kbps"] < 2000).sum())
high_demand = int((gdf_qena_speed["avg_d_kbps"] > 8000).sum())
total_revenue = high_demand * 7500

# عرض الكروت
col1, col2, col3, col4 = st.columns(4)
cards = [
    ("#ffe6e6", "#c0392b", "🕳️ Dead Zones", dead_zones),
    ("#e8f4fd", "#2980b9", "📢 Complaints", complaints),
    ("#eafbea", "#27ae60", "📈 High Demand", high_demand),
    ("#fff9e6", "#f39c12", "💰 Total Revenue", f"{total_revenue:,} EGP")
]
for col, (bg, color, title, value) in zip([col1, col2, col3, col4], cards):
    col.markdown(
        f"<div style='background-color:{bg};border-radius:15px;padding:20px;text-align:center;'>"
        f"<h3 style='color:{color};'>{title}</h3>"
        f"<h1 style='color:{color};'>{value}</h1></div>", unsafe_allow_html=True
    )

st.markdown('---')

# رسم الخريطة
try:
    m = folium.Map(location=[26.2, 32.7], zoom_start=7, tiles="cartodbpositron")
    folium.GeoJson(egypt.geometry, name="Egypt").add_to(m)
    folium.GeoJson(qena.geometry, name="Qina", style_function=lambda x: {'color': 'green', 'weight': 2}).add_to(m)

    gdf_qena_speed = gdf_qena_speed.dropna(subset=["avg_d_kbps"])
    gdf_qena_speed["lat"] = gdf_qena_speed.geometry.y
    gdf_qena_speed["lon"] = gdf_qena_speed.geometry.x
    heat_data = gdf_qena_speed[["lat", "lon", "avg_d_kbps"]].values.tolist()

    HeatMap(heat_data, radius=12, blur=25, min_opacity=0.3).add_to(m)

    st.success("✅ تم تحميل البيانات ورسم Heatmap بنجاح!")
    folium_static(m, width=1100, height=650)
except Exception as e:
    st.error(f"⚠️ حدث خطأ أثناء رسم الخريطة: {e}")
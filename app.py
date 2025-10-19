import streamlit as st
import geopandas as gpd
import folium
from folium.plugins import HeatMap
from streamlit_folium import folium_static
import numpy as np

# -----------------------------
# 🧭 إعداد الصفحة
# -----------------------------
st.set_page_config(page_title="Foresentra Dashboard", layout="wide", page_icon="🌍")
st.markdown("<style>body{background-color:white;}</style>", unsafe_allow_html=True)

# -----------------------------
# 🎯 العنوان الرئيسي
# -----------------------------
st.markdown(
    "<h1 style='text-align:center; color:#2c3e50;'>🌍 Foresentra</h1>"
    "<h3 style='text-align:center; color:#34495e;'>Qina Internet Coverage Dashboard</h3>",
    unsafe_allow_html=True
)

# -----------------------------
# 📂 تحميل البيانات
# -----------------------------
try:
    world = gpd.read_file("data/ne_110m_admin_0_countries.shp")
    gdf_admin1 = gpd.read_file("data/gadm41_EGY_1.json")
    gdf_qena_speed = gpd.read_file("data/gdf_qena_speed.geojson")
except Exception as e:
    st.error(f"⚠️ حدث خطأ أثناء تحميل البيانات: {e}")
    st.stop()

# -----------------------------
# 🗺️ تحديد المناطق
# -----------------------------
try:
    egypt = world[world["NAME"].str.contains("Egypt", case=False)]
    qina = gdf_admin1[gdf_admin1["NAME_1"] == "Qina"]
except Exception as e:
    st.error(f"⚠️ لم يتم العثور على حدود مصر أو قنا: {e}")
    st.stop()

# -----------------------------
# 📈 مؤشرات الأداء
# -----------------------------
dead_zones = 0
complaints = int(np.int64(27))
high_demand = 304
revenue_per_area = 7500
total_revenue = high_demand * revenue_per_area

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
# 🗺️ رسم الخريطة مع Heatmap
# -----------------------------
try:
    m = folium.Map(location=[26.2, 32.7], zoom_start=7, tiles="cartodbpositron")

    folium.GeoJson(egypt.geometry, name="Egypt").add_to(m)
    folium.GeoJson(qina.geometry, name="Qina", style_function=lambda x: {'color': 'green', 'weight': 2}).add_to(m)

    if {"geometry", "avg_d_kbps"}.issubset(gdf_qena_speed.columns):
        gdf_qena_speed = gdf_qena_speed.dropna(subset=["avg_d_kbps"])
        gdf_qena_speed["lat"] = gdf_qena_speed.geometry.y
        gdf_qena_speed["lon"] = gdf_qena_speed.geometry.x
        heat_data = gdf_qena_speed[["lat", "lon", "avg_d_kbps"]].values.tolist()
        HeatMap(heat_data, radius=10, blur=20, min_opacity=0.4, max_zoom=13).add_to(m)

    st.success("✅ تم تحميل البيانات ورسم الخريطة مع Heatmap بنجاح!")
    folium_static(m, width=1100, height=600)

except Exception as e:
    st.error(f"⚠️ خطأ أثناء رسم الخريطة: {e}")
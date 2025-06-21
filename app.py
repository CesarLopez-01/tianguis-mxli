import streamlit as st
import pandas as pd
import folium
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from streamlit_gsheets import GSheetsConnection
from folium.plugins import Draw, Fullscreen
from streamlit_folium import st_folium
from folium import Element

# ==================== Cargar datos ===================
conn = st.connection("gsheets", type=GSheetsConnection)
existing_data = conn.read(worksheet="Tianguis", usecols=list(range(6)), ttl=1800)
existing_data = existing_data.dropna(how="all")
df = existing_data.head(95)

st.set_page_config(layout="wide")
st.markdown("# Mapa de Tianguis en Mexicali")

st.markdown(
    """
    <style>
    /* Reduce padding entre bloques */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
    }
    /* Reduce margen entre los st.columns */
    div[data-testid="column"] {
        padding-top: 0rem;
        padding-bottom: 0rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)



# Calcula el centro del mapa
center_lat = df['lat'].mean()
center_lon = df['lon'].mean()

color_map = {
    "LUNES": "#2e7aab",
    "MARTES": "#ca7214",
    "MIERCOLES": "#ff5659",
    "JUEVES": "#47bab1",
    "VIERNES": "#00a247",
    "SABADO": "#fcca37",
    "DOMINGO": "#c27ba5"
}

# Agrupa por coordenadas
grouped = df.groupby(["lat","lon"]).agg(
    Dias=("DiaSemana", list),
    Nombre=("Nombre","first"),
    Calles=("Calles","first")
).reset_index()

# ==================== Mostrar solo el mapa en una fila ===================
m = folium.Map(location=[center_lat, center_lon], zoom_start=12)
folium.TileLayer('CartoDB positron', name='Blanco').add_to(m)
folium.TileLayer('CartoDB dark_matter', name='Negro').add_to(m)
folium.TileLayer('OpenStreetMap', name='Default').add_to(m)

Draw(
    export=False,
    draw_options={
        "polyline": False,
        "polygon": False,
        "rectangle": False,
        "circle": False,
        "marker": False,
        "circlemarker": True
    },
    edit_options={"edit": False, "remove": False},
).add_to(m)

# Añade marcadores
for idx, row in grouped.iterrows():
    dias = row['Dias']
    popup_content = f"""
    <div style="width:200px">
        <b>COLONIA:</b><br>{row['Nombre']}<br><br>
        <b>CALLES:</b><br>{row['Calles']}<br><br>
        <b>DIAS:</b><br>{', '.join(dias)}
    </div>
    """
    popup = folium.Popup(popup_content, max_width=250)

    fig, ax = plt.subplots(figsize=(1,1), dpi=100)
    counts = pd.Series(dias).value_counts()
    ax.pie(
        counts,
        colors=[color_map[d] for d in counts.index],
        startangle=90
    )
    ax.axis('equal')
    fig.tight_layout(pad=0)

    buf = BytesIO()
    fig.savefig(buf, format="png", transparent=True)
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)

    icon = folium.CustomIcon(
        icon_image=f'data:image/png;base64,{img_base64}',
        icon_size=(25,25)
    )

    folium.Marker(
        location=[row['lat'], row['lon']],
        popup=popup,
        icon=icon
    ).add_to(m)

Fullscreen(
    position="topleft",
    title="Pantalla completa",
    title_cancel="Salir pantalla completa",
    force_separate_button=True,
).add_to(m)

folium.LayerControl().add_to(m)

# Añade leyenda
legend_html = f"""
<div style="
    position: fixed;
    top: 180px; left: 10px;
    padding: 8px 12px;
    background: rgba(255, 255, 255, 0.8);
    border-radius: 8px;
    box-shadow: 0 0 6px rgba(0,0,0,0.2);
    font-size: 12px;
    line-height: 1.4;
    z-index:9999;
">
    <b style="font-size:13px;">Días de la semana</b><br>
    {"".join([f'<span style="background:{color};width:10px;height:10px;display:inline-block;margin-right:6px;border-radius:2px;"></span>{dia.capitalize()}<br>' for dia, color in color_map.items()])}
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# Mostrar mapa
map_data = st_folium(m, width=1200, height=600, returned_objects=["all_drawings"])

coords_clicked = ""
if map_data and "all_drawings" in map_data:
    drawings = map_data.get("all_drawings")
    if isinstance(drawings, list) and len(drawings) > 0:
        last_geom = drawings[-1]
        if last_geom.get("geometry", {}).get("type") == "Point":
            lon, lat = last_geom["geometry"]["coordinates"]
            coords_clicked = f"{lat:.6f}, {lon:.6f}"
lat = ""
lon = ""
if coords_clicked:
    lat_str, lon_str = coords_clicked.split(",")
    lat = lat_str.strip()
    lon = lon_str.strip()

# ==================== Formularios en tres columnas ===================
st.markdown("## Registra un nuevo tianguis")
col1, col2, col3 = st.columns([1,1,1])  # tres columnas en el renglón

# Columna 1: Coordenadas y Calle
with col1:
    st.write("### Coordenadas")
    lat_input = st.text_input(
        "Latitud",
        value=lat,
        disabled=True,
        placeholder="Usa la herramienta en el mapa"
    )
    lon_input = st.text_input(
        "Longitud",
        value=lon,
        disabled=True,
        placeholder="Usa la herramienta en el mapa"
    )
    st.write("### Calle")
    Calles = st.text_input(
        "Nombre de la calle",
        placeholder="Nombre de la calle"
    )

# Columna 2: Día(s) de la semana
with col2:
    st.write("### Día(s) de la semana")
    dias_opciones = ["LUNES","MARTES","MIERCOLES","JUEVES","VIERNES","SABADO","DOMINGO"]
    dias_seleccionados = []
    for dia in dias_opciones:
        if st.checkbox(dia, key=f"check_{dia}"):
            dias_seleccionados.append(dia)

# Columna 3: Momento del día
momentos_por_dia = {}
with col3:
    if dias_seleccionados:
        st.write("### Momento del día para cada día seleccionado")
        for dia in dias_seleccionados:
            momentos_por_dia[dia] = st.radio(
                f"{dia}:",
                ["Por la mañana","Por la tarde","Por la noche"],
                key=f"momento_{dia}"
            )

# Botón para enviar
coordenadas_validas = lat_input and lon_input and lat_input.replace('.', '').replace('-', '').isdigit() and lon_input.replace('.', '').replace('-', '').isdigit()
if st.button("Enviar datos", disabled=not coordenadas_validas):
    if not dias_seleccionados:
        st.warning("⚠️ Por favor, selecciona al menos un día antes de enviar.")
    else:
        nuevos_registros = []
        for dia in dias_seleccionados:
            nuevos_registros.append(
                {
                    "lat": lat_input,
                    "lon": lon_input,
                    "Calles": Calles,
                    "DiaSemana": dia,
                    "momento": momentos_por_dia[dia]
                }
            )
        nuevos_df = pd.DataFrame(nuevos_registros)
        updated_df = pd.concat([df, nuevos_df], ignore_index=True)

        conn.update(
            worksheet="Tianguis",
            data=updated_df
        )
        st.success(f"✅ {len(nuevos_df)} registro(s) guardado(s) correctamente.")
        


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
st.markdown("# Nuevo registro para Tianguis en Mexicali")

# CSS para reducir espacios entre bloques
st.markdown(
    """
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; }
    div[data-testid="column"] { padding-top: 0rem; padding-bottom: 0rem; }
    </style>
    """,
    unsafe_allow_html=True
)

# ==================== Formulario: Calle / Día / Momento ===================
st.markdown("## Datos del nuevo tianguis")

col1, col2, col3 = st.columns([1,1,1])

# Columna 1: Calle
with col1:
    st.write("### Calle")
    Calles = st.text_input(
        "Nombre de la calle",
        placeholder="Nombre de la calle"
    )

# Columna 2: Día(s) de la semana
with col2:
    st.write("### Día(s) de la semana")
    dias_opciones = ["LUNES","MARTES","MIERCOLES","JUEVES","VIERNES","SABADO","DOMINGO"]
    dias_seleccionados = [dia for dia in dias_opciones if st.checkbox(dia, key=f"check_{dia}")]

# Columna 3: Momento del día
momentos_por_dia = {}
with col3:
    if dias_seleccionados:
        st.write("### Momento del día por cada día")
        for dia in dias_seleccionados:
            momentos_por_dia[dia] = st.radio(
                f"{dia}:",
                ["Por la mañana","Por la tarde","Por la noche"],
                key=f"momento_{dia}"
            )

st.markdown("---")

# ==================== Mapa + coordenadas ===================
col_mapa, col_coords = st.columns([2,1])  # mapa a la izquierda, coords a la derecha

with col_mapa:
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

    # Mapa folium
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
        edit_options={"edit": True, "remove": False},
    ).add_to(m)

    # Añade marcadores con gráficos
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
        top: 220px; left: 12px;
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
    map_data = st_folium(m, width=1100, height=800, returned_objects=["all_drawings"])

# Columna derecha: coordenadas y botón enviar
with col_coords:
    st.write("### 📍 Coordenadas del punto")
    coords_clicked = ""
    lat = ""
    lon = ""
    if map_data and "all_drawings" in map_data:
        drawings = map_data.get("all_drawings")
        if isinstance(drawings, list) and len(drawings) > 0:
            last_geom = drawings[-1]
            if last_geom.get("geometry", {}).get("type") == "Point":
                lon, lat = last_geom["geometry"]["coordinates"]

    st.text_input(
        "Latitud",
        value=str(lat) if lat is not None else "",
        disabled=True,
        placeholder="Usa la herramienta en el mapa"
    )
    st.text_input(
        "Longitud",
        value=str(lon) if lon is not None else "",
        disabled=True,
        placeholder="Usa la herramienta en el mapa"
    )

    st.markdown("---")

    coordenadas_validas = (
        lat is not None and lon is not None and
        str(lat).replace('.', '').replace('-', '').isdigit() and
        str(lon).replace('.', '').replace('-', '').isdigit()
    )

    if st.button("Enviar datos", disabled=not coordenadas_validas):
        if not dias_seleccionados:
            st.warning("⚠️ Por favor, selecciona al menos un día antes de enviar.")
        elif not Calles:
            st.warning("⚠️ Por favor, ingresa una calle antes de enviar.")
        else:
            nuevos_registros = []
            for dia in dias_seleccionados:
                nuevos_registros.append(
                    {
                        "lat": lat,
                        "lon": lon,
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


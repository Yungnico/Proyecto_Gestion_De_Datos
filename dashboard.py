import streamlit as st
import pandas as pd
import plotly.express as px
import seaborn as sns
import matplotlib.pyplot as plt
import ssl

# --- 0. PARCHE SSL (Para Windows/Local) ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Dashboard COVID-19 Global", layout="wide")

# --- 2. CARGA DE DATOS ---
@st.cache_data
def load_data():
    try:
        df = pd.read_csv('covid_final_dashboard.csv')
        if 'Last_Update' in df.columns:
            df['Date'] = pd.to_datetime(df['Last_Update']).dt.normalize()
        elif 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
        return df
    except FileNotFoundError:
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.error("❌ No se encontraron datos. Ejecuta la Parte 3.")
    st.stop()

# --- 3. ENCABEZADO Y FILTROS (EN LA PÁGINA PRINCIPAL) ---
st.title("📊 Monitor COVID-19: Panel de Control")

# Creamos un contenedor con borde para que parezca una barra de herramientas
with st.container(border=True):
    st.markdown("### 🛠️ Configuración de Filtros")
    
    # Dividimos el ancho en 3 columnas iguales para los "botones/filtros"
    c_filt1, c_filt2, c_filt3 = st.columns(3)

    # A. Filtro Continente (Columna 1)
    with c_filt1:
        if 'Continent' in df.columns:
            todos_continentes = sorted(df['Continent'].astype(str).unique().tolist())
            sel_continent = st.multiselect("📍 1. Selecciona Continente(s)", todos_continentes, default=todos_continentes)
            df_cont = df[df['Continent'].isin(sel_continent)]
        else:
            df_cont = df
            sel_continent = []

    # B. Filtro País (Columna 2)
    with c_filt2:
        paises_disponibles = ["Todos"] + sorted(df_cont['Country_Region'].unique().tolist())
        sel_pais = st.selectbox("🌍 2. Selecciona País", paises_disponibles)

    # C. Filtro Fechas (Columna 3)
    with c_filt3:
        min_date = df['Date'].min()
        max_date = df['Date'].max()
        start_date, end_date = st.date_input("📅 3. Rango de Fechas", [min_date, max_date], min_value=min_date, max_value=max_date)

# --- 4. FILTRADO Y PROCESAMIENTO ---
mask_base = (df_cont['Date'] >= pd.to_datetime(start_date)) & (df_cont['Date'] <= pd.to_datetime(end_date))
df_filtrado = df_cont.loc[mask_base].sort_values('Date')

# Lógica "Todos" vs "País Individual"
if sel_pais == "Todos":
    subtitulo = "Vista Global (Agregada)"
    df_temporal = df_filtrado.groupby('Date')[['Confirmed', 'Deaths', 'Recovered', 'Active']].sum().reset_index()
    df_snapshot = df_filtrado.sort_values('Date').drop_duplicates(subset=['Country_Region'], keep='last')
else:
    subtitulo = f"Análisis Específico: {sel_pais}"
    df_temporal = df_filtrado[df_filtrado['Country_Region'] == sel_pais].groupby('Date').sum().reset_index()
    df_snapshot = df_filtrado[df_filtrado['Country_Region'] == sel_pais].iloc[[-1]]

if df_temporal.empty:
    st.warning("⚠️ No hay datos para mostrar con esta combinación de filtros.")
    st.stop()

# --- 5. CÁLCULOS (KPIs y REBROTE) ---
ultimo = df_temporal.iloc[-1]
penultimo = df_temporal.iloc[-2] if len(df_temporal) > 1 else ultimo

# Crecimiento
crecimiento = ((ultimo['Confirmed'] - penultimo['Confirmed']) / penultimo['Confirmed'] * 100) if penultimo['Confirmed'] > 0 else 0

# Rebrote (Tendencia últimos 5 días)
df_temporal['Active_Change'] = df_temporal['Active'].diff()
tendencia = df_temporal['Active_Change'].tail(5).sum()

if tendencia > 0:
    estado_rebrote = "⚠️ ALERTA: SUBIENDO"
    color_rebrote = "red" # Color para el semáforo
    icono = "🔥"
    desc_rebrote = "Los casos activos están aumentando en los últimos 5 días."
else:
    estado_rebrote = "✅ ESTABLE / BAJANDO"
    color_rebrote = "green"
    icono = "🛡️"
    desc_rebrote = "La curva de casos activos está controlada o descendiendo."

# Insights
letalidad = (ultimo['Deaths'] / ultimo['Confirmed'] * 100) if ultimo['Confirmed'] > 0 else 0
recuperacion = (ultimo['Recovered'] / ultimo['Confirmed'] * 100) if ultimo['Confirmed'] > 0 else 0

# --- 6. VISUALIZACIÓN ---
st.subheader(subtitulo)

# KPIs Principales
k1, k2, k3, k4 = st.columns(4)
k1.metric("Confirmados", f"{int(ultimo['Confirmed']):,}", f"{crecimiento:.2f}% (24h)")
k2.metric("Activos", f"{int(ultimo['Active']):,}", delta_color="inverse")
k3.metric("Fallecidos", f"{int(ultimo['Deaths']):,}")
k4.metric("Letalidad", f"{letalidad:.2f}%")

st.divider()

# SECCIÓN DE REBROTE E INSIGHTS
c_status, c_info = st.columns([1, 2])

with c_status:
    # Tarjeta visual de Rebrote
    st.markdown(f"""
    <div style="
        background-color: #f8f9fa; 
        padding: 20px; 
        border-radius: 12px; 
        border: 2px solid {color_rebrote};
        text-align: center;">
        <h2 style="color: {color_rebrote}; margin:0;">{icono}</h2>
        <h4 style="color: {color_rebrote}; margin:0;">{estado_rebrote}</h4>
        <hr>
        <p style="font-size: 0.9em;">{desc_rebrote}</p>
    </div>
    """, unsafe_allow_html=True)

with c_info:
    with st.container(border=True):
        st.markdown("#### 🤖 Insights Automáticos")
        col_i_a, col_i_b = st.columns(2)
        with col_i_a:
            st.info(f"**Tasa de Recuperación:** {recuperacion:.1f}% de los infectados ya están sanos.")
        with col_i_b:
            if sel_pais == "Todos":
                top_pais = df_snapshot.sort_values('Confirmed', ascending=False).iloc[0]['Country_Region']
                st.warning(f"**País Crítico:** {top_pais} lidera los contagios en la selección actual.")
            else:
                st.warning(f"**Impacto:** {sel_pais} aporta el {(ultimo['Confirmed']/df['Confirmed'].max()*100):.4f}% de casos globales.")

# PESTAÑAS DE GRÁFICOS
st.write("") # Espacio
tab_evo, tab_map, tab_ana = st.tabs(["📈 Evolución y Tendencias", "🌍 Mapa Geográfico", "🔬 Análisis Avanzado"])

with tab_evo:
    fig_line = px.line(
        df_temporal, 
        x='Date', 
        y=['Confirmed', 'Active', 'Deaths', 'Recovered'],
        log_y=True,
        title=f"Curva Logarítmica: {sel_pais if sel_pais != 'Todos' else 'Global'}",
        markers=True
    )
    st.plotly_chart(fig_line, use_container_width=True)

with tab_map:
    cm1, cm2 = st.columns([3, 1])
    with cm1:
        fig_map = px.choropleth(
            df_snapshot,
            locations='Country_Region',
            locationmode='country names',
            color='Confirmed',
            color_continuous_scale='Plasma',
            title="Distribución Geográfica",
            hover_name='Country_Region'
        )
        st.plotly_chart(fig_map, use_container_width=True)
    with cm2:
        st.markdown("#### Ranking Top 10")
        top10 = df_snapshot.nlargest(10, 'Confirmed').sort_values('Confirmed', ascending=True)
        st.dataframe(top10[['Country_Region', 'Confirmed']].set_index('Country_Region'), height=400)

with tab_ana:
    ca1, ca2 = st.columns(2)
    with ca1:
        st.markdown("##### Correlación de Variables")
        fig_h, ax = plt.subplots(figsize=(6, 5))
        sns.heatmap(df_temporal[['Confirmed', 'Deaths', 'Active', 'Recovered']].corr(), annot=True, cmap='coolwarm', ax=ax)
        st.pyplot(fig_h)
    with ca2:
        st.markdown("##### Composición de Casos")
        # Gráfico de pastel (Pie chart) de la distribución actual
        datos_pie = pd.DataFrame({
            'Estado': ['Activos', 'Fallecidos', 'Recuperados'],
            'Cantidad': [ultimo['Active'], ultimo['Deaths'], ultimo['Recovered']]
        })
        fig_pie = px.pie(datos_pie, values='Cantidad', names='Estado', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)
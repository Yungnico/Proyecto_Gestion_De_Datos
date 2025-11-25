import streamlit as st
import pandas as pd
import plotly.express as px
import seaborn as sns
import matplotlib.pyplot as plt
import ssl
import numpy as np

# --- 0. PARCHE SSL ---
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
        
        # Normalizar fechas
        if 'Last_Update' in df.columns:
            df['Date'] = pd.to_datetime(df['Last_Update']).dt.normalize()
        elif 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            
        # --- LIMPIEZA CRÍTICA DE NULOS (FIX NAN) ---
        cols_num = ['Confirmed', 'Deaths', 'Recovered', 'Active']
        for col in cols_num:
            if col in df.columns:
                df[col] = df[col].fillna(0) # Rellenar vacíos con 0 para evitar errores matemáticos
        
        # Recalcular Activos si son inconsistentes o negativos
        # Lógica: Active = Confirmed - Deaths - Recovered
        # Si el cálculo da negativo (error de datos), lo ponemos en 0
        df['Active_Calc'] = df['Confirmed'] - df['Deaths'] - df['Recovered']
        df['Active'] = df.apply(lambda x: x['Active_Calc'] if x['Active_Calc'] > 0 else 0, axis=1)
        
        return df
    except FileNotFoundError:
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.error("❌ No se encontraron datos. Ejecuta la Parte 3.")
    st.stop()

# --- 3. ENCABEZADO Y FILTROS ---
st.title("📊 Monitor COVID-19: Panel de Control Inteligente")

with st.container(border=True):
    c_filt1, c_filt2, c_filt3 = st.columns(3)

    # A. Continente
    with c_filt1:
        if 'Continent' in df.columns:
            todos_continentes = sorted(df['Continent'].astype(str).unique().tolist())
            sel_continent = st.multiselect("📍 1. Continente", todos_continentes, default=todos_continentes)
            df_cont = df[df['Continent'].isin(sel_continent)]
        else:
            df_cont = df
            sel_continent = []

    # B. País
    with c_filt2:
        paises_disponibles = ["Todos"] + sorted(df_cont['Country_Region'].unique().tolist())
        sel_pais = st.selectbox("🌍 2. País", paises_disponibles)

    # C. Fechas
    with c_filt3:
        min_date = df['Date'].min()
        max_date = df['Date'].max()
        start_date, end_date = st.date_input("📅 3. Rango", [min_date, max_date], min_value=min_date, max_value=max_date)

# --- 4. FILTRADO ---
mask_base = (df_cont['Date'] >= pd.to_datetime(start_date)) & (df_cont['Date'] <= pd.to_datetime(end_date))
df_filtrado = df_cont.loc[mask_base].sort_values('Date')

if sel_pais == "Todos":
    subtitulo = "Vista Global (Agregada)"
    df_temporal = df_filtrado.groupby('Date')[['Confirmed', 'Deaths', 'Recovered', 'Active']].sum().reset_index()
    df_snapshot = df_filtrado.sort_values('Date').drop_duplicates(subset=['Country_Region'], keep='last')
else:
    subtitulo = f"Análisis: {sel_pais}"
    df_temporal = df_filtrado[df_filtrado['Country_Region'] == sel_pais].groupby('Date').sum().reset_index()
    df_snapshot = df_filtrado[df_filtrado['Country_Region'] == sel_pais].iloc[[-1]]

if df_temporal.empty:
    st.warning("⚠️ No hay datos para mostrar.")
    st.stop()

# --- 5. LÓGICA INTELIGENTE DE DATOS (SMART DATA HANDLING) ---
ultimo = df_temporal.iloc[-1]
penultimo = df_temporal.iloc[-2] if len(df_temporal) > 1 else ultimo

# A. Crecimiento
crecimiento = ((ultimo['Confirmed'] - penultimo['Confirmed']) / penultimo['Confirmed'] * 100) if penultimo['Confirmed'] > 0 else 0

# B. Rebrote (Activos)
# Solo calculamos rebrote si hay datos de activos válidos (no planos en 0)
if ultimo['Active'] > 0:
    df_temporal['Active_Change'] = df_temporal['Active'].diff()
    tendencia = df_temporal['Active_Change'].tail(5).sum()
    
    if tendencia > 0:
        est_rebrote = "⚠️ ALERTA: SUBIENDO"
        col_rebrote = "red"
        icono = "🔥"
        desc_rebrote = "Casos activos al alza (últimos 5 días)."
    elif tendencia < 0:
        est_rebrote = "✅ BAJANDO"
        col_rebrote = "green"
        icono = "📉"
        desc_rebrote = "La curva de activos desciende."
    else:
        est_rebrote = "⚖️ ESTABLE"
        col_rebrote = "blue"
        icono = "➖"
        desc_rebrote = "Sin cambios significativos recientemente."
else:
    est_rebrote = "⚪ NO DATA"
    col_rebrote = "gray"
    icono = "🚫"
    desc_rebrote = "Datos de 'Activos' no confiables para este país."

# C. Tasas (Con validación de 0)
letalidad = (ultimo['Deaths'] / ultimo['Confirmed'] * 100) if ultimo['Confirmed'] > 0 else 0

# Validación específica para Recuperados
tiene_datos_recuperados = ultimo['Recovered'] > 0
if tiene_datos_recuperados:
    recuperacion = (ultimo['Recovered'] / ultimo['Confirmed'] * 100)
    txt_recuperacion = f"{recuperacion:.1f}%"
    txt_insight_recuperacion = f"**{recuperacion:.1f}%** tasa de recuperación reportada."
    tipo_alerta_rec = "success"
else:
    recuperacion = 0
    txt_recuperacion = "N/A *"
    txt_insight_recuperacion = "⚠️ **Datos de recuperación no disponibles** o no reportados oficialmente."
    tipo_alerta_rec = "warning"

# --- 6. VISUALIZACIÓN ---
st.subheader(subtitulo)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Confirmados", f"{int(ultimo['Confirmed']):,}", f"{crecimiento:.2f}%")
k2.metric("Activos Estimados", f"{int(ultimo['Active']):,}", delta_color="off")
k3.metric("Fallecidos", f"{int(ultimo['Deaths']):,}")
k4.metric("Recuperados", f"{int(ultimo['Recovered']):,}" if tiene_datos_recuperados else "No Reportado")

if not tiene_datos_recuperados:
    st.caption("* Algunos países dejaron de reportar casos recuperados en 2021/2022.")

st.divider()

# TARJETAS DE ANALISIS
c_status, c_info = st.columns([1, 2])

with c_status:
    st.markdown(f"""
    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 10px; border: 2px solid {col_rebrote}; text-align: center;">
        <h2 style="margin:0;">{icono}</h2>
        <h5 style="color: {col_rebrote}; margin:0;">{est_rebrote}</h5>
        <small>{desc_rebrote}</small>
    </div>
    """, unsafe_allow_html=True)

with c_info:
    with st.container(border=True):
        st.markdown("#### 🤖 Insights Automáticos")
        col_i_a, col_i_b = st.columns(2)
        
        with col_i_a:
            # Usamos st.warning si no hay datos, st.info si los hay
            if tiene_datos_recuperados:
                st.success(txt_insight_recuperacion)
            else:
                st.warning(txt_insight_recuperacion)
                
        with col_i_b:
            if sel_pais == "Todos":
                st.info(f"Letalidad global del periodo: **{letalidad:.2f}%**")
            else:
                # Insight de letalidad condicional
                if letalidad > 5:
                    st.error(f"⚠️ Letalidad alta: **{letalidad:.2f}%** (Superior al promedio).")
                else:
                    st.info(f"Letalidad controlada: **{letalidad:.2f}%**.")

# PESTAÑAS (GRÁFICOS)
tab_evo, tab_map, tab_ana = st.tabs(["📈 Evolución", "🌍 Mapa", "🔬 Análisis"])

with tab_evo:
    cols_plot = ['Confirmed', 'Deaths']
    if tiene_datos_recuperados:
        cols_plot += ['Recovered', 'Active']
    
    fig_line = px.line(
        df_temporal, 
        x='Date', 
        y=cols_plot,
        log_y=True,
        title=f"Curva Logarítmica ({'Datos completos' if tiene_datos_recuperados else 'Sin datos de recuperación'})",
        markers=True
    )
    st.plotly_chart(fig_line, use_container_width=True)

with tab_map:
    # Mapa
    cm1, cm2 = st.columns([3, 1])
    with cm1:
        fig_map = px.choropleth(
            df_snapshot,
            locations='Country_Region',
            locationmode='country names',
            color='Confirmed',
            color_continuous_scale='Plasma',
            hover_name='Country_Region'
        )
        st.plotly_chart(fig_map, use_container_width=True)
    with cm2:
        top10 = df_snapshot.nlargest(10, 'Confirmed')[['Country_Region', 'Confirmed']].set_index('Country_Region')
        st.dataframe(top10)

with tab_ana:
    ca1, ca2 = st.columns(2)
    with ca1:
        st.markdown("##### Correlación")
        # Filtramos columnas que sean todo 0 para no romper el heatmap
        cols_validas = [c for c in ['Confirmed', 'Deaths', 'Active', 'Recovered'] if df_temporal[c].sum() > 0]
        if len(cols_validas) > 1:
            fig_h, ax = plt.subplots(figsize=(5, 4))
            sns.heatmap(df_temporal[cols_validas].corr(), annot=True, cmap='coolwarm', ax=ax)
            st.pyplot(fig_h)
        else:
            st.warning("No hay suficientes variables variadas para correlación.")
            
    with ca2:
        st.markdown("##### Distribución")
        if tiene_datos_recuperados:
            datos_pie = pd.DataFrame({
                'Estado': ['Activos', 'Fallecidos', 'Recuperados'],
                'Cantidad': [ultimo['Active'], ultimo['Deaths'], ultimo['Recovered']]
            })
            fig_pie = px.pie(datos_pie, values='Cantidad', names='Estado', hole=0.4)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Gráfico de distribución no disponible (Faltan datos de recuperados).")
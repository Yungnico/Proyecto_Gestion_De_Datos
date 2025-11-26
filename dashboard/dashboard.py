import streamlit as st
import pandas as pd
import plotly.express as px
import ssl
import numpy as np
import requests
from io import StringIO
import concurrent.futures
import country_converter as coco  # <- para los continentes

# ---------------------------------------------------------
# CONFIG SSL (por si hay problemas de certificados HTTPS)
# ---------------------------------------------------------
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

st.set_page_config(page_title="Monitor COVID-19", layout="wide")

# ---------------------------------------------------------
# CONFIGURACIÓN DESCARGA DATOS (tipo PARTE 3 optimizada)
# ---------------------------------------------------------
url_base = "https://raw.githubusercontent.com/CSSEGISandData/COVID-19/master/csse_covid_19_data/csse_covid_19_daily_reports"

mapeo_columnas = {
    'Province/State': 'Province_State',
    'Country/Region': 'Country_Region',
    'Last Update': 'Last_Update',
    'Last_Update': 'Last_Update',
    'Lat': 'Lat',
    'Long_': 'Long_',
    'Confirmed': 'Confirmed',
    'Deaths': 'Deaths',
    'Recovered': 'Recovered',
    'Active': 'Active',
    'Combined_Key': 'Combined_Key',
    'Incident_Rate': 'Incident_Rate',
    'Incidence_Rate': 'Incident_Rate',
    'Case_Fatality_Ratio': 'Case_Fatality_Ratio',
    'Case-Fatality_Ratio': 'Case_Fatality_Ratio'
}

columnas_finales = list(set(mapeo_columnas.values()))

# estandarización básica de nombres de países
country_name_standardization = {
    "US": "United States",
    "Korea, North": "North Korea",
    "Korea, South": "South Korea",
    "Taiwan*": "Taiwan"
}

def procesar_reporte_diario(argumentos):
    """Descarga y limpia un reporte diario individual."""
    fecha, url = argumentos
    
    try:
        respuesta = requests.get(url, timeout=15)
        if respuesta.status_code != 200:
            return None, f"Status {respuesta.status_code}"

        # Intentar leer en utf-8 y si no, en latin-1
        try:
            datos_csv = StringIO(respuesta.text)
            df_dia = pd.read_csv(datos_csv, on_bad_lines='skip')
        except:
            try:
                datos_csv = StringIO(respuesta.content.decode('latin-1'))
                df_dia = pd.read_csv(datos_csv, on_bad_lines='skip')
            except Exception as e:
                return None, f"Error lectura: {e}"

        # 1. Normalizar nombres de columnas
        df_dia.rename(columns=mapeo_columnas, inplace=True)
        
        # 2. Quedarse sólo con columnas necesarias
        columnas_presentes = [c for c in columnas_finales if c in df_dia.columns]
        df_dia = df_dia[columnas_presentes]

        # 3. Llenar NaN en confirmados y muertos para poder filtrar
        for col in ['Confirmed', 'Deaths']:
            if col in df_dia.columns:
                df_dia[col] = df_dia[col].fillna(0)
            else:
                df_dia[col] = 0  

        # 4. Filtrar filas útiles (donde pasa algo)
        filas_validas = (df_dia['Confirmed'] > 0) | (df_dia['Deaths'] > 0)
        df_dia = df_dia[filas_validas]

        # 5. Filtrar filas sin país
        if 'Country_Region' in df_dia.columns:
            df_dia = df_dia.dropna(subset=['Country_Region'])

        # 6. Optimización de tipos numéricos
        for col in ['Confirmed', 'Deaths', 'Recovered', 'Active']:
            if col in df_dia.columns:
                df_dia[col] = pd.to_numeric(df_dia[col], downcast='integer')
        
        for col in ['Lat', 'Long_', 'Incident_Rate', 'Case_Fatality_Ratio']:
            if col in df_dia.columns:
                df_dia[col] = pd.to_numeric(df_dia[col], downcast='float')

        # Guardar fecha del archivo (por si se necesita)
        df_dia['fecha_archivo'] = fecha
        
        if df_dia.empty:
            return None, "Vacío tras filtro"

        return df_dia, None 

    except Exception as e:
        return None, f"Error de conexión: {e}"

def generar_urls_reportes(anio_inicio, anio_fin):
    """Genera lista de (fecha, url) entre dos años."""
    urls_a_procesar = []
    rango_fechas = pd.date_range(start=f'{anio_inicio}-01-01', end=f'{anio_fin}-12-31')
    
    for fecha in rango_fechas:
        formato = fecha.strftime('%m-%d-%Y')
        url = f"{url_base}/{formato}.csv"
        urls_a_procesar.append((fecha, url))
    
    return urls_a_procesar

def agregar_continente(df):
    """Agrega la columna Continent usando country_converter, optimizado."""
    if 'Country_Region' not in df.columns:
        return df
    
    # Estandarizar algunos nombres raros
    df['Country_Region'] = df['Country_Region'].replace(country_name_standardization)

    # Lista de países únicos (máx ~200)
    unique_countries = df['Country_Region'].astype(str).unique()

    # Convertimos solo esa lista pequeña
    continents_list = coco.convert(names=unique_countries, to='continent', not_found=None)

    # Diccionario país -> continente
    country_to_continent_map = dict(zip(unique_countries, continents_list))

    # Mapear a toda la columna
    df['Continent'] = df['Country_Region'].astype(str).map(country_to_continent_map)
    df['Continent'] = df['Continent'].fillna('Other')

    return df

def descargar_datos_covid(anio_inicio=2021, anio_fin=2022):
    """Descarga todos los reportes diarios y devuelve un único DataFrame limpio."""
    tareas_descarga = generar_urls_reportes(anio_inicio, anio_fin)
    dataframes_descargados = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ejecutor:
        resultados_descarga = ejecutor.map(procesar_reporte_diario, tareas_descarga)
        
        for (fecha, url), (df_dia, error) in zip(tareas_descarga, resultados_descarga):
            if df_dia is not None:
                dataframes_descargados.append(df_dia)

    if not dataframes_descargados:
        return pd.DataFrame()
    
    datos_covid_anuales = pd.concat(dataframes_descargados, ignore_index=True)
    
    # Limpieza final por si quedan NaN
    columnas_enteras = ['Confirmed', 'Deaths', 'Recovered', 'Active']
    for col in columnas_enteras:
        if col in datos_covid_anuales.columns:
            datos_covid_anuales[col] = datos_covid_anuales[col].fillna(0).astype('int32')

    # Asegurarnos de que exista 'Last_Update'
    if 'Last_Update' not in datos_covid_anuales.columns:
        datos_covid_anuales['Last_Update'] = datos_covid_anuales['fecha_archivo']

    # Agregar continente
    datos_covid_anuales = agregar_continente(datos_covid_anuales)

    return datos_covid_anuales

# ---------------------------------------------------------
# FUNCIÓN DEL DASHBOARD PARA CARGAR DATOS (sin CSV)
# ---------------------------------------------------------
@st.cache_data
def load_data():
    df = descargar_datos_covid(2021, 2022)
    if df.empty:
        return pd.DataFrame()

    df.columns = df.columns.str.strip()
        
    col_fecha = 'Last_Update' if 'Last_Update' in df.columns else 'Date'
    df['Date'] = pd.to_datetime(df[col_fecha], errors='coerce').dt.normalize()
    df = df.dropna(subset=['Date'])

    cols = ['Confirmed', 'Deaths', 'Recovered', 'Active']
    for col in cols:
        if col not in df.columns:
            df[col] = 0
        else:
            if df[col].dtype == 'object':
                df[col] = df[col].astype(str).str.replace(',', '').str.strip()
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    def balance_mass(row):
        conf = row['Confirmed']
        death = row['Deaths']
        act = row['Active']
        rec = row['Recovered']
        
        if act == 0 and conf > 0:
            calc_act = conf - death - rec
            return max(0, calc_act)
        return act

    df['Active'] = df.apply(balance_mass, axis=1)
    df['Recovered'] = df['Recovered'].clip(lower=0)
    df['Active'] = df['Active'].clip(lower=0)

    return df

# ---------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------
df = load_data()

if df.empty:
    st.error("Error: No hay datos cargados.")
    st.stop()

st.title("Monitor Epidemiológico COVID-19")
st.markdown("---")

with st.container(border=True):
    c1, c2, c3 = st.columns(3)
    
    if 'Continent' in df.columns:
        cont_list = sorted([str(x) for x in df['Continent'].dropna().unique()])
        sel_cont = c1.multiselect("Filtro Continente", cont_list, default=cont_list)
        df_geo = df[df['Continent'].astype(str).isin(sel_cont)] if sel_cont else df
    else:
        df_geo = df
        
    paises = ["Todos"] + sorted(df_geo['Country_Region'].unique())
    sel_pais = c2.selectbox("Filtro País", paises)
    
    min_d, max_d = df_geo['Date'].min(), df_geo['Date'].max()
    fechas = c3.date_input("Rango de Análisis", [min_d, max_d], min_value=min_d, max_value=max_d)

mask = (df_geo['Date'] >= pd.to_datetime(fechas[0])) & (df_geo['Date'] <= pd.to_datetime(fechas[1]))
df_filt = df_geo.loc[mask].sort_values('Date')

if df_filt.empty:
    st.warning("No hay datos en el rango seleccionado.")
    st.stop()

numeric_cols = ['Confirmed', 'Deaths', 'Recovered', 'Active']

# ---------------------------------------------------------
# APLICAR FILTROS A SERIES / MAPA / RANKING
# ---------------------------------------------------------
if sel_pais == "Todos":
    # Curvas globales: sumar por día
    df_temporal = (
        df_filt
        .groupby('Date')[numeric_cols]
        .sum()
        .reset_index()
    )

    # Datos por país:
    # - último dato del rango
    df_last = (
        df_filt
        .sort_values('Date')
        .groupby('Country_Region')
        .tail(1)
    )[['Country_Region'] + numeric_cols]

    # - acumulado en el rango
    df_acum = (
        df_filt
        .groupby('Country_Region')[numeric_cols]
        .sum()
        .reset_index()
    )

    label_scope = "Global"
else:
    df_country = df_filt[df_filt['Country_Region'] == sel_pais]

    df_temporal = (
        df_country
        .groupby('Date')[numeric_cols]
        .sum()
        .reset_index()
    )

    df_last = (
        df_country
        .sort_values('Date')
        .groupby('Country_Region')
        .tail(1)
    )[['Country_Region'] + numeric_cols]

    df_acum = (
        df_country
        .groupby('Country_Region')[numeric_cols]
        .sum()
        .reset_index()
    )

    label_scope = sel_pais

# ---------------------------------------------------------
# SWITCH: ÚLTIMO DATO vs ACUMULADO EN EL RANGO
# ---------------------------------------------------------
modo_totales = st.radio(
    "Modo de resumen de totales",
    ("Último dato del rango", "Acumulado en el rango"),
    horizontal=True
)

if modo_totales == "Último dato del rango":
    total_stats = df_temporal[['Confirmed', 'Deaths', 'Recovered', 'Active']].iloc[-1]
    titulo_totales = f"Totales al último día del rango: {label_scope}"
    df_map_sum = df_last
    mapa_suffix = "Último dato del rango"
    ranking_suffix = "al último día del rango"
else:
    total_stats = df_temporal[['Confirmed', 'Deaths', 'Recovered', 'Active']].sum()
    titulo_totales = f"Totales acumulados en el rango: {label_scope}"
    df_map_sum = df_acum
    mapa_suffix = "Acumulados en el rango"
    ranking_suffix = "acumulados en el rango"

# ---------------------------------------------------------
# REBROTE (SIEMPRE PRIMER vs ÚLTIMO DÍA)
# ---------------------------------------------------------
activos_inicio = df_temporal.iloc[0]['Active']
activos_fin = df_temporal.iloc[-1]['Active']
variacion_activos = activos_fin - activos_inicio

if variacion_activos > 0:
    estado_rebrote = "EN AUMENTO"
    color_txt = "red"
    mensaje_rebrote = f"Se sumaron +{int(variacion_activos):,} casos activos nuevos netos."
elif variacion_activos < 0:
    estado_rebrote = "EN RETROCESO"
    color_txt = "green"
    mensaje_rebrote = f"Los casos activos bajaron en {abs(int(variacion_activos)):,}."
else:
    estado_rebrote = "ESTABLE"
    color_txt = "gray"
    mensaje_rebrote = "La cantidad de activos se mantiene igual."

# Tasa de letalidad usando los totales según el modo elegido
tasa_letalidad = (
    total_stats['Deaths'] / total_stats['Confirmed'] * 100
    if total_stats['Confirmed'] > 0 else 0
)

st.subheader(titulo_totales)
k1, k2, k3, k4 = st.columns(4)
k1.metric("Confirmados", f"{int(total_stats['Confirmed']):,}")
k2.metric("Activos Totales", f"{int(total_stats['Active']):,}")
k3.metric("Fallecidos", f"{int(total_stats['Deaths']):,}")
k4.metric("Recuperados", f"{int(total_stats['Recovered']):,}")

st.divider()

col_let, col_reb = st.columns(2)

with col_let:
    with st.container(border=True):
        st.markdown("#### Tasa de Letalidad")
        st.metric("Fallecidos vs Confirmados", f"{tasa_letalidad:.2f}%")
        
        if tasa_letalidad > 3:
            st.error("Nivel Crítico: Superior al promedio estándar.")
        elif tasa_letalidad > 1.5:
            st.warning("Nivel Alto: Mortalidad considerable.")
        else:
            st.success("Nivel Bajo: Mortalidad controlada.")

with col_reb:
    with st.container(border=True):
        st.markdown("#### Rebrote Primer resultado - Últimos acumulados (Tendencia)")
        st.markdown(f":{color_txt}[**{estado_rebrote}**]")
        st.write(f"Inicio: {int(activos_inicio):,} activos -> Fin: {int(activos_fin):,} activos")
        st.caption(mensaje_rebrote)

st.divider()

tab1, tab2, tab3 = st.tabs(["Curvas", "Mapa", "Ranking"])

with tab1:
    fig_line = px.line(
        df_temporal, 
        x='Date', 
        y=['Confirmed', 'Active', 'Deaths', 'Recovered'],
        title="Tendencia Temporal",
        markers=True
    )
    st.plotly_chart(fig_line, use_container_width=True)

with tab2:
    if sel_pais == "Todos":
        c_opt, c_map = st.columns([1, 3])
        with c_opt:
            var_map = st.radio("Métrica Mapa:", ["Confirmed", "Active", "Deaths"])
        with c_map:
            fig_map = px.choropleth(
                df_map_sum,
                locations="Country_Region",
                locationmode="country names",
                color=var_map,
                hover_name="Country_Region",
                color_continuous_scale="Reds" if var_map == "Deaths" else "Plasma",
                title=f"{mapa_suffix}: {var_map}"
            )
            st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.info("Selecciona 'Todos' en el filtro de país para ver el mapa global.")

with tab3:
    top_n = df_map_sum.nlargest(10, 'Confirmed').sort_values('Confirmed', ascending=True)
    fig_bar = px.bar(
        top_n,
        x='Confirmed',
        y='Country_Region',
        orientation='h',
        text_auto='.2s',
        title=f"Top 10 Países (Confirmados {ranking_suffix})",
        color='Confirmed',
        color_continuous_scale='Viridis'
    )
    st.plotly_chart(fig_bar, use_container_width=True)

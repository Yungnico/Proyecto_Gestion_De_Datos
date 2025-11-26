import streamlit as st
import pandas as pd
import plotly.express as px
import ssl
import numpy as np

try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

st.set_page_config(page_title="Monitor COVID-19", layout="wide")

@st.cache_data
def load_data():
    try:
        df = pd.read_csv('covid_final_dashboard.csv', thousands=',')
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
    except FileNotFoundError:
        return pd.DataFrame()

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
    
    min_d, max_d = df['Date'].min(), df['Date'].max()
    fechas = c3.date_input("Rango de Análisis", [min_d, max_d], min_value=min_d, max_value=max_d)

mask = (df_geo['Date'] >= pd.to_datetime(fechas[0])) & (df_geo['Date'] <= pd.to_datetime(fechas[1]))
df_filt = df_geo.loc[mask].sort_values('Date')

if df_filt.empty:
    st.warning("No hay datos en el rango seleccionado.")
    st.stop()

if sel_pais == "Todos":
    df_temporal = df_filt.groupby('Date')[['Confirmed', 'Deaths', 'Recovered', 'Active']].sum().reset_index()
    df_map_sum = df_filt.groupby('Country_Region')[['Confirmed', 'Deaths', 'Recovered', 'Active']].sum().reset_index()
    label_scope = "Global"
else:
    df_temporal = df_filt[df_filt['Country_Region'] == sel_pais].groupby('Date').sum().reset_index()
    df_map_sum = df_filt[df_filt['Country_Region'] == sel_pais].groupby('Country_Region')[['Confirmed', 'Deaths', 'Recovered', 'Active']].sum().reset_index()
    label_scope = sel_pais

total_stats = df_temporal[['Confirmed', 'Deaths', 'Recovered', 'Active']].sum()

start_conf = df_temporal.iloc[0]['Confirmed']
end_conf = df_temporal.iloc[-1]['Confirmed']
growth_rate = ((end_conf - start_conf) / start_conf * 100) if start_conf > 0 else 0

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

tasa_letalidad = (total_stats['Deaths'] / total_stats['Confirmed'] * 100) if total_stats['Confirmed'] > 0 else 0

st.subheader(f"Totales Acumulados: {label_scope}")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Confirmados", f"{int(total_stats['Confirmed']):,}", f"{growth_rate:.2f}% Crecimiento")
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
        st.markdown("#### Dinámica de Contagio (Tendencia)")
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
        markers=True, 
        log_y=True
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
                color_continuous_scale="Reds" if var_map=="Deaths" else "Plasma",
                title=f"Volumen Total: {var_map}"
            )
            st.plotly_chart(fig_map, use_container_width=True)
    else:
        st.info("Selecciona Todos en el filtro para ver el mapa global.")

with tab3:
    top_n = df_map_sum.nlargest(10, 'Confirmed').sort_values('Confirmed', ascending=True)
    fig_bar = px.bar(
        top_n,
        x='Confirmed',
        y='Country_Region',
        orientation='h',
        text_auto='.2s',
        title="Top 10 Países (Volumen de Confirmados)",
        color='Confirmed',
        color_continuous_scale='Viridis'
    )
    st.plotly_chart(fig_bar, use_container_width=True)
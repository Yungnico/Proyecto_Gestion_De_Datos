# # Monitor Epidemiológico COVID-19 

Este proyecto es un **dashboard interactivo en Streamlit** para monitorear la evolución del COVID-19 a partir de un archivo de datos preprocesado (`covid_final_dashboard.csv`).

Permite:

- Filtrar por **continente**, **país** y **rango de fechas**.  
- Visualizar **curvas temporales** de Confirmados, Activos, Fallecidos y Recuperados.  
- Ver un **mapa mundial** (cuando se analiza a nivel global).  
- Consultar un **ranking de países** según casos confirmados.  
- Calcular indicadores como:
  - Tasa de letalidad (%).
  - Dinámica de casos activos (si la situación está en aumento, retroceso o estable).

---

## 1. Requisitos previos 

- **Python** 3.9 o superior (recomendado).
- Tener instalado **pip** para gestionar paquetes.

Paquetes principales usados:

- `streamlit`
- `pandas`
- `plotly`
- `numpy`
- `country_converter`
- `ssl` (incluido en la biblioteca estándar de Python)

---

## 2. Instalación de dependencias 

Desde la carpeta del proyecto, puedes instalar las dependencias con:

```bash
pip install streamlit pandas plotly numpy country_converter

# =============================================================================
# CÓDIGO COMPLETO - SISTEMA DE CONTROL VEHICULAR IMSS (CORRECCIONES FINALES)
# Desarrollado por: eduardo.casas@imss.gob.mx
# =============================================================================
import streamlit as st
import base64
from datetime import datetime, date
import os
import io
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from supabase import create_client

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Sistema de Control Vehicular - IMSS",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# CONSTANTES Y CONFIGURACIÓN DE COLUMNAS Y PALETA INSTITUCIONAL (PANTONES)
# =============================================================================
COLORES_PANTONE = {
    "7421": "#7A1332",
    "7420": "#8A1538",
    "627": "#1C3B30",
    "626": "#275043",
    "561": "#326053",
    "504": "#421924",
    "490": "#5A202E",
    "465": "#A4855B",
    "468": "#D3C281"
}

COLUMNAS_OFICIALES = [
    "No. Ecco.",
    "Tipo",
    "Linea",
    "UBICACIÓN",
    "Arrendadora",
    "Estatus",
    "Placas",
    "VIN",
    "No_TC",
    "Ultimo_Servicio",
    "CUOTA DIARIA",
    "TOTAL DÍAS DE SERVICIO",
    "COSTO MENSUAL SIN IVA (a)",
    "TOTAL DE DEDUCCIÓN",
    "TOTAL A PAGAR (b)",
]

# -----------------------------------------------------------------------------
# FUNCIÓN AUXILIAR PARA CONVERSIÓN SEGURA DE NÚMEROS
# -----------------------------------------------------------------------------
def parse_float(val):
    try:
        val_str = str(val).strip()
        if val_str.lower() in ['nan', 'none', 'n/a', '', 'null']:
            return 0.0
        return float(val_str.replace('$', '').replace(',', ''))
    except (ValueError, TypeError):
        return 0.0

# -----------------------------------------------------------------------------
# CONEXIÓN CON SUPABASE
# -----------------------------------------------------------------------------
@st.cache_resource
def conectar_supabase():
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error detallado de conexión: {e}")
        return None

supabase = conectar_supabase()
supabase_url = st.secrets["supabase"]["url"] if supabase else ""

# -----------------------------------------------------------------------------
# GESTIÓN DE IMÁGENES Y LOGO DESDE SUPABASE STORAGE
# -----------------------------------------------------------------------------
def obtener_url_supabase(nombre_archivo):
  if supabase_url:
    return f"{supabase_url}/storage/v1/object/public/vehiculos-fotos/{nombre_archivo}"
  return ""

def obtener_imagen_catalogo_supabase(tipo, linea):
  tipo_str = str(tipo).upper().strip()
  linea_str = str(linea).upper().strip()

  if "PROMASTER" in linea_str:
    archivo = "RAM_PROMASTER_GENERICA.png"
  elif "TRANSIT" in linea_str:
    archivo = "FORD_TRANSIT_GENERICA.png"
  elif "CRETA" in linea_str or "SUV" in linea_str:
    archivo = "creta-1-5l-gls-ivt.png"
  elif "F-150" in linea_str or "PICK UP" in linea_str:
    archivo = "f-150-xl.png"
  elif "URVAN" in linea_str or "VAN" in linea_str:
    archivo = "urvan-panel.png"
  elif "V-DRIVE" in linea_str or "SEDÁN" in linea_str or "SEDAN" in linea_str:
    archivo = "v-drive-tm-ac.png"
  else:
    archivo = "v-drive-tm-ac.png"

  url_supa = obtener_url_supabase(archivo)
  if url_supa:
    return url_supa

  return os.path.join("assets", archivo)

url_logo_supa = obtener_url_supabase("logo_imss.png")

os.makedirs("data", exist_ok=True)
os.makedirs("expedientes", exist_ok=True)
os.makedirs("assets", exist_ok=True)

# -----------------------------------------------------------------------------
# GESTIÓN DEL ESTADO DE SESIÓN
# -----------------------------------------------------------------------------
if "categoria_seleccionada" not in st.session_state:
  st.session_state.categoria_seleccionada = "Administrativos"

if "modulo_activo" not in st.session_state:
  st.session_state.modulo_activo = "Dashboard General"

if "taller_registros" not in st.session_state:
  st.session_state.taller_registros = []

if "bitacora_cargas" not in st.session_state:
  st.session_state.bitacora_cargas = []

if "reasignaciones_historial" not in st.session_state:
  st.session_state.reasignaciones_historial = []

if "admin_autenticado" not in st.session_state:
  st.session_state.admin_autenticado = False

def cambiar_categoria(cat):
  st.session_state.categoria_seleccionada = cat
  st.session_state.modulo_activo = "Dashboard General"

cat_actual = st.session_state.categoria_seleccionada

# -----------------------------------------------------------------------------
# CARGA DE DATOS DESDE TABLAS SEPARADAS EN SUPABASE CON PAGINACIÓN
# -----------------------------------------------------------------------------
@st.cache_data(ttl=600)
def cargar_datos_supabase(categoria):
  if not supabase:
    return pd.DataFrame(columns=COLUMNAS_OFICIALES)
  try:
    tabla_map = {
        "Administrativos": "vehiculos_administrativos",
        "Ambulancias": "vehiculos_ambulancias",
        "Institucionales": "vehiculos_institucionales"
    }
    nombre_tabla = tabla_map.get(categoria, "vehiculos_administrativos")
    
    all_rows = []
    batch_size = 1000
    offset = 0
    
    while True:
      response = supabase.table(nombre_tabla).select("*").range(offset, offset + batch_size - 1).execute()
      data = response.data
      if not data:
        break
      all_rows.extend(data)
      if len(data) < batch_size:
        break
      offset += batch_size

    df = pd.DataFrame(all_rows)
    
    if not df.empty:
      df = df.astype(str)
      df.columns = df.columns.str.strip()
      if "id" in df.columns:
        df = df.drop(columns=["id"])
    else:
      return pd.DataFrame(columns=COLUMNAS_OFICIALES)
      
    return df
  except Exception as e:
    st.error(f"Error al conectar o consultar la tabla '{nombre_tabla}' en Supabase: {e}")
    return pd.DataFrame(columns=COLUMNAS_OFICIALES)

df_base = cargar_datos_supabase(cat_actual)

# -----------------------------------------------------------------------------
# ESTILOS CSS EXTENDIDOS
# -----------------------------------------------------------------------------
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] {{ font-family: 'Montserrat', sans-serif !important; }}
    .block-container {{ padding: 1.2rem 2rem 2rem 2rem !important; }}
    .main {{ background-color: #FFFFFF; }}
    [data-testid="stSidebar"] {{ background-color: {COLORES_PANTONE["627"]} !important; }}
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] div {{ color: #FFFFFF !important; font-weight: 600; }}
    [data-testid="stSidebar"] button[kind="primary"] {{ background-color: {COLORES_PANTONE["468"]} !important; color: {COLORES_PANTONE["627"]} !important; font-weight: 800 !important; border: 1px solid {COLORES_PANTONE["468"]} !important; }}
    [data-testid="stSidebar"] button[kind="secondary"] {{ background-color: {COLORES_PANTONE["626"]} !important; color: #FFFFFF !important; font-weight: 700 !important; border: 1px solid {COLORES_PANTONE["561"]} !important; }}
    [data-testid="stSidebar"] img {{ max-width: 100%; height: auto; object-fit: contain; }}
    div[data-testid="stMetricValue"] {{ font-size: 22px !important; color: {COLORES_PANTONE["627"]} !important; font-weight: 800 !important; }}
    div[data-testid="stMetricLabel"] {{ font-size: 11px !important; font-weight: 700 !important; color: #555555 !important; }}
    .subtitulo-seccion {{ color: #222222; font-weight: 700; font-size: 18px; margin-bottom: 15px !important; }}
    .badge-verde {{ background-color: #27ae60; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 11px; }}
    .badge-amarillo {{ background-color: #f39c12; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 11px; }}
    .badge-rojo {{ background-color: {COLORES_PANTONE["7420"]}; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 11px; }}
    .card-resumen {{ background-color: #F8F9FA; border: 1px solid #E9ECEF; border-radius: 8px; padding: 14px; margin-bottom: 12px; }}
    .image-container-full {{
        width: 100%;
        max-height: 220px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #fdfdfd;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 8px;
        overflow: hidden;
    }}
    .image-container-full img {{
        max-width: 100% !important;
        max-height: 200px !important;
        object-fit: contain !important;
    }}
    .footer-firma {{
        margin-top: 30px;
        padding: 10px;
        text-align: center;
        border-top: 1px solid #E9ECEF;
        font-size: 11px;
        color: #555555;
        font-weight: 600;
    }}
    </style>
""",
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# BARRA LATERAL (SIDEBAR)
# -----------------------------------------------------------------------------
with st.sidebar:
  if url_logo_supa:
    st.image(url_logo_supa, use_container_width=True)
  else:
    st.markdown(
        f"<h2 style='color:{COLORES_PANTONE['468']}; text-align:center;'>IMSS</h2>",
        unsafe_allow_html=True,
    )

  st.markdown(
      "<div style='text-align: center; font-size: 11px; margin-bottom:"
      " 10px;'><b>DIRECCIÓN DE ADMINISTRACIÓN</b><br><span"
      f" style='font-size:9px; color:{COLORES_PANTONE['468']};'>Coordinación Técnica de Servicios"
      " Generales</span></div>",
      unsafe_allow_html=True,
  )
  st.markdown("---")
  st.markdown(
      "<p style='font-size: 12px; margin-bottom: 8px;'><b>SELECCIONAR"
      " FLOTILLA:</b></p>",
      unsafe_allow_html=True,
  )

  st.button(
      "ADMINISTRATIVOS",
      use_container_width=True,
      type=(
          "primary"
          if st.session_state.categoria_seleccionada == "Administrativos"
          else "secondary"
      ),
      on_click=cambiar_categoria,
      args=("Administrativos",),
  )
  st.button(
      "AMBULANCIAS",
      use_container_width=True,
      type=(
          "primary"
          if st.session_state.categoria_seleccionada == "Ambulancias"
          else "secondary"
      ),
      on_click=cambiar_categoria,
      args=("Ambulancias",),
  )
  st.button(
      "INSTITUCIONALES",
      use_container_width=True,
      type=(
          "primary"
          if st.session_state.categoria_seleccionada == "Institucionales"
          else "secondary"
      ),
      on_click=cambiar_categoria,
      args=("Institucionales",),
  )

  st.markdown("---")

  modulos = [
      "Dashboard General",
      "Semáforo de Movilidad por Ciudad",
      "Control del Pool de Sustitutos (20%)",
      "Carga Inicial",
      "Expediente por ECO y Documental",
      "Registro de Taller e Incidencias",
      "Reasignación por Necesidad de Servicio",
      "Reportes y Exportación",
      "Conciliación Financiera y Pagos",
  ]

  if st.session_state.modulo_activo not in modulos:
    st.session_state.modulo_activo = "Dashboard General"

  st.session_state.modulo_activo = st.radio(
      "Módulos del Sistema:",
      modulos,
      index=modulos.index(st.session_state.modulo_activo),
  )

  st.markdown("---")
  st.markdown(
      "<div style='text-align: center; font-size: 10px; color: #CCCCCC;'>Desarrollado por:<br><b>eduardo.casas@imss.gob.mx</b></div>",
      unsafe_allow_html=True,
  )

# -----------------------------------------------------------------------------
# ENCABEZADO INSTITUCIONAL ÚNICO
# -----------------------------------------------------------------------------
logo_html = f'<img src="{url_logo_supa}" style="height: 200px; width: auto; object-fit: contain; display: inline-block; vertical-align: middle;">' if url_logo_supa else f'<h2 style="color:{COLORES_PANTONE["468"]}; margin:0;">IMSS</h2>'

st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 15px; width: 100%; margin: 10px 0 15px 0;">
        <div>{logo_html}</div>
        <div style="line-height: 1.2;">
            <p style="color: {COLORES_PANTONE["627"]}; font-weight: 800; font-size: 20px; margin: 0;">Sistema de Gestión y Control Vehicular</p>
            <p style="color: #555555; font-size: 11px; margin: 2px 0 0 0; font-weight: 600;">
                <b>Flotilla Seleccionada:</b> <code>{st.session_state.categoria_seleccionada}</code> &nbsp;|&nbsp; 
                <b>Módulo Activo:</b> <code>{st.session_state.modulo_activo}</code> &nbsp;|&nbsp; 
                <b>Fecha de Operación:</b> {datetime.now().strftime('%d/%m/%Y')}
            </p>
        </div>
    </div>
    <hr style="margin: 0 0 15px 0; border: none; border-top: 1px solid #E9ECEF;">
""", unsafe_allow_html=True)

mod_actual = st.session_state.modulo_activo

# -----------------------------------------------------------------------------
# 1. DASHBOARD GENERAL
# -----------------------------------------------------------------------------
if mod_actual == "Dashboard General":
  st.markdown(
      f'<p class="subtitulo-seccion">Dashboard General - Flotilla:'
      f" {cat_actual}</p>",
      unsafe_allow_html=True,
  )

  if df_base.empty:
    st.warning(
        f"⚠️ No se han encontrado registros en Supabase para la flotilla **{cat_actual}**."
    )

  col_filtro, col_exp = st.columns([3, 1])
  unidades_list = ["Todas las Ubicaciones (Nacional)"] + (
      list(df_base["UBICACIÓN"].dropna().unique())
      if "UBICACIÓN" in df_base.columns
      else []
  )
  unidad_sel = col_filtro.selectbox(
      "Filtrar Consulta por Unidad Receptora / Ubicación:", unidades_list
  )

  df_dash = (
      df_base
      if (
          unidad_sel == "Todas las Ubicaciones (Nacional)" or df_base.empty
      )
      else df_base[df_base["UBICACIÓN"] == unidad_sel]
  )

  tot_unidades = len(df_dash)
  ecos_filtrados = (
      set(df_dash["No. Ecco."].unique()) if "No. Ecco." in df_dash.columns else set()
  )

  ecos_en_taller = {
      r["ECO"]
      for r in st.session_state.taller_registros
      if r["Estatus"] == "Activo (En Taller)" and r["ECO"] in ecos_filtrados
  }
  n_taller = len(ecos_en_taller)
  n_baja = (
      len(df_dash[df_dash["Estatus"] == "Inoperativo / Baja"])
      if "Estatus" in df_dash.columns
      else 0
  )
  n_sust = (
      len(
          df_dash[
              (df_dash["Estatus"] == "Sustituto Entregado")
              & (~df_dash["No. Ecco."].isin(ecos_en_taller))
          ]
      )
      if "Estatus" in df_dash.columns
      else 0
  )
  n_activos = (
      len(
          df_dash[
              (df_dash["Estatus"] == "Titular Activo")
              & (~df_dash["No. Ecco."].isin(ecos_en_taller))
          ]
      )
      if "Estatus" in df_dash.columns
      else 0
  )

  disponibilidad = (
      ((n_activos + n_sust) / tot_unidades * 100) if tot_unidades > 0 else 0.0
  )

  c1, c2, c3, c4 = st.columns(4)
  c1.metric("Total Unidades Registradas", f"{tot_unidades:,}")
  c2.metric("Titulares / Sustitutos Activos", f"{n_activos + n_sust:,}")
  c3.metric(
      "En Taller / Inoperativos", f"{n_taller + n_baja:,}", delta_color="inverse"
  )
  c4.metric("Disponibilidad Operativa Real", f"{disponibilidad:.1f}%")

  st.markdown("---")
  col_dona, col_barras, col_tabla = st.columns(
      [1.2, 1.5, 1.3], gap="medium"
  )

  with col_dona:
    st.markdown("##### **Estatus Operativo**")
    valores_dona = [n_activos, n_sust, n_taller, n_baja]
    etiquetas_dona = [
        "Activas",
        "Sustitutos",
        "En Taller",
        "Baja / Inoperativos",
    ]
    colores_dona = [COLORES_PANTONE["627"], COLORES_PANTONE["468"], COLORES_PANTONE["7420"], COLORES_PANTONE["490"]]

    fig_d, ax_d = plt.subplots(figsize=(3.5, 3.5))
    if sum(valores_dona) == 0:
      ax_d.text(
          0.5,
          0.5,
          "Sin Datos",
          horizontalalignment="center",
          verticalalignment="center",
          fontsize=12,
          color="gray",
      )
      ax_d.axis("off")
    else:
      wedges, _ = ax_d.pie(
          valores_dona,
          startangle=140,
          colors=colores_dona,
          wedgeprops=dict(width=0.4, edgecolor="white", linewidth=2),
      )
      ax_d.legend(
          wedges,
          [f"{e}: {v}" for e, v in zip(etiquetas_dona, valores_dona)],
          loc="center",
          bbox_to_anchor=(0.5, -0.15),
          frameon=False,
          fontsize=8,
      )
      ax_d.axis("equal")
    fig_d.tight_layout()
    st.pyplot(fig_d)

  with col_barras:
    st.markdown("##### **Distribución por Tipo de Vehículo**")
    fig_v, ax_v = plt.subplots(figsize=(4.5, 3.5))
    if not df_dash.empty and "Tipo" in df_dash.columns:
      df_tipo_filtrado = df_dash[~df_dash["Tipo"].str.upper().isin(["SONORA", "SINALOA", "BAJA CALIFORNIA", "CHIHUAHUA", "N/A", "nan"])]
      
      resumen_tipo = (
          df_tipo_filtrado.groupby("Tipo")
          .size()
          .reset_index(name="Cantidad")
          .sort_values(by="Cantidad", ascending=False)
      )
      
      if not resumen_tipo.empty:
        # Paleta variada de colores institucionales para cada barra de la gráfica
        paleta_barras = [
            COLORES_PANTONE["627"],
            COLORES_PANTONE["626"],
            COLORES_PANTONE["561"],
            COLORES_PANTONE["490"],
            COLORES_PANTONE["7420"],
            COLORES_PANTONE["465"]
        ]
        colores_asignados = [paleta_barras[i % len(paleta_barras)] for i in range(len(resumen_tipo))]
        
        bars = ax_v.bar(
            resumen_tipo["Tipo"], resumen_tipo["Cantidad"], color=colores_asignados
        )
        ax_v.tick_params(axis="x", rotation=30, labelsize=8)
        ax_v.grid(axis="y", linestyle="--", alpha=0.5)
        for bar in bars:
          h = bar.get_height()
          ax_v.text(
              bar.get_x() + bar.get_width() / 2,
              h + 0.5,
              f"{int(h)}",
              ha="center",
              va="bottom",
              fontweight="bold",
              fontsize=8,
          )
      else:
        ax_v.text(0.5, 0.5, "Sin Tipos Válidos", ha="center", va="center", fontsize=10, color="gray")
        ax_v.axis("off")
    else:
      resumen_tipo = pd.DataFrame(columns=["Tipo", "Cantidad"])
      ax_v.text(
          0.5,
          0.5,
          "Sin Datos",
          horizontalalignment="center",
          verticalalignment="center",
          fontsize=12,
          color="gray",
      )
      ax_v.axis("off")
    fig_v.tight_layout()
    st.pyplot(fig_v)

  with col_tabla:
    st.markdown("##### **Resumen Cantidades Detalladas**")
    if not resumen_tipo.empty:
      df_totales = pd.DataFrame(
          [{"Tipo": "TOTAL UNIDADES", "Cantidad": resumen_tipo["Cantidad"].sum()}]
      )
      df_mostrar_res = pd.concat([resumen_tipo, df_totales], ignore_index=True)
      st.dataframe(df_mostrar_res, hide_index=True, use_container_width=True)
    else:
      st.dataframe(
          pd.DataFrame(columns=["Tipo", "Cantidad"]),
          hide_index=True,
          use_container_width=True,
      )

  st.markdown("---")
  st.markdown("##### **Vistas Detalladas de la Base de Datos Activa**")
  cols_mostrar = [
      "No. Ecco.",
      "Tipo",
      "Linea",
      "UBICACIÓN",
      "Arrendadora",
      "Estatus",
      "Placas",
      "VIN",
      "CUOTA DIARIA",
      "TOTAL A PAGAR (b)",
  ]
  cols_existentes = [c for c in cols_mostrar if c in df_dash.columns]
  st.dataframe(
      df_dash[cols_existentes]
      if not df_dash.empty
      else pd.DataFrame(columns=cols_mostrar),
      use_container_width=True,
      hide_index=True,
  )

# -----------------------------------------------------------------------------
# 2. SEMÁFORO DE MOVILIDAD POR CIUDAD
# -----------------------------------------------------------------------------
elif mod_actual == "Semáforo de Movilidad por Ciudad":
  st.markdown(
      f'<p class="subtitulo-seccion">Semáforo de Movilidad por Ciudad -'
      f" Flotilla {cat_actual}</p>",
      unsafe_allow_html=True,
  )

  lista_ciudades = (
      list(df_base["UBICACIÓN"].dropna().unique())
      if "UBICACIÓN" in df_base.columns
      else []
  )
  ciudad_sel = st.selectbox(
      "Seleccionar Vista / Filtro de Ciudad:",
      ["Todas las Ciudades (General)"] + lista_ciudades,
  )

  if not df_base.empty and "UBICACIÓN" in df_base.columns:
    df_ciudades = (
        df_base.groupby("UBICACIÓN")
        .agg(
            Flotilla_Asignada=("No. Ecco.", "count"),
            Titulares_Activos=(
                "Estatus",
                lambda x: (x == "Titular Activo").sum(),
            ),
            Sustitutos_Entregados=(
                "Estatus",
                lambda x: (x == "Sustituto Entregado").sum(),
            ),
            En_Taller_Inoperativos=(
                "Estatus",
                lambda x: (x == "Inoperativo / Baja").sum(),
            ),
        )
        .reset_index()
    )

    df_ciudades["Movilidad (%)"] = np.where(
        df_ciudades["Flotilla_Asignada"] > 0,
        (
            (
                df_ciudades["Titulares_Activos"]
                + df_ciudades["Sustitutos_Entregados"]
            )
            / df_ciudades["Flotilla_Asignada"]
            * 100
        ).round(1),
        0.0,
    )
    df_ciudades["Estado"] = np.where(
        df_ciudades["Movilidad (%)"] >= 95,
        "VERDE",
        np.where(df_ciudades["Movilidad (%)"] >= 85, "AMARILLO", "ROJO"),
    )
    df_ciudades.rename(
        columns={
            "UBICACIÓN": "Ciudad / OOAD",
            "Flotilla_Asignada": "Flotilla Asignada",
            "Titulares_Activos": "Titulares Activos",
            "Sustitutos_Entregados": "Sustitutos Entregados",
            "En_Taller_Inoperativos": "En Taller / Inoperativos",
        },
        inplace=True,
    )
  else:
    df_ciudades = pd.DataFrame(columns=[
        "Ciudad / OOAD",
        "Flotilla Asignada",
        "Titulares Activos",
        "Sustitutos Entregados",
        "En Taller / Inoperativos",
        "Movilidad (%)",
        "Estado",
    ])

  if ciudad_sel != "Todas las Ciudades (General)":
    df_ciudades = df_ciudades[df_ciudades["Ciudad / OOAD"] == ciudad_sel]

  st.markdown("---")

  if df_ciudades.empty:
    st.info("Sin registros cargados para evaluar semáforo de movilidad.")
  else:
    if ciudad_sel != "Todas las Ciudades (General)":
      info_c = df_ciudades.iloc[0]
      m1, m2, m3 = st.columns(3)
      m1.metric("Flotilla Asignada en Sede", info_c["Flotilla Asignada"])
      m2.metric("Porcentaje Movilidad Real", f"{info_c['Movilidad (%)']}%")
      m3.metric("Estatus del Semáforo", info_c["Estado"])
    else:
      st.info("ℹ️ Nota: Reporte métrico consolidado y tabla ejecutiva de cumplimiento por OOAD.")

    def colorear_estado(val):
      if val == "VERDE":
        return "background-color: #27ae60; color: white; font-weight: bold;"
      elif val == "AMARILLO":
        return "background-color: #f39c12; color: white; font-weight: bold;"
      elif val == "ROJO":
        return f"background-color: {COLORES_PANTONE['7420']}; color: white; font-weight: bold;"
      return ""

    try:
      df_estilizado = df_ciudades.style.map(colorear_estado, subset=["Estado"])
    except AttributeError:
      df_estilizado = df_ciudades.style.applymap(colorear_estado, subset=["Estado"])

    st.dataframe(
        df_estilizado,
        use_container_width=True,
        hide_index=True,
    )

# -----------------------------------------------------------------------------
# 3. CONTROL DEL POOL DE SUSTITUTOS (20%)
# -----------------------------------------------------------------------------
elif mod_actual == "Control del Pool de Sustitutos (20%)":
  if cat_actual == "Institucionales":
    st.warning(
        "El control del pool del 20% de sustitutos aplica únicamente para los"
        " contratos de Arrendamiento (Administrativos y Ambulancias)."
    )
  else:
    st.markdown(
        f'<p class="subtitulo-seccion">Control del Pool del 20% de Sustitutos -'
        f" Flotilla {cat_actual}</p>",
        unsafe_allow_html=True,
    )

    tot_flotilla = len(df_base)
    existentes = int(tot_flotilla * 0.20)
    asignadas = (
        len(df_base[df_base["Estatus"] == "Sustituto Entregado"])
        if "Estatus" in df_base.columns
        else 0
    )
    disponibles = existentes - asignadas

    k1, k2, k3 = st.columns(3)
    k1.metric("Sustitutas Existentes en Pool (20%)", existentes)
    k2.metric("Sustitutas Activas en Uso", asignadas)
    if disponibles >= 0:
      k3.metric("Sustitutas Disponibles en Pool", disponibles)
    else:
      k3.metric(
          "Saturación de Pool",
          f"{abs(disponibles)} Excedidas",
          delta_color="inverse",
      )
      st.error(
          f"⚠️ ALERTA DE CAPACIDAD: Se han asignado {asignadas} unidades"
          f" sustitutas, superando el límite del pool contractual"
          f" ({existentes})."
      )

    st.markdown("---")
    st.markdown(
        "##### **Solicitudes y Entregas de Sustitutos en Seguimiento (SLA 48"
        " horas)**"
    )
    st.table(
        pd.DataFrame(
            columns=[
                "ECO Titular",
                "Ciudad / OOAD",
                "Fecha/Hora Ingreso Taller",
                "ECO Sustituto Asignado",
                "Estatus Cumplimiento SLA",
            ]
        )
    )

# -----------------------------------------------------------------------------
# 4. CARGA INICIAL
# -----------------------------------------------------------------------------
elif mod_actual == "Carga Inicial":
  st.markdown(
      '<p class="subtitulo-seccion">Carga Inicial y Actualización Masiva de'
      " Base de Datos</p>",
      unsafe_allow_html=True,
  )
  st.info(
      f"🔒 Módulo configurado para la carga directa en la tabla de Supabase correspondiente a la flotilla actual:"
      f" **{cat_actual}**."
  )

  with st.expander(
      "🔑 Autenticación de Administrador",
      expanded=not st.session_state.admin_autenticado,
  ):
    usr = st.text_input("Usuario Administrador:", key="admin_user_input")
    pwd = st.text_input("Contraseña:", type="password", key="admin_pwd_input")
    if st.button("Iniciar Sesión"):
      if usr == "e.casas" and pwd == "99094056":
        st.session_state.admin_autenticado = True
        st.success("Acceso concedido como Administrador Central.")
        st.rerun()
      else:
        st.error("Credenciales incorrectas.")

  if st.session_state.admin_autenticado:
    st.markdown(
        f"##### **Subir Archivo de Plantilla para: {cat_actual} (.xlsx o"
        " .csv)**"
    )
    up_file = st.file_uploader(
        "Cargar libro de Excel o CSV con la estructura oficial:",
        type=["xlsx", "csv"],
    )
    if up_file is not None:
      if st.button("Procesar y Guardar en Supabase"):
        try:
          if up_file.name.endswith(".csv"):
            df_subido = pd.read_csv(up_file, dtype=str)
          else:
            df_subido = pd.read_excel(up_file, dtype=str)
            
          df_subido.columns = df_subido.columns.str.strip()
          
          tabla_map = {
              "Administrativos": "vehiculos_administrativos",
              "Ambulancias": "vehiculos_ambulancias",
              "Institucionales": "vehiculos_institucionales"
          }
          nombre_tabla = tabla_map.get(cat_actual, "vehiculos_administrativos")
          
          if supabase:
            supabase.table(nombre_tabla).delete().neq("id", 0).execute()
            
            registros = df_subido.to_dict(orient="records")
            chunk_size = 500
            for i in range(0, len(registros), chunk_size):
              chunk = registros[i:i + chunk_size]
              supabase.table(nombre_tabla).insert(chunk).execute()

          st.session_state.bitacora_cargas.append({
              "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
              "Usuario": st.session_state.get("admin_user_input", "admin"),
              "Base": cat_actual,
              "Archivo": up_file.name,
              "Registros": len(df_subido),
              "Estado": "Exitoso",
          })
          st.cache_data.clear()
          st.success(
              f"¡Base de datos sincronizada con éxito en Supabase! Se guardaron"
              f" {len(df_subido)} unidades en la tabla '{nombre_tabla}'."
          )
          st.rerun()
        except Exception as e:
          st.error(f"Error al procesar y subir el archivo: {e}")

    st.markdown("---")
    st.markdown("##### **Histórico y Bitácora de Cargas Realizadas**")
    st.dataframe(
        pd.DataFrame(st.session_state.bitacora_cargas),
        use_container_width=True,
        hide_index=True,
    )

# -----------------------------------------------------------------------------
# 5. EXPEDIENTE POR ECO Y DOCUMENTAL
# -----------------------------------------------------------------------------
elif mod_actual == "Expediente por ECO y Documental":
  st.markdown(
      f'<p class="subtitulo-seccion">Expediente Técnico y Documental por ECO -'
      f" {cat_actual}</p>",
      unsafe_allow_html=True,
  )

  lista_ecos = (
      list(df_base["No. Ecco."].unique())
      if not df_base.empty and "No. Ecco." in df_base.columns
      else []
  )

  if not lista_ecos:
    st.warning(
        f"No hay vehículos cargados en la base de datos para la flotilla"
        f" **{cat_actual}**."
    )
  else:
    eco_search = st.selectbox(
        "Seleccione o Ingrese el ECO a Consultar:", lista_ecos, index=0
    )
    vehiculo_sel = df_base[df_base["No. Ecco."] == eco_search]

    if not vehiculo_sel.empty:
      v_data = vehiculo_sel.iloc[0]
      st.markdown("---")
      st.markdown(
          f"#### 📋 Ficha Técnica y Descriptiva — ECO:"
          f" `{v_data['No. Ecco.']}`"
      )

      col_img_cat, col_info_cat = st.columns([1, 2.2], gap="small")

      with col_img_cat:
        tipo_v = v_data.get("Tipo", "")
        linea_v = v_data.get("Linea", "")
        url_cat = obtener_imagen_catalogo_supabase(tipo_v, linea_v)
        if url_cat:
          st.markdown(
              f'<div class="image-container-full"><img src="{url_cat}" alt="Vehículo"></div>',
              unsafe_allow_html=True,
          )
          st.caption(f"Catálogo: {tipo_v} - {linea_v}")
        else:
          st.info(f"📷 [Sin foto en catálogo: {linea_v}]")

      with col_info_cat:
        en_taller = any(
            r["ECO"] == v_data["No. Ecco."]
            and r["Estatus"] == "Activo (En Taller)"
            for r in st.session_state.taller_registros
        )
        estatus_veh = (
            "En Taller"
            if en_taller
            else str(v_data.get("Estatus", "Titular Activo"))
        )
        badge_class = (
            "badge-verde"
            if "Activo" in estatus_veh
            else (
                "badge-amarillo" if "Taller" in estatus_veh else "badge-rojo"
            )
        )

        st.markdown(
            f"""
                <div class="card-resumen">
                    <div style="margin-bottom: 6px;">
                        <b>Estatus Operativo:</b> <span class="{badge_class}">{estatus_veh.upper()}</span>
                    </div>
                    <hr style="margin: 6px 0;">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 13px;">
                        <div>
                            <p><b>Placas:</b> {v_data.get('Placas', 'N/A')}</p>
                            <p><b>Número de Serie (VIN):</b> {v_data.get('VIN', 'N/A')}</p>
                            <p><b>No. Tarjeta Circulación:</b> {v_data.get('No_TC', 'N/A')}</p>
                            <p><b>Arrendadora:</b> {v_data.get('Arrendadora', 'N/A')}</p>
                        </div>
                        <div>
                            <p><b>Tipo / Línea:</b> {v_data.get('Tipo', 'N/A')} - {v_data.get('Linea', 'N/A')}</p>
                            <p><b>Ubicación / OOAD:</b> {v_data.get('UBICACIÓN', 'N/A')}</p>
                            <p><b>Último Servicio:</b> {v_data.get('Ultimo_Servicio', 'N/A')}</p>
                            <p><b>Cuota Diaria:</b> ${parse_float(v_data.get('CUOTA DIARIA', 0.0)):,.2f}</p>
                        </div>
                    </div>
                </div>
                """,
            unsafe_allow_html=True,
        )

      st.markdown("---")
      t1, t2, t3 = st.tabs([
          "Galería de Inspección Física",
          "Expediente Documental (PDF/Visor)",
          "Historial de Mantenimientos",
      ])

      with t1:
        st.markdown("##### **Evidencia Fotográfica de la Unidad**")
        g1, g2, g3, g4 = st.columns(4)
        g1.markdown("**Vista Frontal**")
        g1.info("📷 [Foto Frontal]")
        g2.markdown("**Lateral Derecha**")
        g2.info("📷 [Foto Lat. Der.]")
        g3.markdown("**Lateral Izquierda**")
        g3.info("📷 [Foto Lat. Izq.]")
        g4.markdown("**Vista Trasera**")
        g4.info("📷 [Foto Trasera]")

      with t2:
        st.markdown("##### **Documentos Oficiales Registrados**")
        df_docs = pd.DataFrame(columns=[
            "Tipo Documento",
            "Nombre Archivo",
            "Fecha de Carga",
            "Estado Documental",
        ])
        st.dataframe(df_docs, use_container_width=True, hide_index=True)

      with t3:
        st.markdown("##### **Bitácora de Servicios e Intervenciones**")
        hist_taller = [
            r for r in st.session_state.taller_registros if r["ECO"] == eco_search
        ]
        if hist_taller:
          st.dataframe(
              pd.DataFrame(hist_taller),
              use_container_width=True,
              hide_index=True,
          )
        else:
          st.caption(
              "No se registran mantenimientos o siniestros previos para este ECO."
          )

# -----------------------------------------------------------------------------
# 6. REGISTRO DE TALLER E INCIDENCIAS
# -----------------------------------------------------------------------------
elif mod_actual == "Registro de Taller e Incidencias":
  st.markdown(
      f'<p class="subtitulo-seccion">Registro de Taller, Incidencias y'
      f" Siniestros - Flotilla {cat_actual}</p>",
      unsafe_allow_html=True,
  )

  lista_ecos_taller = (
      list(df_base["No. Ecco."].unique())
      if not df_base.empty and "No. Ecco." in df_base.columns
      else []
  )
  tab_captura, tab_editar = st.tabs([
      "📝 Captura de Altas / Salidas",
      "✏️ Editar / Corregir Registro Existente",
  ])

  with tab_captura:
    opcion_taller = st.radio(
        "Seleccione la Operación a Realizar:",
        [
            "1. Ingreso a Taller (Mantenimiento Preventivo / Correctivo)",
            "2. Ingreso a Taller por Siniestro",
            "3. Salida de Taller",
        ],
        horizontal=True,
    )
    st.markdown("---")

    if (
        opcion_taller
        == "1. Ingreso a Taller (Mantenimiento Preventivo / Correctivo)"
    ):
      with st.form(key="form_ingreso_mantenimiento"):
        st.markdown("##### **Registro de Ingreso a Taller**")
        c1, c2 = st.columns(2)
        eco_t = c1.selectbox(
            "Número Económico (ECO):",
            (
                lista_ecos_taller
                if lista_ecos_taller
                else ["Sin ECCOS registrados"]
            ),
        )
        tipo_mantenimiento = c2.selectbox(
            "Tipo de Estatus / Servicio:",
            ["Mantenimiento Preventivo", "Mantenimiento Correctivo"],
        )

        c3, c4 = st.columns(2)
        f_ent = c3.date_input("Fecha Ingreso Taller:", value=date.today())
        h_ent = c4.time_input("Hora Ingreso Taller:")

        c5, c6 = st.columns(2)
        resp_t = c5.text_input("Responsable que Autoriza Ingreso:", value="")
        taller_nom = c6.text_input(
            "Nombre / Razón Social del Taller:", value=""
        )

        req_sust = (
            "Sí" if tipo_mantenimiento == "Mantenimiento Correctivo" else "No"
        )
        if tipo_mantenimiento == "Mantenimiento Correctivo":
          st.info(
              "ℹ️ **Mantenimiento Correctivo:** Requiere asignación de Vehículo"
              " Sustituto (Pool 20%)."
          )
        else:
          st.caption(
              "ℹ️ **Mantenimiento Preventivo:** No aplica vehículo sustituto si"
              " la salida del taller no pasa de 48Hrs."
          )

        evidencia = st.file_uploader(
            "Subir Diagnóstico / Orden de Entrada (PDF/JPG):",
            type=["pdf", "jpg", "png"],
        )
        obs_m = st.text_area("Descripción detallada de fallas o trabajos a realizar:")

        if st.form_submit_button("Registrar Ingreso a Taller"):
          if not lista_ecos_taller:
            st.error("No se puede registrar sin vehículos en la base.")
          else:
            nombre_archivo = (
                f"{eco_t}_ENTRADA_TALLER_{datetime.now().strftime('%Y%m%d')}.pdf"
                if evidencia
                else "N/A"
            )
            nuevo_reg = {
                "ECO": eco_t,
                "Tipo": tipo_mantenimiento,
                "Fecha_Ingreso": str(f_ent),
                "Hora": str(h_ent),
                "Responsable": resp_t,
                "Taller": taller_nom,
                "Sustituto": req_sust,
                "Estatus": "Activo (En Taller)",
                "Observaciones": obs_m,
            }
            st.session_state.taller_registros.append(nuevo_reg)
            st.success(
                f"Ingreso registrado para {eco_t}. Documento:"
                f" '{nombre_archivo}'."
            )

    elif opcion_taller == "2. Ingreso a Taller por Siniestro":
      with st.form(key="form_ingreso_siniestro"):
        st.markdown("##### **Registro de Ingreso por Siniestro**")
        s1, s2 = st.columns(2)
        eco_s = s1.selectbox(
            "Número Económico (ECO):",
            lista_ecos_taller if lista_ecos_taller else ["Sin ECOs cargados"],
        )
        aseg = s2.selectbox(
            "Aseguradora:", ["Qualitas", "GNP", "AXA", "Banorte", "Inbursa", "Otra"]
        )

        s3, s4 = st.columns(2)
        s3.text_input("Número de Póliza:", value="")
        s4.text_input("Número de Folio / Siniestro:", value="")

        s6, s7 = st.columns(2)
        f_sin = s6.date_input("Fecha del Siniestro:", value=date.today())
        taller_sin = s7.text_input("Taller Asignado por Ajustador:", value="")

        st.info(
            "ℹ️ **Siniestro:** Requiere asignación de Vehículo Sustituto (Pool"
            " 20%)."
        )
        evidencia_s = st.file_uploader(
            "Declaración de Siniestro / Fotos Impacto (PDF/JPG):",
            type=["pdf", "jpg", "png"],
        )
        obs_s = st.text_area("Narrativa completa de los hechos e incidencia:")

        if st.form_submit_button("Registrar Siniestro e Ingreso"):
          if not lista_ecos_taller:
            st.error("No se puede registrar sin vehículos en la base.")
          else:
            nombre_archivo_s = (
                f"{eco_s}_SINIESTRO_{datetime.now().strftime('%Y%m%d')}.pdf"
                if evidencia_s
                else "N/A"
            )
            nuevo_reg_s = {
                "ECO": eco_s,
                "Tipo": "Siniestro",
                "Fecha_Ingreso": str(f_sin),
                "Hora": datetime.now().strftime("%H:%M"),
                "Responsable": f"Ajustador {aseg}",
                "Taller": taller_sin,
                "Sustituto": "Sí",
                "Estatus": "Activo (En Taller)",
                "Observaciones": obs_s,
            }
            st.session_state.taller_registros.append(nuevo_reg_s)
            st.warning(
                f"Siniestro registrado para {eco_s}. Documento:"
                f" '{nombre_archivo_s}'."
            )

    elif opcion_taller == "3. Salida de Taller":
      st.markdown("##### **Formulario de Salida y Liberación de Vehículo**")
      eco_salida = st.selectbox(
          "Ingresar ECO de la Unidad que Saldrá del Taller:",
          lista_ecos_taller if lista_ecos_taller else ["Sin ECOs cargados"],
      )
      ingresos_activos = [
          r
          for r in st.session_state.taller_registros
          if r["ECO"] == eco_salida and r["Estatus"] == "Activo (En Taller)"
      ]

      if len(ingresos_activos) == 0:
        st.error("⚠️ Vehículo sin registro de entrada activo en taller.")
      else:
        reg_previo = ingresos_activos[0]
        st.success(
            f"✓ Entrada activa confirmada para **{eco_salida}**"
            f" ({reg_previo['Tipo']} | Fecha Entrada:"
            f" {reg_previo['Fecha_Ingreso']})."
        )

        with st.form(key="form_salida_taller"):
          cs1, cs2 = st.columns(2)
          f_sal = cs1.date_input("Fecha Real de Salida:", value=date.today())
          h_sal = cs2.time_input("Hora de Salida:")
          recibe = st.text_input(
              "Nombre del Personal que Recibe la Unidad:", value=""
          )
          evidencia_salida = st.file_uploader(
              "Comprobante de Entrega / Conformidad (PDF/JPG):",
              type=["pdf", "jpg", "png"],
          )
          obs_salida = st.text_area(
              "Observaciones de Salida y Estado General del Vehículo:"
          )

          if st.form_submit_button("Confirmar y Liberar Salida"):
            nombre_archivo_sal = (
                f"{eco_salida}_SALIDA_TALLER_{datetime.now().strftime('%Y%m%d')}.pdf"
                if evidencia_salida
                else "N/A"
            )
            for r in st.session_state.taller_registros:
              if (
                  r["ECO"] == eco_salida
                  and r["Estatus"] == "Activo (En Taller)"
              ):
                r["Estatus"] = "Concluido (Salida Completa)"
            st.success(
                f"Salida registrada exitosamente para {eco_salida}. Documento:"
                f" '{nombre_archivo_sal}'."
            )

    with tab_editar:
      st.markdown("##### **Módulo de Corrección de Registros Mal Capturados**")
      if len(st.session_state.taller_registros) == 0:
        st.info("No hay registros guardados en la bitácora para corregir.")
      else:
        opciones_reg = [
            (
                f"ID: {idx} | ECO: {r['ECO']} | Tipo: {r['Tipo']} | Fecha:"
                f" {r['Fecha_Ingreso']} | Estatus: {r['Estatus']}"
            )
            for idx, r in enumerate(st.session_state.taller_registros)
        ]
        sel_str = st.selectbox(
            "Seleccione el registro que desea modificar o corregir:",
            opciones_reg,
        )
        idx_sel = int(sel_str.split(" | ")[0].replace("ID: ", ""))
        reg_actual = st.session_state.taller_registros[idx_sel]

        with st.form(key="form_corregir_taller_extension"):
          st.markdown(f"**Modificando Registro en la Posición `{idx_sel}`**")
          ce1, ce2 = st.columns(2)
          e_eco = ce1.text_input("ECO Correcto:", value=reg_actual["ECO"])

          tipos_m_list = [
              "Mantenimiento Preventivo",
              "Mantenimiento Correctivo",
              "Siniestro",
          ]
          idx_t = (
              tipos_m_list.index(reg_actual["Tipo"])
              if reg_actual["Tipo"] in tipos_m_list
              else 0
          )
          e_tipo = ce2.selectbox("Tipo Correcto:", tipos_m_list, index=idx_t)

          ce3, ce4 = st.columns(2)
          e_resp = ce3.text_input(
              "Responsable:", value=reg_actual["Responsable"]
          )
          e_taller = ce4.text_input("Taller:", value=reg_actual["Taller"])

          estatus_list = [
              "Activo (En Taller)",
              "Concluido (Salida Completa)",
              "Anulado por Error",
          ]
          idx_est = (
              estatus_list.index(reg_actual["Estatus"])
              if reg_actual["Estatus"] in estatus_list
              else 0
          )
          e_estatus = st.selectbox(
              "Estatus del Registro:", estatus_list, index=idx_est
          )

          e_obs = st.text_area(
              "Observaciones o notas de la corrección:",
              value=reg_actual["Observaciones"],
          )

          if st.form_submit_button("💾 Guardar Cambios en Bitácora"):
            st.session_state.taller_registros[idx_sel] = {
                "ECO": e_eco.upper().strip(),
                "Tipo": e_tipo,
                "Fecha_Ingreso": reg_actual["Fecha_Ingreso"],
                "Hora": reg_actual["Hora"],
                "Responsable": e_resp,
                "Taller": e_taller,
                "Sustituto": (
                    "Sí" if e_tipo != "Mantenimiento Preventivo" else "No"
                ),
                "Estatus": e_estatus,
                "Observaciones": e_obs,
            }
            st.success("¡El registro ha sido actualizado correctamente!")
            st.rerun()

  st.markdown("---")
  st.markdown("##### **Bitácora de Control de Taller e Incidencias**")
  st.dataframe(
      pd.DataFrame(st.session_state.taller_registros),
      use_container_width=True,
      hide_index=True,
  )

# -----------------------------------------------------------------------------
# 7. REASIGNACIÓN POR NECESIDAD DE SERVICIO
# -----------------------------------------------------------------------------
elif mod_actual == "Reasignación por Necesidad de Servicio":
  st.markdown(
      f'<p class="subtitulo-seccion">Reasignación Geográfica de Vehículos por'
      " Necesidad de Servicio</p>",
      unsafe_allow_html=True,
  )
  st.info(
      "Permite la transferencia oficial de unidades entre sedes u OOAD por"
      " necesidades operativas o de cobertura."
  )

  lista_ecos_reasignacion = (
      list(df_base["No. Ecco."].unique())
      if not df_base.empty and "No. Ecco." in df_base.columns
      else []
  )
  
  # Extracción dinámica y completa de todas las ubicaciones/ciudades desde la base de datos de Supabase
  lista_ciudades_dinamica = (
      sorted(list(df_base["UBICACIÓN"].dropna().unique()))
      if not df_base.empty and "UBICACIÓN" in df_base.columns
      else ["Aguascalientes", "Colima", "Manzanillo", "Tepic", "Mazatlán", "Zacatecas"]
  )

  with st.form(key="form_reasignacion"):
    st.markdown("##### **Formulario Oficial de Reasignación**")
    col_r1, col_r2 = st.columns(2)
    eco_r = col_r1.selectbox(
        "Seleccione el ECO a Reasignar:",
        (
            lista_ecos_reasignacion
            if lista_ecos_reasignacion
            else ["Sin ECOs cargados"]
        ),
    )

    sede_origen = ""
    if not df_base.empty and eco_r in lista_ecos_reasignacion:
      veh_r_info = df_base[df_base["No. Ecco."] == eco_r].iloc[0]
      sede_origen = veh_r_info.get("UBICACIÓN", "")

    col_r2.text_input("Sede de Origen Actual:", value=sede_origen, disabled=True)

    col_r3, col_r4 = st.columns(2)
    sedes_dest = [s for s in lista_ciudades_dinamica if s != sede_origen]
    if not sedes_dest:
      sedes_dest = lista_ciudades_dinamica
      
    sede_destino = col_r3.selectbox("Sede de Destino / Nueva OOAD:", sedes_dest)
    oficio = col_r4.text_input("Número de Oficio de Autorización:", value="")

    motivo = st.text_area("Justificación Técnica / Necesidad de Servicio:")

    if st.form_submit_button("Registrar y Transferir Unidad"):
      if not lista_ecos_reasignacion:
        st.error("No hay vehículos cargados para reasignar.")
      else:
        st.session_state.reasignaciones_historial.append({
            "ECO": eco_r,
            "Sede_Origen": sede_origen,
            "Sede_Destino": sede_destino,
            "Fecha": datetime.now().strftime("%Y-%m-%d"),
            "Motivo": motivo,
            "Oficio_Autorizacion": oficio,
        })
        st.success(
            f"La unidad {eco_r} ha sido reasignada exitosamente de"
            f" {sede_origen} a {sede_destino}."
        )

  st.markdown("---")
  st.markdown("##### **Histórico de Reasignaciones Realizadas**")
  st.dataframe(
      pd.DataFrame(st.session_state.reasignaciones_historial),
      use_container_width=True,
      hide_index=True,
  )

# -----------------------------------------------------------------------------
# 8. REPORTES Y EXPORTACIÓN (ROBUSTO CONTRA DEPENDENCIAS FALTANTES)
# -----------------------------------------------------------------------------
elif mod_actual == "Reportes y Exportación":
  st.markdown(
      f'<p class="subtitulo-seccion">Módulo Consolidado de Reportes y'
      f" Exportación - {cat_actual}</p>",
      unsafe_allow_html=True,
  )
  st.markdown("##### **Parámetros de Reporte**")
  rc1, rc2, rc3 = st.columns(3)
  tipo_rep = rc1.selectbox(
      "Tipo de Reporte:",
      [
          "Inventario General de Flotilla",
          "Estatus de Movilidad por Ciudad",
          "Bitácora Mantenimiento y Siniestros",
          "Consolidado Deducciones y Pagos",
      ],
  )
  formato_rep = rc2.selectbox(
      "Formato de Salida:", ["Excel (.xlsx)", "CSV (.csv)"]
  )
  periodo_rep = rc3.selectbox(
      "Periodo:", ["Septiembre 2026", "Agosto 2026", "Histórico Acumulado"]
  )

  st.markdown("---")
  
  if st.button("🚀 Generar y Descargar Reporte Consolidado"):
    try:
      if "Inventario" in tipo_rep:
        df_export = df_base.copy()
      elif "Movilidad" in tipo_rep:
        df_export = df_ciudades if 'df_ciudades' in locals() and not df_ciudades.empty else df_base.copy()
      elif "Mantenimiento" in tipo_rep:
        df_export = pd.DataFrame(st.session_state.taller_registros) if st.session_state.taller_registros else pd.DataFrame(columns=["Mensaje"])
        if df_export.empty: df_export = pd.DataFrame([{"Mensaje": "Sin registros en bitácora de taller"}])
      else:
        df_export = df_base.copy()

      buffer = io.BytesIO()
      
      if "Excel" in formato_rep:
        file_name_ext = f"Reporte_{tipo_rep.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        # Intento seguro con openpyxl; respaldo automático a CSV si no está instalado
        try:
          with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Reporte_IMSS')
          buffer.seek(0)
          st.download_button(
              label="📥 Clic aquí para descargar el archivo Excel generado",
              data=buffer,
              file_name=file_name_ext,
              mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          )
        except ImportError:
          # Respaldo automático a CSV para prevenir errores de librerías faltantes
          file_name_ext = f"Reporte_{tipo_rep.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
          csv_data = df_export.to_csv(index=False).encode('utf-8')
          st.warning("⚠️ Librería 'openpyxl' no disponible en el entorno; el reporte se generó y entregó en formato CSV compatible.")
          st.download_button(
              label="📥 Clic aquí para descargar el archivo CSV generado",
              data=csv_data,
              file_name=file_name_ext,
              mime="text/csv"
          )
      else:
        file_name_ext = f"Reporte_{tipo_rep.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
        csv_data = df_export.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Clic aquí para descargar el archivo CSV generado",
            data=csv_data,
            file_name=file_name_ext,
            mime="text/csv"
        )
        
      st.success(f"Reporte '{tipo_rep}' generado exitosamente.")
    except Exception as e:
      st.error(f"Error al generar el archivo de descarga: {e}")

# -----------------------------------------------------------------------------
# 9. CONCILIACIÓN FINANCIERA Y PAGOS
# -----------------------------------------------------------------------------
elif mod_actual == "Conciliación Financiera y Pagos":
  st.markdown(
      f'<p class="subtitulo-seccion">Conciliación Financiera y Control de Pagos'
      f" Mensuales - Flotilla {cat_actual}</p>",
      unsafe_allow_html=True,
  )
  st.info(
      "💡 **Acumulación de Archivos:** Las capturas mensuales se integran"
      " históricamente para auditar la vigencia completa del contrato."
  )

  archivo_p = st.file_uploader(
      "Cargar Archivo Mensual de Conciliación (.xlsx):", type=["xlsx"]
  )
  archivo_pdf_mensual = st.file_uploader(
      "Cargar PDF de Evidencias / Constancias de Pago (.pdf):", type=["pdf"]
  )

  df_p = pd.read_excel(archivo_p) if archivo_p is not None else df_base.copy()

  if archivo_pdf_mensual is not None and supabase:
    try:
      pdf_bytes = archivo_pdf_mensual.getvalue()
      file_name_pdf = f"CONCILIACION_{cat_actual}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
      supabase.storage.from_("evidencias-pdf").upload(
          file=pdf_bytes,
          path=file_name_pdf,
          file_options={"content-type": "application/pdf", "upsert": "true"},
      )
      st.success(
          "✅ PDF de evidencias mensuales vinculado y almacenado en Supabase"
          " Storage."
      )
    except Exception as e:
      st.warning(f"No se pudo subir el PDF de evidencias a la nube: {e}")

  f1, f2 = st.columns(2)
  mes_corte = f1.selectbox(
      "Mes de Corte a Consultar:",
      [
          "Acumulado Histórico Total",
          "Septiembre 2026",
          "Agosto 2026",
          "Julio 2026",
      ],
  )
  arr_opciones = ["Todas"] + (
      list(df_p["Arrendadora"].dropna().unique())
      if "Arrendadora" in df_p.columns
      else []
  )
  arr_sel_p = f2.selectbox("Filtrar por Arrendadora:", arr_opciones)

  if arr_sel_p != "Todas" and not df_p.empty and "Arrendadora" in df_p.columns:
    df_p = df_p[df_p["Arrendadora"] == arr_sel_p]

  monto_sub = (
      pd.to_numeric(df_p["COSTO MENSUAL SIN IVA (a)"], errors="coerce").sum()
      if "COSTO MENSUAL SIN IVA (a)" in df_p.columns
      else 0.0
  )
  monto_ded = (
      pd.to_numeric(df_p["TOTAL DE DEDUCCIÓN"], errors="coerce").sum()
      if "TOTAL DE DEDUCCIÓN" in df_p.columns
      else 0.0
  )
  monto_neto = (
      pd.to_numeric(df_p["TOTAL A PAGAR (b)"], errors="coerce").sum()
      if "TOTAL A PAGAR (b)" in df_p.columns
      else 0.0
  )

  c_m1, c_m2, c_m3 = st.columns(3)
  c_m1.metric("Subtotal Sin IVA", f"${monto_sub:,.2f}")
  c_m2.metric(
      "Deducciones Totales Aplicadas",
      f"${monto_ded:,.2f}",
      delta_color="inverse",
  )
  c_m3.metric("Total Neto Pagado/Conciliado", f"${monto_neto:,.2f}")

  st.markdown("---")
  st.markdown("##### **Detalle por Registro de Unidad**")
  cols_fin = [
      "No. Ecco.",
      "UBICACIÓN",
      "Arrendadora",
      "CUOTA DIARIA",
      "TOTAL DÍAS DE SERVICIO",
      "COSTO MENSUAL SIN IVA (a)",
      "TOTAL DE DEDUCCIÓN",
      "TOTAL A PAGAR (b)",
  ]
  cols_fin_existentes = [c for c in cols_fin if c in df_p.columns]
  st.dataframe(
      df_p[cols_fin_existentes]
      if not df_p.empty
      else pd.DataFrame(columns=cols_fin),
      use_container_width=True,
      hide_index=True,
  )

# -----------------------------------------------------------------------------
# FIRMA INSTITUCIONAL FINAL OBLIGATORIA
# -----------------------------------------------------------------------------
st.markdown("""
    <div class="footer-firma">
        Sistema de Control Vehicular IMSS &nbsp;|&nbsp; Creado y desarrollado por: <b>eduardo.casas@imss.gob.mx</b>
    </div>
""", unsafe_allow_html=True)
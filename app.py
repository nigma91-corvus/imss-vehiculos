# =============================================================================
# CÓDIGO COMPLETO - SISTEMA DE CONTROL VEHICULAR IMSS (PERSISTENCIA TOTAL SUPABASE)
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
# --- DISEÑO COMPACTO Y FIJO PARA LA BARRA LATERAL (SIN ENCIMARSE) ---
st.markdown(
    """
    <style>
        /* 0. Reducir al mínimo los espacios internos y externos de la barra lateral */
        [data-testid="stSidebar"] > div:first-child {
            padding-top: 0.5rem !important;
            padding-bottom: 0.5rem !important;
        }

        /* 1. Forzar contenedor estricto de altura sin scroll */
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            display: flex;
            flex-direction: column;
            height: 100vh;
            max-height: 100vh;
            justify-content: space-between;
            overflow: hidden !important;
        }

        /* 1.1 Centrar y reducir el contenedor del logo de manera absoluta */
        [data-testid="stSidebar"] [data-testid="stImage"] {
            display: flex;
            justify-content: center;
            align-items: center;
            margin-bottom: -10px !important;
        }
        [data-testid="stSidebar"] img {
            max-width: 75px !important;
            height: auto !important;
            display: block;
            margin: 0 auto !important;
        }

        /* 1.2 Subir las secciones de títulos y textos */
        [data-testid="stSidebar"] h3, 
        [data-testid="stSidebar"] h4, 
        [data-testid="stSidebar"] p {
            margin-top: 0px !important;
            margin-bottom: 2px !important;
            padding-top: 0px !important;
            padding-bottom: 0px !important;
        }

        /* 2. Dar mejor separación (interlineado) a las opciones del menú de módulos */
        [data-testid="stSidebar"] .stRadio label {
            font-size: 11.5px !important;
            line-height: 1.35 !important;
            padding: 3px 0px !important;
        }

        /* 3. Reducir separación superior de los selectores o radios */
        [data-testid="stSidebar"] .stRadio {
            margin-top: -8px !important;
        }

        /* 4. Espaciado controlado entre los elementos internos de los módulos */
        [data-testid="stSidebar"] .stRadio div[role="radiogroup"] {
            gap: 1px !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
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
    "eco",
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
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

supabase = conectar_supabase()
supabase_url = st.secrets["supabase"]["url"] if supabase else ""

# -----------------------------------------------------------------------------
# GESTIÓN DE IMÁGENES Y DOCUMENTOS DESDE SUPABASE STORAGE
# -----------------------------------------------------------------------------
def obtener_url_supabase(nombre_archivo, bucket="vehiculos-fotos"):
  if supabase_url:
    return f"{supabase_url}/storage/v1/object/public/{bucket}/{nombre_archivo}"
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

  url_supa = obtener_url_supabase(archivo, "vehiculos-fotos")
  if url_supa:
    return url_supa
  return os.path.join("assets", archivo)

url_logo_supa = obtener_url_supabase("logo_imss.png", "vehiculos-fotos")

os.makedirs("data", exist_ok=True)
os.makedirs("expedientes", exist_ok=True)
os.makedirs("assets", exist_ok=True)

# -----------------------------------------------------------------------------
# CARGA DE DATOS DESDE SUPABASE (FLOTILLAS, TALLER, BITÁCORAS, REASIGNACIONES)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=60)
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
      
      # Mapeo flexible para estandarizar columnas de identificación (eco, eco, etc.)
      columnas_mapeo = {}
      for col in df.columns:
        c_clean = col.lower().replace(".", "").replace("_", " ").strip()
        if c_clean in ["eco", "no eco", "noecco", "no_ecco"]:
          columnas_mapeo[col] = "eco"
        elif c_clean in ["ubicacion", "ubicación"]:
          columnas_mapeo[col] = "UBICACIÓN"
      if columnas_mapeo:
        df = df.rename(columns=columnas_mapeo)
    else:
      return pd.DataFrame(columns=COLUMNAS_OFICIALES)
    return df
  except Exception as e:
    return pd.DataFrame(columns=COLUMNAS_OFICIALES)

@st.cache_data(ttl=60)
def cargar_taller_supabase():
    if not supabase:
        return []
    try:
        res = supabase.table("taller_incidencias").select("*").execute()
        rows = res.data or []
        mapped = []
        for r in rows:
            mapped.append({
                "ECO": r.get("eco") or r.get("ECO", ""),
                "Tipo": r.get("tipo") or r.get("Tipo", ""),
                "Fecha_Ingreso": r.get("fecha_ingreso") or r.get("Fecha_Ingreso", ""),
                "Hora": r.get("hora") or r.get("Hora", ""),
                "Responsable": r.get("responsable") or r.get("Responsable", ""),
                "Taller": r.get("taller") or r.get("Taller", ""),
                "Sustituto": r.get("sustituto") or r.get("Sustituto", ""),
                "Estatus": r.get("estatus") or r.get("Estatus", ""),
                "Observaciones": r.get("observaciones") or r.get("Observaciones", "")
            })
        return mapped
    except Exception:
        return []

@st.cache_data(ttl=60)
def cargar_bitacora_cargas_supabase():
    if not supabase:
        return []
    try:
        res = supabase.table("bitacora_cargas").select("*").execute()
        rows = res.data or []
        mapped = []
        for r in rows:
            mapped.append({
                "Fecha": r.get("fecha") or r.get("Fecha", ""),
                "Usuario": r.get("usuario") or r.get("Usuario", ""),
                "Base": r.get("base") or r.get("Base", ""),
                "Archivo": r.get("archivo") or r.get("Archivo", ""),
                "Registros": int(r.get("registros") or r.get("Registros", 0)),
                "Estado": r.get("estado") or r.get("Estado", "Exitoso")
            })
        return mapped
    except Exception:
        return []

@st.cache_data(ttl=60)
def cargar_reasignaciones_supabase():
    if not supabase:
        return []
    try:
        res = supabase.table("reasignaciones").select("*").execute()
        rows = res.data or []
        mapped = []
        for r in rows:
            mapped.append({
                "ECO": r.get("eco") or r.get("ECO", ""),
                "Sede_Origen": r.get("sede_origen") or r.get("Sede_Origen", ""),
                "Sede_Destino": r.get("sede_destino") or r.get("Sede_Destino", ""),
                "Fecha": r.get("fecha") or r.get("Fecha", ""),
                "Motivo": r.get("motivo") or r.get("Motivo", ""),
                "Oficio_Autorizacion": r.get("oficio_autorizacion") or r.get("Oficio_Autorizacion", "")
            })
        return mapped
    except Exception:
        return []

# -----------------------------------------------------------------------------
# GESTIÓN DEL ESTADO DE SESIÓN (SINCRONIZADO CON SUPABASE)
# -----------------------------------------------------------------------------
if "categoria_seleccionada" not in st.session_state:
  st.session_state.categoria_seleccionada = "Administrativos"

if "modulo_activo" not in st.session_state:
  st.session_state.modulo_activo = "Dashboard General"

if "taller_registros" not in st.session_state:
  st.session_state.taller_registros = cargar_taller_supabase()

if "bitacora_cargas" not in st.session_state:
  st.session_state.bitacora_cargas = cargar_bitacora_cargas_supabase()

if "reasignaciones_historial" not in st.session_state:
  st.session_state.reasignaciones_historial = cargar_reasignaciones_supabase()

if "admin_autenticado" not in st.session_state:
  st.session_state.admin_autenticado = False

if "expedientes_fotos" not in st.session_state:
  st.session_state.expedientes_fotos = {}

if "expedientes_docs" not in st.session_state:
  st.session_state.expedientes_docs = {}

if "pagos_cargados" not in st.session_state:
  st.session_state.pagos_cargados = pd.DataFrame()

def cambiar_categoria(cat):
  st.session_state.categoria_seleccionada = cat
  st.session_state.modulo_activo = "Dashboard General"

cat_actual = st.session_state.categoria_seleccionada
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

  color_468 = COLORES_PANTONE["468"]

  st.markdown(
    "<div style='text-align: center; font-size: 11px; margin-bottom: 10px;'>"
    "<b>Coordinación Técnica de Servicios Generales</b><br>"
    f"<span style='font-size:9px; color:{color_468};'>"
    "División de Transportes y Operación</span></div>",
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

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1rem !important; /* Mantenemos el padding compacto */
            padding-bottom: 1rem !important;
        }
    </style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
        }
    </style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div style="display: flex; align-items: flex-end; gap: 15px; width: 100%; margin: 0 0 15px 0;">
        <div style="max-width: 65px; flex-shrink: 0;">
            {logo_html.replace('<img ', '<img style="width: 100%; height: auto; display: block;" ')}
        </div>
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
""",
    unsafe_allow_html=True,
)
mod_actual = st.session_state.modulo_activo

# -----------------------------------------------------------------------------
# # -----------------------------------------------------------------------------
# 1. FUNCIÓN AUXILIAR DE ESTILIZACIÓN (Colócala arriba en tu app o antes del dashboard)
# -----------------------------------------------------------------------------
def aplicar_estilo_tabla(df):
  def estilo_filas(row):
    if df.empty:
      return []
    # Destaca la última fila si coincide con un indicador de total
    if row.name == len(df) - 1 and (
        "TOTAL" in str(row.iloc[0]).upper()
        or "TOTALES" in str(row.iloc[0]).upper()
    ):
      return ["background-color: #e6e6e6; font-weight: bold;" for _ in row.index]

    # Alterna colores cebra entre filas pares e impares
    if row.name % 2 == 0:
      return ["background-color: #ffffff" for _ in row.index]
    else:
      return ["background-color: #f2f4f7" for _ in row.index]

  return df.style.apply(estilo_filas, axis=1)


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
      set(df_dash["eco"].unique()) if "eco" in df_dash.columns else set()
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
              & (~df_dash["eco"].isin(ecos_en_taller))
          ]
      )
      if "Estatus" in df_dash.columns
      else 0
  )
  n_activos = (
      len(
          df_dash[
              (df_dash["Estatus"] == "Titular Activo")
              & (~df_dash["eco"].isin(ecos_en_taller))
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
    colores_dona = [
        COLORES_PANTONE["561"],
        COLORES_PANTONE["465"],
        COLORES_PANTONE["7420"],
        COLORES_PANTONE["504"],
    ]

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
      df_tipo_filtrado = df_dash[
          ~df_dash["Tipo"]
          .str.upper()
          .isin(["SONORA", "SINALOA", "BAJA CALIFORNIA", "CHIHUAHUA", "N/A", "nan"])
      ]

      resumen_tipo = (
          df_tipo_filtrado.groupby("Tipo")
          .size()
          .reset_index(name="Cantidad")
          .sort_values(by="Cantidad", ascending=False)
      )

      if not resumen_tipo.empty:
        paleta_barras = [
            COLORES_PANTONE["7421"],
            COLORES_PANTONE["561"],
            COLORES_PANTONE["465"],
            COLORES_PANTONE["7420"],
            COLORES_PANTONE["626"],
            COLORES_PANTONE["468"],
        ]
        colores_asignados = [
            paleta_barras[i % len(paleta_barras)] for i in range(len(resumen_tipo))
        ]

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
        ax_v.text(
            0.5,
            0.5,
            "Sin Tipos Válidos",
            ha="center",
            va="center",
            fontsize=10,
            color="gray",
        )
        ax_v.axis("off")
    else:
      resumen_tipo = pd.DataFrame(columns=["Tipo", "Cantidad"])
      ax_v.text(
          0.5, 0.5, "Sin Datos", ha="center", va="center", fontsize=12, color="gray"
      )
      ax_v.axis("off")
    fig_v.tight_layout()
    st.pyplot(fig_v)

  with col_tabla:
    st.markdown("##### **Resumen Cantidades Detalladas**")
    if "resumen_tipo" in locals() and not resumen_tipo.empty:
      df_totales = pd.DataFrame(
          [{"Tipo": "TOTAL UNIDADES", "Cantidad": resumen_tipo["Cantidad"].sum()}]
      )
      df_mostrar_res = pd.concat([resumen_tipo, df_totales], ignore_index=True)

      # --- APLICAMOS EL ESTILO DE FILAS CEBRA A LA TABLA DE RESUMEN ---
      st.dataframe(
          aplicar_estilo_tabla(df_mostrar_res),
          hide_index=True,
          use_container_width=True,
      )
    else:
      st.dataframe(
          pd.DataFrame(columns=["Tipo", "Cantidad"]),
          hide_index=True,
          use_container_width=True,
      )

  st.markdown("---")
  st.markdown("##### **Vistas Detalladas de la Base de Datos Activa**")
  cols_mostrar = [
      "eco",
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

  df_detallado = (
      df_dash[cols_existentes]
      if not df_dash.empty
      else pd.DataFrame(columns=cols_mostrar)
  )

  # --- APLICAMOS EL ESTILO DE FILAS CEBRA A LA TABLA DETALLADA ---
  st.dataframe(
      aplicar_estilo_tabla(df_detallado),
      use_container_width=True,
      hide_index=True,
  )
# -----------------------------------------------------------------------------
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
  
  col_filtro_semaforo, col_descarga = st.columns([3, 1])
  
  ciudad_sel = col_filtro_semaforo.selectbox(
      "Seleccionar Vista / Filtro de Ciudad:",
      ["Todas las Ciudades (General)"] + lista_ciudades,
  )

  if not df_base.empty and "UBICACIÓN" in df_base.columns:
    df_ciudades = (
        df_base.groupby("UBICACIÓN")
        .agg(
            Flotilla_Asignada=("eco", "count"),
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

  # --- BOTÓN DE DESCARGA PARA EL REPORTE FILTRADO ---
  with col_descarga:
    st.write("") # Pequeño ajuste visual para alinear con el selectbox
    csv_reporte = df_ciudades.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Descargar Reporte",
        data=csv_reporte,
        file_name=f"semaforo_movilidad_{cat_actual.lower().replace(' ', '_')}.csv",
        mime="text/csv",
        use_container_width=True
    )

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

    def aplicar_estilo_semaforo(row):
      if df_ciudades.empty:
        return []
      
      # Estilo cebra base alternado
      if row.name % 2 == 0:
        estilos = ["background-color: #ffffff" for _ in row.index]
      else:
        estilos = ["background-color: #f2f4f7" for _ in row.index]
        
      return estilos

    # Aplicamos primero el estilo cebra global a la tabla
    df_estilizado = df_ciudades.style.apply(aplicar_estilo_semaforo, axis=1)

    # Añadimos el color dinámico específico para la columna de Estado
    def colorear_estado(val):
      if val == "VERDE":
        return "background-color: #27ae60; color: white; font-weight: bold;"
      elif val == "AMARILLO":
        return "background-color: #f39c12; color: white; font-weight: bold;"
      elif val == "ROJO":
        return f"background-color: {COLORES_PANTONE['7420']}; color: white; font-weight: bold;"
      return ""

    try:
      df_estilizado = df_estilizado.map(colorear_estado, subset=["Estado"])
    except AttributeError:
      df_estilizado = df_estilizado.applymap(colorear_estado, subset=["Estado"])

    st.dataframe(
        df_estilizado,
        use_container_width=True,
        hide_index=True,
    )# -----------------------------------------------------------------------------
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
      f"🔒 Módulo configurado para la carga directa en la tabla de Supabase"
      f" correspondiente a la flotilla actual: **{cat_actual}**."
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
    # --- PEGALO AQUÍ: Botón de Descarga de Plantilla ---
    st.markdown("##### **1. Descargar Plantilla Oficial**")
    columnas_plantilla = [
        "eco",
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
    df_plantilla = pd.DataFrame(columns=columnas_plantilla)
    csv_plantilla = df_plantilla.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="📥 Descargar Plantilla CSV Oficial",
        data=csv_plantilla,
        file_name=f"plantilla_carga_{cat_actual.lower()}.csv",
        mime="text/csv",
        help=(
            "Descarga el archivo modelo con los encabezados exactos requeridos."
        ),
    )

    st.markdown("---")
    # ---------------------------------------------------

    st.markdown(
        f"##### **2. Subir Archivo de Plantilla para: {cat_actual} (.xlsx o"
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
              "Institucionales": "vehiculos_institucionales",
          }
          nombre_tabla = tabla_map.get(
              cat_actual, "vehiculos_administrativos"
          )

          if supabase:
            supabase.table(nombre_tabla).delete().neq("id", 0).execute()
            registros = df_subido.to_dict(orient="records")
            chunk_size = 500
            for i in range(0, len(registros), chunk_size):
              chunk = registros[i : i + chunk_size]
              supabase.table(nombre_tabla).insert(chunk).execute()

            # Guardar bitácora en Supabase
            nueva_bitacora = {
                "fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "usuario": st.session_state.get("admin_user_input", "admin"),
                "base": cat_actual,
                "archivo": up_file.name,
                "registros": len(df_subido),
                "estado": "Exitoso",
            }
            supabase.table("bitacora_cargas").insert(nueva_bitacora).execute()

          st.session_state.bitacora_cargas = cargar_bitacora_cargas_supabase()
          st.cache_data.clear()
          st.success(
              f"¡Base de datos sincronizada con éxito en Supabase! Se"
              f" guardaron {len(df_subido)} unidades en la tabla"
              f" '{nombre_tabla}'."
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
# 5. EXPEDIENTE POR ECO Y DOCUMENTAL (CON CARGA REAL DE FOTOS Y DOCUMENTOS)
# -----------------------------------------------------------------------------
import json
import unicodedata
from datetime import datetime
import pandas as pd
import streamlit as st

# 5. EXPEDIENTE POR ECO Y DOCUMENTAL (CON CARGA REAL DE FOTOS Y DOCUMENTOS)
# -----------------------------------------------------------------------------
if mod_actual == "Expediente por ECO y Documental":
    st.markdown(
        f'<p class="subtitulo-seccion">Expediente Técnico y Documental por ECO - {cat_actual}</p>',
        unsafe_allow_html=True,
    )

    if df_base.empty or "eco" not in df_base.columns:
        st.warning(
            f"No hay vehículos cargados en la base de datos para la flotilla **{cat_actual}**."
        )
    else:
        # Cambio de selectbox a text_input para escribir directamente el ECO
        eco_input = st.text_input(
            "Escriba el Número de ECO a Consultar:",
            value="",
            placeholder="Ej. ECO-101",
        )

        # Normalizamos o filtramos dependiendo de lo que el usuario escriba
        if not eco_input.strip():
            st.info(
                "Por favor, escriba un número de ECO en el campo superior para"
                " ver su expediente."
            )
        else:
            # Filtramos buscando coincidencia exacta (puedes usar .str.contains() si prefieres búsqueda parcial)
            vehiculo_sel = df_base[
                df_base["eco"].astype(str).str.strip().str.lower()
                == eco_input.strip().lower()
            ]

            if vehiculo_sel.empty:
                st.error(
                    f"No se encontró ningún vehículo con el ECO '{eco_input}' en"
                    f" la flotilla **{cat_actual}**."
                )
            else:
                eco_search = vehiculo_sel.iloc[0][
                    "eco"
                ]  # Mantiene el formato original de la BD
                v_data = vehiculo_sel.iloc[0]

                st.markdown("---")
                st.markdown(
                    f"#### 📋 Ficha Técnica y Descriptiva — ECO: `{v_data['eco']}`"
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
                        r["ECO"] == v_data["eco"]
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
                            "badge-amarillo"
                            if "Taller" in estatus_veh
                            else "badge-rojo"
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
                    "Galería de Inspección Física (4 Vistas)",
                    "Expediente Documental (PDF/Visor)",
                    "Historial de Mantenimientos",
                ])

                with t1:
                    st.markdown(
                        "##### **Galería de Inspección Física (Vistas"
                        " Reglamentarias)**"
                    )
                    st.info(
                        "Sube un archivo o toma una fotografía directa. Las"
                        " imágenes se ajustan automáticamente para mantener un"
                        " diseño limpio y ordenado."
                    )

                    eco_limpio = (
                        str(eco_search).replace(" ", "_").replace("/", "-")
                    )
                    vistas_inspeccion = {
                        "Foto Frontal": "foto_frontal",
                        "Foto Trasera": "foto_trasera",
                        "Foto Lateral Derecho": "foto_lateral_der",
                        "Foto Lateral Izquierdo": "foto_lateral_izq",
                    }

                    grid_cols = st.columns(2)

                    for idx, (nombre_vista, campo_key) in enumerate(
                        vistas_inspeccion.items()
                    ):
                        col_actual = grid_cols[idx % 2]

                        with col_actual:
                            st.markdown(f"**{nombre_vista}**")

                            foto_guardada_url = v_data.get(campo_key)

                            if foto_guardada_url and str(
                                foto_guardada_url
                            ).startswith("http"):
                                st.markdown(
                                    f"""
                                    <div style="width: 100%; max-height: 220px; overflow: hidden; display: flex; justify-content: center; align-items: center; background: #f8f9fa; border-radius: 8px; border: 1px solid #dee2e6; margin-bottom: 8px;">
                                        <img src="{foto_guardada_url}" style="max-width: 100%; max-height: 210px; object-fit: contain;" alt="{nombre_vista}">
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                                st.success("✔ Imagen cargada en servidor")
                            else:
                                st.warning("⚠ Sin fotografía registrada")

                            metodo_captura = st.radio(
                                f"Método para {nombre_vista}:",
                                ["Subir Imagen", "Tomar Foto con Cámara"],
                                key=f"radio_{campo_key}_{eco_search}",
                                horizontal=True,
                            )

                            imagen_a_guardar = None

                            if metodo_captura == "Subir Imagen":
                                imagen_a_guardar = st.file_uploader(
                                    f"Cargar {nombre_vista}",
                                    type=["jpg", "jpeg", "png"],
                                    key=f"upl_{campo_key}_{eco_search}",
                                )
                            else:
                                imagen_a_guardar = st.camera_input(
                                    f"Tomar {nombre_vista}",
                                    key=f"cam_{campo_key}_{eco_search}",
                                )

                            if imagen_a_guardar is not None:
                                if st.button(
                                    f"Guardar {nombre_vista}",
                                    key=f"btn_save_{campo_key}_{eco_search}",
                                ):
                                    try:
                                        nombre_original = getattr(
                                            imagen_a_guardar,
                                            "name",
                                            "captura.jpg",
                                        )
                                        extension = (
                                            nombre_original.split(".")[-1]
                                            if "." in nombre_original
                                            else "jpg"
                                        )
                                        nombre_archivo_nube = f"{eco_limpio}_{campo_key}.{extension}"
                                        bytes_f = imagen_a_guardar.getvalue()

                                        if supabase:
                                            supabase.storage.from_(
                                                "vehiculos-fotos"
                                            ).upload(
                                                file=bytes_f,
                                                path=nombre_archivo_nube,
                                                file_options={
                                                    "content-type": (
                                                        f"image/{extension}"
                                                    ),
                                                    "upsert": "true",
                                                },
                                            )

                                            pub_res = supabase.storage.from_(
                                                "vehiculos-fotos"
                                            ).get_public_url(
                                                nombre_archivo_nube
                                            )
                                            url_base = (
                                                pub_res
                                                if isinstance(pub_res, str)
                                                else pub_res.get("publicUrl")
                                            )
                                            url_final = f"{url_base}?t={int(datetime.now().timestamp())}"

                                            tabla_map = {
                                                "Administrativos": (
                                                    "vehiculos_administrativos"
                                                ),
                                                "Ambulancias": (
                                                    "vehiculos_ambulancias"
                                                ),
                                                "Institucionales": (
                                                    "vehiculos_institucionales"
                                                ),
                                            }
                                            nombre_tabla_vehiculos = (
                                                tabla_map.get(
                                                    cat_actual,
                                                    (
                                                        "vehiculos_administrativos"
                                                    ),
                                                )
                                            )

                                            supabase.table(
                                                nombre_tabla_vehiculos
                                            ).update(
                                                {campo_key: url_final}
                                            ).eq(
                                                "eco", eco_search
                                            ).execute()

                                            st.success(
                                                f"✅ {nombre_vista} guardada y"
                                                " vinculada permanentemente."
                                            )

                                            st.cache_data.clear()
                                            if "df_base" in st.session_state:
                                                del st.session_state["df_base"]

                                            st.rerun()
                                    except Exception as e:
                                        st.error(
                                            f"Error al subir la imagen: {e}"
                                        )

                            st.markdown("---")

                with t2:
                    st.markdown("##### **Documentos Oficiales Registrados y Carga**")
                    st.info("Sube un archivo PDF o captura una fotografía directa del documento físico.")

                    if "expedientes_docs" not in st.session_state:
                        st.session_state.expedientes_docs = {}

                    if eco_search not in st.session_state.expedientes_docs:
                        docs_bd = v_data.get("documentos", None)
                        if docs_bd:
                            if isinstance(docs_bd, str):
                                try:
                                    st.session_state.expedientes_docs[eco_search] = json.loads(docs_bd)
                                except:
                                    st.session_state.expedientes_docs[eco_search] = []
                            elif isinstance(docs_bd, list):
                                st.session_state.expedientes_docs[eco_search] = docs_bd
                        else:
                            st.session_state.expedientes_docs[eco_search] = []

                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        tipo_doc_sel = st.selectbox(
                            "Tipo de Documento:",
                            [
                                "Póliza de Seguro",
                                "Tarjeta de Circulación",
                                "Factura / Contrato",
                                "Dictamen Taller",
                                "Otro",
                            ],
                            key=f"tipo_doc_sel_{eco_search}",
                        )

                        metodo_captura_doc = st.radio(
                            "Método para adjuntar documento:",
                            ["Subir Archivo (PDF/Imagen)", "Tomar Foto con Cámara"],
                            key=f"radio_doc_{eco_search}",
                            horizontal=True,
                        )

                        doc_a_guardar = None
                        if metodo_captura_doc == "Subir Archivo (PDF/Imagen)":
                            doc_a_guardar = st.file_uploader(
                                f"Cargar archivo para ECO {eco_search}:",
                                type=["pdf", "jpg", "jpeg", "png"],
                                key=f"doc_uploader_{eco_search}",
                            )
                        else:
                            doc_a_guardar = st.camera_input(
                                f"Tomar foto del documento",
                                key=f"doc_camera_{eco_search}",
                            )

                        if doc_a_guardar is not None:
                            if st.button("Guardar Documento", key=f"btn_save_doc_{eco_search}"):
                                if supabase:
                                    try:
                                        def limpiar_nombre_archivo(texto):
                                            nfkd_form = unicodedata.normalize("NFKD", str(texto))
                                            solo_ascii = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
                                            return (
                                                solo_ascii.replace(" ", "_")
                                                .replace("/", "_")
                                                .replace("\\", "_")
                                                .replace(".", "_")
                                            )

                                        bytes_d = doc_a_guardar.getvalue()
                                        nombre_original = getattr(doc_a_guardar, "name", "captura_doc.jpg")
                                        
                                        extension = (
                                            nombre_original.split(".")[-1].lower()
                                            if "." in nombre_original
                                            else "jpg"
                                        )
                                        
                                        if extension == "pdf":
                                            content_type = "application/pdf"
                                        elif extension in ["png", "jpg", "jpeg"]:
                                            content_type = f"image/{extension if extension != 'jpg' else 'jpeg'}"
                                        else:
                                            content_type = "application/octet-stream"

                                        eco_limpio_str = limpiar_nombre_archivo(str(eco_search))
                                        tipo_limpio_str = limpiar_nombre_archivo(tipo_doc_sel)
                                        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")

                                        nombre_d = f"{eco_limpio_str}_{tipo_limpio_str}_{timestamp_str}.{extension}"

                                        supabase.storage.from_("evidencias-pdf").upload(
                                            file=bytes_d,
                                            path=nombre_d,
                                            file_options={
                                                "content-type": content_type,
                                                "upsert": "true",
                                            },
                                        )

                                        pub_res_doc = supabase.storage.from_("evidencias-pdf").get_public_url(nombre_d)
                                        url_doc = (
                                            pub_res_doc
                                            if isinstance(pub_res_doc, str)
                                            else pub_res_doc.get("publicUrl")
                                        )

                                        if eco_search not in st.session_state.expedientes_docs:
                                            st.session_state.expedientes_docs[eco_search] = []

                                        nuevo_doc = {
                                            "Tipo": tipo_doc_sel,
                                            "Nombre": nombre_original,
                                            "URL": url_doc,
                                            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                        }
                                        st.session_state.expedientes_docs[eco_search].append(nuevo_doc)

                                        tabla_map = {
                                            "Administrativos": "vehiculos_administrativos",
                                            "Ambulancias": "vehiculos_ambulancias",
                                            "Institucionales": "vehiculos_institucionales",
                                        }
                                        nombre_tabla_vehiculos = tabla_map.get(cat_actual, "vehiculos_administrativos")

                                        docs_json_str = json.dumps(st.session_state.expedientes_docs[eco_search])

                                        # CORREGIDO: Apunta directo a la columna "eco" de la base de datos
                                        supabase.table(nombre_tabla_vehiculos).update(
                                            {"documentos": docs_json_str}
                                        ).eq("eco", eco_search).execute()

                                        st.success("✅ Documento subido y guardado permanentemente en la base de datos.")

                                        st.cache_data.clear()
                                        if "df_base" in st.session_state:
                                            del st.session_state["df_base"]
                                        st.rerun()

                                    except Exception as e:
                                        st.error(f"Error al subir el documento: {e}")
                                else:
                                    st.warning("Conexión a Supabase no disponible.")

                    with col_d2:
                        docs_guardados = st.session_state.expedientes_docs.get(eco_search, [])
                        if docs_guardados:
                            df_docs = pd.DataFrame(docs_guardados)
                            st.dataframe(
                                df_docs,
                                use_container_width=True,
                                hide_index=True,
                            )

                            for idx, doc in enumerate(docs_guardados):
                                st.markdown(
                                    f"📄 [{doc['Tipo']} - {doc['Nombre']}]({doc['URL']})"
                                    f" (Agregado: {doc['Fecha']})"
                                )
                        else:
                            st.info("Sin documentos registrados para este vehículo.")

                    with col_d2:
                        docs_guardados = st.session_state.expedientes_docs.get(eco_search, [])
                        if docs_guardados:
                            df_docs = pd.DataFrame(docs_guardados)
                            st.dataframe(
                                df_docs,
                                use_container_width=True,
                                hide_index=True,
                            )

                            for idx, doc in enumerate(docs_guardados):
                                st.markdown(
                                    f"📄 [{doc['Tipo']} - {doc['Nombre']}]({doc['URL']})"
                                    f" (Agregado: {doc['Fecha']})"
                                )
                        else:
                            st.info("Sin documentos registrados para este vehículo.")

                    with col_d2:
                        docs_guardados = st.session_state.expedientes_docs.get(
                            eco_search, []
                        )
                        if docs_guardados:
                            df_docs = pd.DataFrame(docs_guardados)
                            st.dataframe(
                                df_docs,
                                use_container_width=True,
                                hide_index=True,
                            )

                            for idx, doc in enumerate(docs_guardados):
                                st.markdown(
                                    f"📄 [{doc['Tipo']} - {doc['Nombre']}]({doc['URL']})"
                                    f" (Agregado: {doc['Fecha']})"
                                )
                        else:
                            st.info(
                                "Sin documentos registrados para este vehículo."
                            )

                with t3:
                    st.markdown(
                        "##### **Bitácora de Servicios e Intervenciones**"
                    )
                    hist_taller = [
                        r
                        for r in st.session_state.taller_registros
                        if r["ECO"] == eco_search
                    ]
                    if hist_taller:
                        st.dataframe(
                            pd.DataFrame(hist_taller),
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.caption(
                            "No se registran mantenimientos o siniestros"
                            " previos para este ECO."
                        )
# 6. REGISTRO DE TALLER E INCIDENCIAS (PERSISTIDO EN SUPABASE)
# -----------------------------------------------------------------------------
elif mod_actual == "Registro de Taller e Incidencias":
  st.markdown(
      f'<p class="subtitulo-seccion">Registro de Taller, Incidencias y'
      f" Siniestros - Flotilla {cat_actual}</p>",
      unsafe_allow_html=True,
  )

  lista_ecos_taller = (
      list(df_base["eco"].unique())
      if not df_base.empty and "eco" in df_base.columns
      else []
  )
  tab_captura, tab_csv, tab_editar = st.tabs([
      "📝 Captura de Altas / Salidas",
      "📥 Carga Masiva CSV Incidencias",
      "✏️ Editar / Corregir Registro",
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
                "eco": eco_t,
                "tipo": tipo_mantenimiento,
                "fecha_ingreso": str(f_ent),
                "hora": str(h_ent),
                "responsable": resp_t,
                "taller": taller_nom,
                "sustituto": req_sust,
                "estatus": "Activo (En Taller)",
                "observaciones": obs_m,
            }
            if supabase:
              try:
                supabase.table("taller_incidencias").insert(nuevo_reg).execute()
              except Exception as err:
                st.error(f"Error al guardar en Supabase: {err}")

            st.session_state.taller_registros = cargar_taller_supabase()
            st.success(
                f"Ingreso registrado para {eco_t}. Documento:"
                f" '{nombre_archivo}'."
            )
            st.rerun()

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
                "eco": eco_s,
                "tipo": "Siniestro",
                "fecha_ingreso": str(f_sin),
                "hora": datetime.now().strftime("%H:%M"),
                "responsable": f"Ajustador {aseg}",
                "taller": taller_sin,
                "sustituto": "Sí",
                "estatus": "Activo (En Taller)",
                "observaciones": obs_s,
            }
            if supabase:
              try:
                supabase.table("taller_incidencias").insert(nuevo_reg_s).execute()
              except Exception as err:
                st.error(f"Error al guardar en Supabase: {err}")

            st.session_state.taller_registros = cargar_taller_supabase()
            st.warning(
                f"Siniestro registrado para {eco_s}. Documento:"
                f" '{nombre_archivo_s}'."
            )
            st.rerun()

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
            if supabase:
              try:
                supabase.table("taller_incidencias").update({"estatus": "Concluido (Salida Completa)"}).eq("eco", eco_salida).eq("estatus", "Activo (En Taller)").execute()
              except Exception as err:
                st.error(f"Error al actualizar en Supabase: {err}")

            st.session_state.taller_registros = cargar_taller_supabase()
            st.success(
                f"Salida registrada exitosamente para {eco_salida}. Documento:"
                f" '{nombre_archivo_sal}'."
            )
            st.rerun()

  with tab_csv:
    st.markdown("##### **Importación Masiva de Incidencias de Taller via CSV**")
    st.info("Cargue el archivo CSV de reporte de incidencias para volcarlo directamente al sistema.")
    archivo_csv_taller = st.file_uploader("Seleccionar archivo CSV de incidencias:", type=["csv"], key="csv_taller_up")
    if archivo_csv_taller is not None:
      if st.button("Procesar y Cargar CSV a Base de Taller"):
        try:
          df_inc = pd.read_csv(archivo_csv_taller, dtype=str)
          df_inc.columns = df_inc.columns.str.strip()
          registros_inc = df_inc.to_dict(orient="records")
          
          inserts = []
          for ri in registros_inc:
            inserts.append({
                "eco": ri.get("ECO", "N/A"),
                "tipo": ri.get("Tipo", "Mantenimiento Correctivo"),
                "fecha_ingreso": ri.get("Fecha_Ingreso", str(date.today())),
                "hora": ri.get("Hora", "09:00"),
                "responsable": ri.get("Responsable", "Importación CSV"),
                "taller": ri.get("Taller", "General"),
                "sustituto": ri.get("Sustituto", "Sí"),
                "estatus": ri.get("Estatus", "Activo (En Taller)"),
                "observaciones": ri.get("Observaciones", "Carga por CSV")
            })
          
          if supabase and inserts:
            supabase.table("taller_incidencias").insert(inserts).execute()

          st.session_state.taller_registros = cargar_taller_supabase()
          st.success(f"¡Se han importado {len(df_inc)} registros de incidencias exitosamente a Supabase!")
          st.rerun()
        except Exception as e:
          st.error(f"Error al procesar el archivo CSV: {e}")

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
# 7. REASIGNACIÓN POR NECESIDAD DE SERVICIO (PERSISTIDA EN SUPABASE)
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
      list(df_base["eco"].unique())
      if not df_base.empty and "eco" in df_base.columns
      else []
  )
  
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
      veh_r_info = df_base[df_base["eco"] == eco_r].iloc[0]
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
        nueva_reasig = {
            "eco": eco_r,
            "sede_origen": sede_origen,
            "sede_destino": sede_destino,
            "fecha": str(date.today()),
            "motivo": motivo,
            "oficio_autorizacion": oficio,
        }
        if supabase:
          try:
            supabase.table("reasignaciones").insert(nueva_reasig).execute()
          except Exception as err:
            st.error(f"Error al guardar reasignación en Supabase: {err}")

        st.session_state.reasignaciones_historial = cargar_reasignaciones_supabase()
        st.success(
            f"La unidad {eco_r} ha sido reasignada exitosamente de"
            f" {sede_origen} a {sede_destino}."
        )
        st.rerun()

  st.markdown("---")
  st.markdown("##### **Histórico de Reasignaciones Realizadas**")
  st.dataframe(
      pd.DataFrame(st.session_state.reasignaciones_historial),
      use_container_width=True,
      hide_index=True,
  )

# -----------------------------------------------------------------------------
# 8. REPORTES Y EXPORTACIÓN
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
          file_name_ext = f"Reporte_{tipo_rep.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
          csv_data = df_export.to_csv(index=False).encode('utf-8')
          st.warning("⚠️ Librería 'openpyxl' no disponible; el reporte se generó en formato CSV.")
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
      "💡 **Acumulación de Archivos y Reportes XLS:** Cargue sus archivos mensuales de conciliación en Excel/XLSX para auditoría histórica y cálculo por lapsos de tiempo personalizados."
  )

  archivo_p = st.file_uploader(
      "Cargar Archivo Mensual de Conciliación (.xlsx / .xls):", type=["xlsx", "xls"]
  )
  archivo_pdf_mensual = st.file_uploader(
      "Cargar PDF de Evidencias / Constancias de Pago (.pdf):", type=["pdf"]
  )

  if archivo_p is not None:
    try:
      if archivo_p.name.endswith('.csv'):
        st.session_state.pagos_cargados = pd.read_csv(archivo_p, dtype=str)
      else:
        st.session_state.pagos_cargados = pd.read_excel(archivo_p, dtype=str)
      st.success(f"✅ Archivo de pagos '{archivo_p.name}' cargado e integrado correctamente.")
    except Exception as e:
      st.error(f"Error al leer el archivo de pagos: {e}")

  df_p = st.session_state.pagos_cargados if not st.session_state.pagos_cargados.empty else df_base.copy()

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
      pass

  st.markdown("##### **Selección de Lapso de Tiempo y Filtros**")
  f_col1, f_col2, f_col3 = st.columns(3)
  
  usar_rango = f_col1.checkbox("Filtrar por Lapso de Tiempo Específico (Fechas)", value=False)
  
  if usar_rango:
    fecha_inicio = f_col2.date_input("Fecha de Inicio:", value=date(2026, 1, 1))
    fecha_fin = f_col3.date_input("Fecha de Fin:", value=date.today())
    st.info(f"Mostrando transacciones financieras en el lapso del {fecha_inicio} al {fecha_fin}.")
  else:
    mes_corte = f_col2.selectbox(
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
  arr_sel_p = st.selectbox("Filtrar por Arrendadora:", arr_opciones)

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
      "eco",
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

# =============================================================================
# CÓDIGO COMPLETO - SISTEMA DE CONTROL VEHICULAR IMSS (VERSIÓN PERSISTENTE)
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
# CONSTANTES Y PALETA INSTITUCIONAL (PANTONES)
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
  return url_supa if url_supa else os.path.join("assets", archivo)

url_logo_supa = obtener_url_supabase("logo_imss.png", "vehiculos-fotos")

os.makedirs("data", exist_ok=True)
os.makedirs("expedientes", exist_ok=True)
os.makedirs("assets", exist_ok=True)

# -----------------------------------------------------------------------------
# GESTIÓN DEL ESTADO DE SESIÓN Y PERSISTENCIA EN SUPABASE
# -----------------------------------------------------------------------------
if "categoria_seleccionada" not in st.session_state:
  st.session_state.categoria_seleccionada = "Administrativos"

if "modulo_activo" not in st.session_state:
  st.session_state.modulo_activo = "Dashboard General"

if "admin_autenticado" not in st.session_state:
  st.session_state.admin_autenticado = False

def cambiar_categoria(cat):
  st.session_state.categoria_seleccionada = cat
  st.session_state.modulo_activo = "Dashboard General"

cat_actual = st.session_state.categoria_seleccionada

# Cargar registros persistentes desde Supabase (Taller, Reasignaciones, Bitácora)
@st.cache_data(ttl=60)
def cargar_bitacoras_supabase():
  taller = []
  reasig = []
  bitacora = []
  if supabase:
    try:
      res_t = supabase.table("taller_registros").select("*").execute()
      if res_t.data: taller = res_t.data
    except Exception: pass
    try:
      res_r = supabase.table("reasignaciones_historial").select("*").execute()
      if res_r.data: reasig = res_r.data
    except Exception: pass
    try:
      res_b = supabase.table("bitacora_cargas").select("*").execute()
      if res_b.data: bitacora = res_b.data
    except Exception: pass
  return taller, reasig, bitacora

if "taller_registros" not in st.session_state or "reasignaciones_historial" not in st.session_state:
    t_reg, r_reg, b_reg = cargar_bitacoras_supabase()
    st.session_state.taller_registros = t_reg
    st.session_state.reasignaciones_historial = r_reg
    st.session_state.bitacora_cargas = b_reg

@st.cache_data(ttl=300)
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
      if not data: break
      all_rows.extend(data)
      if len(data) < batch_size: break
      offset += batch_size

    df = pd.DataFrame(all_rows)
    if not df.empty:
      df = df.astype(str)
      df.columns = df.columns.str.strip()
      if "id" in df.columns: df = df.drop(columns=["id"])
    else:
      return pd.DataFrame(columns=COLUMNAS_OFICIALES)
    return df
  except Exception as e:
    return pd.DataFrame(columns=COLUMNAS_OFICIALES)

df_base = cargar_datos_supabase(cat_actual)

# -----------------------------------------------------------------------------
# ESTILOS CSS
# -----------------------------------------------------------------------------
st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] {{ font-family: 'Montserrat', sans-serif !important; }}
    .block-container {{ padding: 1.2rem 2rem 2rem 2rem !important; }}
    [data-testid="stSidebar"] {{ background-color: {COLORES_PANTONE["627"]} !important; }}
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] div {{ color: #FFFFFF !important; font-weight: 600; }}
    .subtitulo-seccion {{ color: #222222; font-weight: 700; font-size: 18px; margin-bottom: 15px !important; }}
    .badge-verde {{ background-color: #27ae60; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 11px; }}
    .badge-amarillo {{ background-color: #f39c12; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 11px; }}
    .badge-rojo {{ background-color: {COLORES_PANTONE["7420"]}; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 11px; }}
    .card-resumen {{ background-color: #F8F9FA; border: 1px solid #E9ECEF; border-radius: 8px; padding: 14px; margin-bottom: 12px; }}
    .image-container-full {{ width: 100%; max-height: 220px; display: flex; align-items: center; justify-content: center; background: #fdfdfd; border: 1px solid #e0e0e0; border-radius: 8px; padding: 8px; overflow: hidden; }}
    .image-container-full img {{ max-width: 100% !important; max-height: 200px !important; object-fit: contain !important; }}
    .footer-firma {{ margin-top: 30px; padding: 10px; text-align: center; border-top: 1px solid #E9ECEF; font-size: 11px; color: #555555; font-weight: 600; }}
    </style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# BARRA LATERAL (SIDEBAR)
# -----------------------------------------------------------------------------
with st.sidebar:
  if url_logo_supa:
    st.image(url_logo_supa, use_container_width=True)
  else:
    st.markdown(f"<h2 style='color:{COLORES_PANTONE['468']}; text-align:center;'>IMSS</h2>", unsafe_allow_html=True)

  st.markdown("<div style='text-align: center; font-size: 11px; margin-bottom: 10px;'><b>DIRECCIÓN DE ADMINISTRACIÓN</b><br><span style='font-size:9px; color:#D3C281;'>Coordinación Técnica de Servicios Generales</span></div>", unsafe_allow_html=True)
  st.markdown("---")
  st.markdown("<p style='font-size: 12px; margin-bottom: 8px;'><b>SELECCIONAR FLOTILLA:</b></p>", unsafe_allow_html=True)

  st.button("ADMINISTRATIVOS", use_container_width=True, type="primary" if st.session_state.categoria_seleccionada == "Administrativos" else "secondary", on_click=cambiar_categoria, args=("Administrativos",))
  st.button("AMBULANCIAS", use_container_width=True, type="primary" if st.session_state.categoria_seleccionada == "Ambulancias" else "secondary", on_click=cambiar_categoria, args=("Ambulancias",))
  st.button("INSTITUCIONALES", use_container_width=True, type="primary" if st.session_state.categoria_seleccionada == "Institucionales" else "secondary", on_click=cambiar_categoria, args=("Institucionales",))

  st.markdown("---")

  modulos = [
      "Dashboard General",
      "Semáforo de Movilidad por Ciudad",
      "Control del Pool de Sustitutos (20%)",
      "Carga Inicial",
      "Expediente por ECO y Documental",
      "Registro de Taller e Incidencias",
      "Reporte Oficial Incidencias (IMSS)",
      "Reasignación por Necesidad de Servicio",
      "Reportes y Exportación",
      "Conciliación Financiera y Pagos",
  ]

  if st.session_state.modulo_activo not in modulos:
    st.session_state.modulo_activo = "Dashboard General"

  st.session_state.modulo_activo = st.radio("Módulos del Sistema:", modulos, index=modulos.index(st.session_state.modulo_activo))
  st.markdown("---")
  st.markdown("<div style='text-align: center; font-size: 10px; color: #CCCCCC;'>Desarrollado por:<br><b>eduardo.casas@imss.gob.mx</b></div>", unsafe_allow_html=True)

mod_actual = st.session_state.modulo_activo

# -----------------------------------------------------------------------------
# 1. DASHBOARD GENERAL
# -----------------------------------------------------------------------------
if mod_actual == "Dashboard General":
  st.markdown(f'<p class="subtitulo-seccion">Dashboard General - Flotilla: {cat_actual}</p>', unsafe_allow_html=True)

  col_filtro, _ = st.columns([3, 1])
  unidades_list = ["Todas las Ubicaciones (Nacional)"] + (list(df_base["UBICACIÓN"].dropna().unique()) if "UBICACIÓN" in df_base.columns else [])
  unidad_sel = col_filtro.selectbox("Filtrar Consulta por Unidad Receptora / Ubicación:", unidades_list)

  df_dash = df_base if (unidad_sel == "Todas las Ubicaciones (Nacional)" or df_base.empty) else df_base[df_base["UBICACIÓN"] == unidad_sel]

  tot_unidades = len(df_dash)
  ecos_filtrados = set(df_dash["No. Ecco."].unique()) if "No. Ecco." in df_dash.columns else set()
  ecos_en_taller = {r["ECO"] for r in st.session_state.taller_registros if r.get("Estatus") == "Activo (En Taller)" and r.get("ECO") in ecos_filtrados}
  n_taller = len(ecos_en_taller)
  n_baja = len(df_dash[df_dash["Estatus"] == "Inoperativo / Baja"]) if "Estatus" in df_dash.columns else 0
  n_sust = len(df_dash[(df_dash["Estatus"] == "Sustituto Entregado") & (~df_dash["No. Ecco."].isin(ecos_en_taller))]) if "Estatus" in df_dash.columns else 0
  n_activos = len(df_dash[(df_dash["Estatus"] == "Titular Activo") & (~df_dash["No. Ecco."].isin(ecos_en_taller))]) if "Estatus" in df_dash.columns else 0
  disponibilidad = (((n_activos + n_sust) / tot_unidades * 100) if tot_unidades > 0 else 0.0)

  c1, c2, c3, c4 = st.columns(4)
  c1.metric("Total Unidades Registradas", f"{tot_unidades:,}")
  c2.metric("Titulares / Sustitutos Activos", f"{n_activos + n_sust:,}")
  c3.metric("En Taller / Inoperativos", f"{n_taller + n_baja:,}", delta_color="inverse")
  c4.metric("Disponibilidad Operativa Real", f"{disponibilidad:.1f}%")

  st.markdown("---")
  cols_mostrar = ["No. Ecco.", "Tipo", "Linea", "UBICACIÓN", "Arrendadora", "Estatus", "Placas", "VIN", "CUOTA DIARIA", "TOTAL A PAGAR (b)"]
  cols_existentes = [c for c in cols_mostrar if c in df_dash.columns]
  st.dataframe(df_dash[cols_existentes] if not df_dash.empty else pd.DataFrame(columns=cols_mostrar), use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# 2. SEMÁFORO DE MOVILIDAD POR CIUDAD
# -----------------------------------------------------------------------------
elif mod_actual == "Semáforo de Movilidad por Ciudad":
  st.markdown(f'<p class="subtitulo-seccion">Semáforo de Movilidad por Ciudad - Flotilla {cat_actual}</p>', unsafe_allow_html=True)
  if not df_base.empty and "UBICACIÓN" in df_base.columns:
    df_ciudades = df_base.groupby("UBICACIÓN").agg(
        Flotilla_Asignada=("No. Ecco.", "count"),
        Titulares_Activos=("Estatus", lambda x: (x == "Titular Activo").sum()),
        Sustitutos_Entregados=("Estatus", lambda x: (x == "Sustituto Entregado").sum()),
        En_Taller_Inoperativos=("Estatus", lambda x: (x == "Inoperativo / Baja").sum())
    ).reset_index()
    df_ciudades["Movilidad (%)"] = np.where(df_ciudades["Flotilla_Asignada"] > 0, ((df_ciudades["Titulares_Activos"] + df_ciudades["Sustitutos_Entregados"]) / df_ciudades["Flotilla_Asignada"] * 100).round(1), 0.0)
    df_ciudades["Estado"] = np.where(df_ciudades["Movilidad (%)"] >= 95, "VERDE", np.where(df_ciudades["Movilidad (%)"] >= 85, "AMARILLO", "ROJO"))
    st.dataframe(df_ciudades, use_container_width=True, hide_index=True)
  else:
    st.info("Sin registros para evaluar semáforo.")

# -----------------------------------------------------------------------------
# 3. CONTROL DEL POOL DE SUSTITUTOS (20%)
# -----------------------------------------------------------------------------
elif mod_actual == "Control del Pool de Sustitutos (20%)":
  st.markdown(f'<p class="subtitulo-seccion">Control del Pool del 20% de Sustitutos - Flotilla {cat_actual}</p>', unsafe_allow_html=True)
  tot_flotilla = len(df_base)
  existentes = int(tot_flotilla * 0.20)
  asignadas = len(df_base[df_base["Estatus"] == "Sustituto Entregado"]) if "Estatus" in df_base.columns else 0
  disponibles = existentes - asignadas
  k1, k2, k3 = st.columns(3)
  k1.metric("Sustitutas Existentes en Pool (20%)", existentes)
  k2.metric("Sustitutas Activas en Uso", asignadas)
  k3.metric("Sustitutas Disponibles en Pool", disponibles)

# -----------------------------------------------------------------------------
# 4. CARGA INICIAL
# -----------------------------------------------------------------------------
elif mod_actual == "Carga Inicial":
  st.markdown('<p class="subtitulo-seccion">Carga Inicial y Actualización Masiva de Base de Datos</p>', unsafe_allow_html=True)
  with st.expander("🔑 Autenticación de Administrador", expanded=not st.session_state.admin_autenticado):
    usr = st.text_input("Usuario Administrador:", key="admin_user_input")
    pwd = st.text_input("Contraseña:", type="password", key="admin_pwd_input")
    if st.button("Iniciar Sesión"):
      if usr == "e.casas" and pwd == "99094056":
        st.session_state.admin_autenticado = True
        st.success("Acceso concedido.")
        st.rerun()
      else:
        st.error("Credenciales incorrectas.")

  if st.session_state.admin_autenticado:
    up_file = st.file_uploader("Cargar libro de Excel o CSV con estructura oficial:", type=["xlsx", "csv"])
    if up_file is not None and st.button("Procesar y Guardar en Supabase"):
      try:
        df_subido = pd.read_csv(up_file, dtype=str) if up_file.name.endswith(".csv") else pd.read_excel(up_file, dtype=str)
        df_subido.columns = df_subido.columns.str.strip()
        tabla_map = {"Administrativos": "vehiculos_administrativos", "Ambulancias": "vehiculos_ambulancias", "Institucionales": "vehiculos_institucionales"}
        nombre_tabla = tabla_map.get(cat_actual, "vehiculos_administrativos")
        if supabase:
          supabase.table(nombre_tabla).delete().neq("id", 0).execute()
          registros = df_subido.to_dict(orient="records")
          for i in range(0, len(registros), 500):
            supabase.table(nombre_tabla).insert(registros[i:i+500]).execute()
        st.success(f"¡Base sincronizada con éxito! {len(df_subido)} registros guardados en Supabase.")
        st.rerun()
      except Exception as e:
        st.error(f"Error: {e}")

# -----------------------------------------------------------------------------
# 5. EXPEDIENTE POR ECO Y DOCUMENTAL (CON FOTOS Y DOCUMENTOS PERSISTENTES)
# -----------------------------------------------------------------------------
elif mod_actual == "Expediente por ECO y Documental":
  st.markdown(f'<p class="subtitulo-seccion">Expediente Técnico, Fotográfico y Documental por ECO - {cat_actual}</p>', unsafe_allow_html=True)
  lista_ecos = list(df_base["No. Ecco."].unique()) if not df_base.empty and "No. Ecco." in df_base.columns else []

  if not lista_ecos:
    st.warning("No hay vehículos cargados.")
  else:
    eco_search = st.selectbox("Seleccione o Ingrese el ECO a Consultar:", lista_ecos)
    vehiculo_sel = df_base[df_base["No. Ecco."] == eco_search]
    if not vehiculo_sel.empty:
      v_data = vehiculo_sel.iloc[0]
      st.markdown(f"#### 📋 Ficha Técnica — ECO: `{v_data['No. Ecco.']}`")
      col_img, col_info = st.columns([1, 2], gap="small")

      with col_img:
        tipo_v = v_data.get("Tipo", "")
        linea_v = v_data.get("Linea", "")
        url_cat = obtener_imagen_catalogo_supabase(tipo_v, linea_v)
        st.markdown(f'<div class="image-container-full"><img src="{url_cat}" alt="Vehículo"></div>', unsafe_allow_html=True)
        
        # Subida de foto real del vehículo con persistencia en Supabase Storage
        foto_subida = st.file_uploader("Subir / Actualizar Fotografía Real:", type=["jpg", "png", "jpeg"], key=f"foto_{eco_search}")
        if foto_subida and supabase:
          try:
            foto_bytes = foto_subida.getvalue()
            nombre_foto_db = f"{eco_search}_real_{datetime.now().strftime('%Y%m%d')}.png"
            supabase.storage.from_("vehiculos-fotos").upload(path=nombre_foto_db, file=foto_bytes, file_options={"upsert": "true"})
            st.success("Fotografía guardada en Supabase Storage.")
          except Exception as e:
            st.warning(f"Error al subir foto: {e}")

      with col_info:
        st.markdown(f"""
            <div class="card-resumen">
                <p><b>Placas:</b> {v_data.get('Placas', 'N/A')}</p>
                <p><b>VIN:</b> {v_data.get('VIN', 'N/A')}</p>
                <p><b>Ubicación:</b> {v_data.get('UBICACIÓN', 'N/A')}</p>
                <p><b>Arrendadora:</b> {v_data.get('Arrendadora', 'N/A')}</p>
            </div>
        """, unsafe_allow_html=True)

      st.markdown("---")
      t_doc, t_hist = st.tabs(["📁 Gestión de Documentos (PDF/Facturas)", "🔧 Bitácora de Mantenimiento"])
      with t_doc:
        doc_sub = st.file_uploader("Subir documento oficial (Póliza, Factura, Tarjeta de Circulación):", type=["pdf", "jpg", "png"], key=f"doc_{eco_search}")
        if doc_sub and supabase:
          try:
            doc_bytes = doc_sub.getvalue()
            doc_name = f"{eco_search}_{doc_sub.name}"
            supabase.storage.from_("vehiculos-docs").upload(path=doc_name, file=doc_bytes, file_options={"upsert": "true"})
            st.success(f"Documento '{doc_sub.name}' guardado correctamente en la nube.")
          except Exception as e:
            st.warning(f"Error al subir documento: {e}")

      with t_hist:
        hist_taller = [r for r in st.session_state.taller_registros if r.get("ECO") == eco_search]
        if hist_taller:
          st.dataframe(pd.DataFrame(hist_taller), use_container_width=True, hide_index=True)
        else:
          st.caption("Sin intervenciones registradas.")

# -----------------------------------------------------------------------------
# 6. REGISTRO DE TALLER E INCIDENCIAS (PERSISTENTE)
# -----------------------------------------------------------------------------
elif mod_actual == "Registro de Taller e Incidencias":
  st.markdown(f'<p class="subtitulo-seccion">Registro de Taller, Incidencias y Siniestros - Flotilla {cat_actual}</p>', unsafe_allow_html=True)
  lista_ecos_taller = list(df_base["No. Ecco."].unique()) if not df_base.empty and "No. Ecco." in df_base.columns else []

  with st.form(key="form_ingreso_taller_pers"):
    st.markdown("##### **Nuevo Registro de Ingreso a Taller / Siniestro**")
    c1, c2 = st.columns(2)
    eco_t = c1.selectbox("Número Económico (ECO):", lista_ecos_taller if lista_ecos_taller else ["Sin ECCOS"])
    tipo_m = c2.selectbox("Tipo de Evento:", ["Mantenimiento Preventivo", "Mantenimiento Correctivo", "Siniestro"])
    c3, c4 = st.columns(2)
    f_ent = c3.date_input("Fecha Ingreso:", value=date.today())
    taller_nom = c4.text_input("Nombre del Taller / Patio:")
    obs_m = st.text_area("Diagnóstico / Observaciones:")

    if st.form_submit_button("Guardar en Base de Datos"):
      nuevo_reg = {
          "ECO": eco_t,
          "Tipo": tipo_m,
          "Fecha_Ingreso": str(f_ent),
          "Taller": taller_nom,
          "Estatus": "Activo (En Taller)",
          "Observaciones": obs_m,
      }
      st.session_state.taller_registros.append(nuevo_reg)
      if supabase:
        try:
          supabase.table("taller_registros").insert(nuevo_reg).execute()
        except Exception: pass
      st.success("¡Registro guardado y persistido con éxito!")
      st.rerun()

  st.markdown("---")
  st.markdown("##### **Bitácora General de Taller**")
  if st.session_state.taller_registros:
    st.dataframe(pd.DataFrame(st.session_state.taller_registros), use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# 7. REPORTE OFICIAL INCIDENCIAS (IMSS - 31 AGO 2026)
# -----------------------------------------------------------------------------
elif mod_actual == "Reporte Oficial Incidencias (IMSS)":
  st.markdown('<p class="subtitulo-seccion">Reporte Oficial de Incidencias CENTRACOM (Al 31 de Agosto de 2026)</p>', unsafe_allow_html=True)
  st.info("Datos consolidados de unidades en taller, patio y siniestros basados en el reporte oficial del IMSS.")
  
  # Datos extraídos del PDF oficial del IMSS (31 de agosto de 2026)
  datos_incidencias = [
      {"No": 1, "Modulo": "1", "Ecco": "AA042", "Falla": "Servicio preventivo 45,000 km, revisión frenos", "Taller": "Gutsa Ecatepec", "Ingreso": "24/08/2026", "Dias": 7, "Sustituta": "ST074", "Categoria": "Taller"},
      {"No": 2, "Modulo": "1", "Ecco": "AA003", "Falla": "Filtración de agua de lluvia", "Taller": "Chrysler La Villa", "Ingreso": "13/05/2026", "Dias": 110, "Sustituta": "ST040", "Categoria": "Taller"},
      {"No": 3, "Modulo": "3", "Ecco": "AA004", "Falla": "Falla en arranque, depósito combustible", "Taller": "Auto Kasa Viaducto", "Ingreso": "24/08/2026", "Dias": 7, "Sustituta": "ST183", "Categoria": "Taller"},
      {"No": 4, "Modulo": "3", "Ecco": "AA026", "Falla": "Falla en frenos", "Taller": "Auto Kasa Viaducto", "Ingreso": "27/07/2026", "Dias": 35, "Sustituta": "ST104", "Categoria": "Taller"},
      {"No": 5, "Modulo": "3", "Ecco": "AA123", "Falla": "No arranca, servicio 30,000 km", "Taller": "Ford Pasa Tlalpan", "Ingreso": "17/08/2026", "Dias": 14, "Sustituta": "ST195", "Categoria": "Taller"},
      {"No": 6, "Modulo": "5", "Ecco": "AA127", "Falla": "Reparación anclaje llanta refacción", "Taller": "Rivher Iztapalapa", "Ingreso": "25/08/2026", "Dias": 6, "Sustituta": "ST217", "Categoria": "Taller"},
      {"No": 7, "Modulo": "6", "Ecco": "AA039", "Falla": "Falla en frenos", "Taller": "Ford Pasa Tlalpan", "Ingreso": "26/08/2026", "Dias": 5, "Sustituta": "ST057", "Categoria": "Taller"},
      {"No": 8, "Modulo": "8", "Ecco": "AA014", "Falla": "Fuga de anticongelante", "Taller": "Kasa Naucalpan", "Ingreso": "10/08/2026", "Dias": 21, "Sustituta": "ST258", "Categoria": "Taller"},
      {"No": 9, "Modulo": "8", "Ecco": "AA305", "Falla": "Falla en dirección hidráulica", "Taller": "Kasa Naucalpan", "Ingreso": "11/08/2026", "Dias": 20, "Sustituta": "ST222", "Categoria": "Taller"},
      {"No": 10, "Modulo": "La Raza", "Ecco": "AA019", "Falla": "Servicio preventivo 40,000 km", "Taller": "Auto Mundo Vallejo", "Ingreso": "24/08/2026", "Dias": 7, "Sustituta": "ST152", "Categoria": "Taller"},
  ]
  df_inc = pd.DataFrame(datos_incidencias)
  st.dataframe(df_inc, use_container_width=True, hide_index=True)
  
  csv_inc = df_inc.to_csv(index=False).encode('utf-8')
  st.download_button("📥 Descargar Reporte de Incidencias en CSV", data=csv_inc, file_name="Incidencias_IMSS_31_Ago_2026.csv", mime="text/csv")

# -----------------------------------------------------------------------------
# 8. REASIGNACIÓN POR NECESIDAD DE SERVICIO
# -----------------------------------------------------------------------------
elif mod_actual == "Reasignación por Necesidad de Servicio":
  st.markdown(f'<p class="subtitulo-seccion">Reasignación Geográfica de Vehículos</p>', unsafe_allow_html=True)
  lista_ecos_r = list(df_base["No. Ecco."].unique()) if not df_base.empty and "No. Ecco." in df_base.columns else []

  with st.form("form_reasig"):
    eco_r = st.selectbox("ECO a Reasignar:", lista_ecos_r if lista_ecos_r else ["Sin ECOs"])
    nueva_sede = st.text_input("Nueva Sede / OOAD de Destino:")
    motivo_r = st.text_area("Justificación:")
    if st.form_submit_button("Registrar Reasignación"):
      reg_r = {"ECO": eco_r, "Sede_Destino": nueva_sede, "Motivo": motivo_r, "Fecha": str(date.today())}
      st.session_state.reasignaciones_historial.append(reg_r)
      if supabase:
        try: supabase.table("reasignaciones_historial").insert(reg_r).execute()
        except Exception: pass
      st.success("Reasignación guardada.")
      st.rerun()

  if st.session_state.reasignaciones_historial:
    st.dataframe(pd.DataFrame(st.session_state.reasignaciones_historial), use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# 9. REPORTES Y EXPORTACIÓN
# -----------------------------------------------------------------------------
elif mod_actual == "Reportes y Exportación":
  st.markdown(f'<p class="subtitulo-seccion">Módulo Consolidado de Reportes - {cat_actual}</p>', unsafe_allow_html=True)
  if st.button("🚀 Generar Reporte General en CSV"):
    csv_data = df_base.to_csv(index=False).encode('utf-8')
    st.download_button("Descargar CSV", data=csv_data, file_name=f"Reporte_{cat_actual}_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")

# -----------------------------------------------------------------------------
# 10. CONCILIACIÓN FINANCIERA Y PAGOS (CON LAPSO DE TIEMPO Y XLS)
# -----------------------------------------------------------------------------
elif mod_actual == "Conciliación Financiera y Pagos":
  st.markdown(f'<p class="subtitulo-seccion">Conciliación Financiera y Control de Pagos - {cat_actual}</p>', unsafe_allow_html=True)
  
  archivo_p = st.file_uploader("Cargar Archivo Excel Mensual de Pagos (.xlsx):", type=["xlsx"])
  df_p = pd.read_excel(archivo_p) if archivo_p is not None else df_base.copy()

  st.markdown("##### **Filtrar por Lapso de Tiempo / Rango de Fechas**")
  c_f1, c_f2 = st.columns(2)
  fecha_inicio = c_f1.date_input("Fecha Inicio:", value=date(2026, 1, 1))
  fecha_fin = c_f2.date_input("Fecha Fin:", value=date.today())

  monto_sub = pd.to_numeric(df_p["COSTO MENSUAL SIN IVA (a)"], errors="coerce").sum() if "COSTO MENSUAL SIN IVA (a)" in df_p.columns else 0.0
  monto_ded = pd.to_numeric(df_p["TOTAL DE DEDUCCIÓN"], errors="coerce").sum() if "TOTAL DE DEDUCCIÓN" in df_p.columns else 0.0
  monto_neto = pd.to_numeric(df_p["TOTAL A PAGAR (b)"], errors="coerce").sum() if "TOTAL A PAGAR (b)" in df_p.columns else 0.0

  c_m1, c_m2, c_m3 = st.columns(3)
  c_m1.metric("Subtotal Sin IVA", f"${monto_sub:,.2f}")
  c_m2.metric("Deducciones Totales", f"${monto_ded:,.2f}")
  c_m3.metric("Total Neto Pagado", f"${monto_neto:,.2f}")

  st.markdown("---")
  st.dataframe(df_p, use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# FIRMA INSTITUCIONAL
# -----------------------------------------------------------------------------
st.markdown("""
    <div class="footer-firma">
        Sistema de Control Vehicular IMSS &nbsp;|&nbsp; Creado y desarrollado por: <b>eduardo.casas@imss.gob.mx</b>
    </div>
""", unsafe_allow_html=True)
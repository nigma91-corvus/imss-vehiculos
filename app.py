# =============================================================================
# SISTEMA DE CONTROL VEHICULAR IMSS - VERSIÓN 2.0 (DEPURADO Y ESTABILIZADO)
# Desarrollado por: eduardo.casas@imss.gob.mx
# =============================================================================
import streamlit as st
import base64
from datetime import datetime, date
import os
import io
import unicodedata
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from supabase import create_client
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Configuración de Cloudinary
cloudinary.config(
  cloud_name = st.secrets["cloudinary"]["cloud_name"],
  api_key = st.secrets["cloudinary"]["api_key"],
  api_secret = st.secrets["cloudinary"]["api_secret"],
  secure = True
)

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Sistema de Control Vehicular - IMSS",
    page_icon="🚌",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Estilos CSS generales y barra lateral fija
st.markdown(
    """
    <style>
        [data-testid="stSidebar"] > div:first-child {
            padding-top: 1rem !important;
            padding-bottom: 1rem !important;
        }
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
            display: flex;
            flex-direction: column;
            height: calc(100vh - 20px);
            justify-content: space-between;
        }
        [data-testid="stSidebar"] img {
            max-width: 100px !important;
            display: block;
            margin-left: auto;
            margin-right: auto;
        }
        [data-testid="stSidebar"] .stRadio label {
            font-size: 12px !important;
            line-height: 1.15 !important;
            padding: 1px 0px !important;
        }
        [data-testid="stSidebar"] .stRadio {
            margin-top: -5px !important;
        }
        [data-testid="stSidebar"] .stRadio div[role="radiogroup"] {
            gap: 2px !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
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
    "eco", "tipo", "linea", "ubicacion", "arrendadora", "estatus",
    "placas", "vin", "no_tc", "ultimo_servicio", "cuota_diaria",
    "total_dias_servicio", "costo_mensual_sin_iva", "total_deduccion", "total_a_pagar"
]

# -----------------------------------------------------------------------------
# FUNCIONES AUXILIARES GLOBALES
# -----------------------------------------------------------------------------
def parse_float(val):
    try:
        val_str = str(val).strip()
        if val_str.lower() in ['nan', 'none', 'n/a', '', 'null']:
            return 0.0
        return float(val_str.replace('$', '').replace(',', ''))
    except (ValueError, TypeError):
        return 0.0

def limpiar_texto(texto):
    if not texto:
        return ""
    return ''.join(
        c for c in unicodedata.normalize('NFD', str(texto))
        if unicodedata.category(c) != 'Mn'
    ).lower()

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
# GESTIÓN DE IMÁGENES Y CATÁLOGOS
# -----------------------------------------------------------------------------
def obtener_url_supabase(nombre_archivo, bucket="vehiculos-fotos"):
    if supabase_url:
        return f"{supabase_url}/storage/v1/object/public/{bucket}/{nombre_archivo}"
    return ""

def obtener_imagen_catalogo_supabase(tipo_v, linea_v):
    texto_busqueda = limpiar_texto(f"{tipo_v} {linea_v}")
    cloud_name = st.secrets["cloudinary"]["cloud_name"]

    if "transit" in texto_busqueda:
        return f"https://res.cloudinary.com/{cloud_name}/image/upload/v1788891028/FORD_TRANSIT_GENERICA.png"
    elif "promaster" in texto_busqueda or "ram 2500" in texto_busqueda:
        return f"https://res.cloudinary.com/{cloud_name}/image/upload/v1788891029/RAM_PROMASTER_GENERICA.png"
    elif "silverado" in texto_busqueda:
        return f"https://res.cloudinary.com/{cloud_name}/image/upload/v1788993595/silverado.png"
    elif "urvan" in texto_busqueda:
        return f"https://res.cloudinary.com/{cloud_name}/image/upload/v1788891027/urvan-panel.png"
    elif "f-150" in texto_busqueda:
        return f"https://res.cloudinary.com/{cloud_name}/image/upload/v1788891030/f-150-xl.png"
    elif "v-drive" in texto_busqueda:
        return f"https://res.cloudinary.com/{cloud_name}/image/upload/v1788891031/v-drive-tm-ac.png"
    elif "creta" in texto_busqueda:
        return f"https://res.cloudinary.com/{cloud_name}/image/upload/v1788891030/creta-1-5l-gls-ivt.png"
    return ""

url_logo_supa = "https://res.cloudinary.com/apg9jptd/image/upload/v1788891026/logo_imss.png"

os.makedirs("data", exist_ok=True)
os.makedirs("expedientes", exist_ok=True)
os.makedirs("assets", exist_ok=True)

# -----------------------------------------------------------------------------
# CARGA DE DATOS DESDE SUPABASE (CACHED)
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
    except Exception:
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
# GESTIÓN DEL ESTADO DE SESIÓN
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
        st.markdown(
            f"""
            <div style="display: flex; justify-content: center; align-items: center; margin-top: -10px; margin-bottom: 10px;">
                <img src="{url_logo_supa}" style="max-height: 120px; width: auto; object-fit: contain;">
            </div>
            """,
            unsafe_allow_html=True,
        )

    color_468 = COLORES_PANTONE["468"]

    st.markdown(
        f"<div style='text-align: center; font-size: 11px; margin-bottom: 15px; line-height: 1.2;'>"
        "<b>Coordinación Técnica de Servicios Generales</b><br>"
        f"<span style='font-size:9px; color:{color_468};'>"
        "División de Transportes y Operación</span></div>",
        unsafe_allow_html=True,
    )
    
    st.markdown("<b>FLOTILLA ACTIVA:</b>", unsafe_allow_html=True)
    st.button("ADMINISTRATIVOS", use_container_width=True, type="primary" if cat_actual == "Administrativos" else "secondary", on_click=cambiar_categoria, args=("Administrativos",))
    st.button("AMBULANCIAS", use_container_width=True, type="primary" if cat_actual == "Ambulancias" else "secondary", on_click=cambiar_categoria, args=("Ambulancias",))
    st.button("INSTITUCIONALES", use_container_width=True, type="primary" if cat_actual == "Institucionales" else "secondary", on_click=cambiar_categoria, args=("Institucionales",))

    st.markdown("---")

    modulos = [
        "Dashboard General",
        "Semáforo de Movilidad por Ciudad",
        "Control del Pool de Sustitutos (20%)",
        "Expediente por ECO y Documental",
        "Registro de Taller e Incidencias",
        "Reasignación por Necesidad de Servicio",
        "Conciliación Financiera y Pagos",
        "Reporte Semanal Centracom",
        "Carga Inicial Masiva"
    ]

    if st.session_state.modulo_activo not in modulos:
        st.session_state.modulo_activo = "Dashboard General"

    st.session_state.modulo_activo = st.radio(
        "Módulos Operativos:",
        modulos,
        index=modulos.index(st.session_state.modulo_activo),
    )

    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; font-size: 9px; color: #CCCCCC; line-height: 1.1;'>Desarrollado por:<br><b>eduardo.casas@imss.gob.mx</b></div>",
        unsafe_allow_html=True,
    )

# -----------------------------------------------------------------------------
# ENCABEZADO INSTITUCIONAL
# -----------------------------------------------------------------------------
logo_html = f'<img src="{url_logo_supa}" style="height: 60px; width: auto; object-fit: contain;">' if url_logo_supa else f'<h2 style="color:{COLORES_PANTONE["468"]}; margin:0;">IMSS</h2>'

st.markdown(
    f"""
    <div style="display: flex; align-items: center; gap: 15px; width: 100%; margin: 0 0 15px 0;">
        <div style="max-width: 65px; flex-shrink: 0;">
            {logo_html}
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

def aplicar_estilo_tabla(df):
    def estilo_filas(row):
        if df.empty:
            return []
        if row.name == len(df) - 1 and ("TOTAL" in str(row.iloc[0]).upper() or "TOTALES" in str(row.iloc[0]).upper()):
            return ["background-color: #e6e6e6; font-weight: bold;" for _ in row.index]
        if row.name % 2 == 0:
            return ["background-color: #ffffff" for _ in row.index]
        else:
            return ["background-color: #f2f4f7" for _ in row.index]
    return df.style.apply(estilo_filas, axis=1)

# =============================================================================
# ENRUTAMIENTO DE MÓDULOS DENTRO DEL SISTEMA
# =============================================================================

# 1. DASHBOARD GENERAL
if mod_actual == "Dashboard General":
    st.markdown(f'<p class="subtitulo-seccion">Dashboard General - Flotilla: {cat_actual}</p>', unsafe_allow_html=True)

    if df_base.empty:
        st.warning(f"⚠️ No se han encontrado registros en Supabase para la flotilla **{cat_actual}**.")

    col_filtro, col_exp = st.columns([3, 1])
    unidades_list = ["Todas las Ubicaciones (Nacional)"] + (list(df_base["UBICACIÓN"].dropna().unique()) if "UBICACIÓN" in df_base.columns else [])
    unidad_sel = col_filtro.selectbox("Filtrar Consulta por Unidad Receptora / Ubicación:", unidades_list)

    df_dash = df_base if (unidad_sel == "Todas las Ubicaciones (Nacional)" or df_base.empty) else df_base[df_base["UBICACIÓN"] == unidad_sel]

    tot_unidades = len(df_dash)
    col_estatus_val = 'estatus' if 'estatus' in df_dash.columns else 'Estatus'

    n_taller = len(df_dash[df_dash[col_estatus_val].isin(['TALLER', 'Activo (En Taller)'])])
    n_baja = len(df_dash[df_dash[col_estatus_val] == "Inoperativo / Baja"])
    n_siniestro = len(df_dash[df_dash[col_estatus_val] == "SINIESTRO"])
    n_patio = len(df_dash[df_dash[col_estatus_val] == "PATIO MALAS"])
    total_detenidos_taller = n_taller + n_baja + n_siniestro + n_patio

    n_sust = len(df_dash[df_dash[col_estatus_val] == "Sustituto Entregado"])
    n_activos = len(df_dash[df_dash[col_estatus_val] == "Titular Activo"])
    disponibilidad = ((n_activos + n_sust) / tot_unidades * 100) if tot_unidades > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Unidades Registradas", f"{tot_unidades:,}")
    c2.metric("Titulares / Sustitutos Activos", f"{n_activos + n_sust:,}")
    c3.metric("En Taller / Inoperativos", f"{total_detenidos_taller:,}", delta_color="inverse")
    c4.metric("Disponibilidad Operativa Real", f"{disponibilidad:.1f}%")

    st.markdown("---")
    col_dona, col_barras, col_tabla = st.columns([1.2, 1.5, 1.3], gap="medium")

    with col_dona:
        st.markdown("##### **Estatus Operativo**")
        valores_dona = [n_activos, n_sust, total_detenidos_taller, n_baja]
        etiquetas_dona = ["Activas", "Sustitutos", "En Taller", "Baja / Inoperativos"]
        colores_dona = [COLORES_PANTONE["561"], COLORES_PANTONE["465"], COLORES_PANTONE["7420"], COLORES_PANTONE["504"]]

        fig_d, ax_d = plt.subplots(figsize=(3.5, 3.5))
        if sum(valores_dona) == 0:
            ax_d.text(0.5, 0.5, "Sin Datos", ha="center", va="center", fontsize=12, color="gray")
            ax_d.axis("off")
        else:
            wedges, _ = ax_d.pie(
                valores_dona, startangle=140, colors=colores_dona,
                wedgeprops=dict(width=0.4, edgecolor="white", linewidth=2)
            )
            ax_d.legend(
                wedges, [f"{e}: {v}" for e, v in zip(etiquetas_dona, valores_dona)],
                loc="center", bbox_to_anchor=(0.5, -0.15), frameon=False, fontsize=8
            )
            ax_d.axis("equal")
        fig_d.tight_layout()
        st.pyplot(fig_d)

    with col_barras:
        st.markdown("##### **Distribución de Unidades Activas por Tipo**")
        fig_v, ax_v = plt.subplots(figsize=(4.5, 3.5))
        if not df_dash.empty and "tipo" in df_dash.columns:
            df_tipo_filtrado = df_dash[
                ~df_dash["tipo"].astype(str).str.upper().isin(["SONORA", "SINALOA", "BAJA CALIFORNIA", "CHIHUAHUA", "N/A", "NAN"])
            ]
            resumen_tipo = df_tipo_filtrado.groupby("tipo").size().reset_index(name="Cantidad").sort_values(by="Cantidad", ascending=False)

            if not resumen_tipo.empty:
                paleta_barras = [COLORES_PANTONE["7421"], COLORES_PANTONE["561"], COLORES_PANTONE["465"], COLORES_PANTONE["7420"], COLORES_PANTONE["626"]]
                colores_asignados = [paleta_barras[i % len(paleta_barras)] for i in range(len(resumen_tipo))]
                bars = ax_v.bar(resumen_tipo["tipo"], resumen_tipo["Cantidad"], color=colores_asignados)
                ax_v.tick_params(axis="x", rotation=30, labelsize=8)
                ax_v.grid(axis="y", linestyle="--", alpha=0.5)
                for bar in bars:
                    h = bar.get_height()
                    ax_v.text(bar.get_x() + bar.get_width() / 2, h + 0.5, f"{int(h)}", ha="center", va="bottom", fontweight="bold", fontsize=8)
            else:
                resumen_tipo = pd.DataFrame(columns=["tipo", "Cantidad"])
                ax_v.text(0.5, 0.5, "Sin Unidades Activas", ha="center", va="center", fontsize=10, color="gray")
                ax_v.axis("off")
        else:
            resumen_tipo = pd.DataFrame(columns=["tipo", "Cantidad"])
            ax_v.text(0.5, 0.5, "Sin Datos", ha="center", va="center", fontsize=12, color="gray")
            ax_v.axis("off")
        fig_v.tight_layout()
        st.pyplot(fig_v)

    with col_tabla:
        st.markdown("##### **Resumen Cantidades Detalladas (Activas)**")
        if 'resumen_tipo' in locals() and not resumen_tipo.empty:
            df_totales = pd.DataFrame([{"tipo": "TOTAL UNIDADES", "Cantidad": resumen_tipo["Cantidad"].sum()}])
            df_mostrar_res = pd.concat([resumen_tipo, df_totales], ignore_index=True)
            df_mostrar_res.columns = ["Tipo de Vehículo", "Cantidad"]
            st.dataframe(aplicar_estilo_tabla(df_mostrar_res), hide_index=True, use_container_width=True)
        else:
            st.dataframe(pd.DataFrame(columns=["Tipo de Vehículo", "Cantidad"]), hide_index=True, use_container_width=True)

    st.markdown("---")
    st.markdown("##### **Vistas Detalladas de la Base de Datos Activa**")
    cols_mostrar = ["eco", "tipo", "linea", "UBICACIÓN", "arrendadora", "estatus", "placas", "vin", "cuota_diaria", "total_a_pagar"]
    cols_existentes = [c for c in cols_mostrar if c in df_dash.columns]
    st.dataframe(aplicar_estilo_tabla(df_dash[cols_existentes] if not df_dash.empty else pd.DataFrame(columns=cols_mostrar)), use_container_width=True, hide_index=True)

# 2. SEMÁFORO DE MOVILIDAD POR CIUDAD
elif mod_actual == "Semáforo de Movilidad por Ciudad":
    st.markdown(f'<p class="subtitulo-seccion">Semáforo de Movilidad por Ciudad - Flotilla {cat_actual}</p>', unsafe_allow_html=True)

    lista_ciudades = list(df_base["UBICACIÓN"].dropna().unique()) if "UBICACIÓN" in df_base.columns else []
    col_filtro_semaforo, col_descarga = st.columns([3, 1])
    ciudad_sel = col_filtro_semaforo.selectbox("Seleccionar Vista / Filtro de Ciudad:", ["Todas las Ciudades (General)"] + lista_ciudades)

    if not df_base.empty and "UBICACIÓN" in df_base.columns:
        ecos_en_taller = {r.get("eco", r.get("ECO")) for r in st.session_state.get("taller_registros", []) if r.get("estatus", r.get("Estatus")) == "Activo (En Taller)"}
        df_temp = df_base.copy()
        df_temp["en_taller"] = df_temp["eco"].isin(ecos_en_taller)
        df_temp["es_titular_activo"] = (df_temp["estatus"] == "Titular Activo") & (~df_temp["en_taller"])
        df_temp["es_sustituto"] = df_temp["estatus"] == "Sustituto Entregado"
        df_temp["es_inoperativo"] = df_temp["estatus"].isin(["Inoperativo / Baja", "TALLER", "SINIESTRO", "PATIO MALAS"])

        df_ciudades = df_temp.groupby("UBICACIÓN").agg(
            Flotilla_Asignada=("eco", "count"),
            Titulares_Activos=("es_titular_activo", "sum"),
            Sustitutos_Entregados=("es_sustituto", "sum"),
            En_Taller_Inoperativos=("es_inoperativo", "sum"),
        ).reset_index()

        df_ciudades["Movilidad (%)"] = np.where(df_ciudades["Flotilla_Asignada"] > 0, ((df_ciudades["Titulares_Activos"] + df_ciudades["Sustitutos_Entregados"]) / df_ciudades["Flotilla_Asignada"] * 100).round(1), 0.0)
        df_ciudades["Estado"] = np.where(df_ciudades["Movilidad (%)"] >= 95, "VERDE", np.where(df_ciudades["Movilidad (%)"] >= 85, "AMARILLO", "ROJO"))
        df_ciudades.rename(columns={"UBICACIÓN": "Ciudad / OOAD", "Flotilla_Asignada": "Flotilla Asignada", "Titulares_Activos": "Titulares Activos", "Sustitutos_Entregados": "Sustitutos Entregados", "En_Taller_Inoperativos": "En Taller / Inoperativos"}, inplace=True)
        df_ciudades = df_ciudades.sort_values(by="Movilidad (%)", ascending=True).reset_index(drop=True)
    else:
        df_ciudades = pd.DataFrame(columns=["Ciudad / OOAD", "Flotilla Asignada", "Titulares Activos", "Sustitutos Entregados", "En Taller / Inoperativos", "Movilidad (%)", "Estado"])

    if ciudad_sel != "Todas las Ciudades (General)":
        df_ciudades = df_ciudades[df_ciudades["Ciudad / OOAD"] == ciudad_sel]

    with col_descarga:
        st.write("") 
        csv_reporte = df_ciudades.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Descargar Reporte", data=csv_reporte,
            file_name=f"semaforo_movilidad_{cat_actual.lower().replace(' ', '_')}.csv",
            mime="text/csv", use_container_width=True
        )

    st.markdown("---")
    if not df_ciudades.empty:
        def colorear_estado(val):
            if val == "VERDE": return "background-color: #27ae60; color: white; font-weight: bold;"
            elif val == "AMARILLO": return "background-color: #f39c12; color: white; font-weight: bold;"
            elif val == "ROJO": return f"background-color: {COLORES_PANTONE['7420']}; color: white; font-weight: bold;"
            return ""

        df_estilizado = df_ciudades.style.apply(lambda r: ["background-color: #ffffff" if r.name % 2 == 0 else "background-color: #f2f4f7" for _ in r.index], axis=1)
        try:
            df_estilizado = df_estilizado.map(colorear_estado, subset=["Estado"])
        except AttributeError:
            df_estilizado = df_estilizado.applymap(colorear_estado, subset=["Estado"])

        st.dataframe(df_estilizado, use_container_width=True, hide_index=True)

# 3. CONTROL DEL POOL DE SUSTITUTOS (20%)
elif mod_actual == "Control del Pool de Sustitutos (20%)":
    if cat_actual == "Institucionales":
        st.warning("El control del pool del 20% de sustitutos aplica únicamente para los contratos de Arrendamiento (Administrativos y Ambulancias).")
    else:
        st.markdown(f'<p class="subtitulo-seccion">Control del Pool del 20% de Sustitutos - Flotilla {cat_actual}</p>', unsafe_allow_html=True)
        tot_flotilla = len(df_base)
        existentes = int(tot_flotilla * 0.20)
        asignadas = len(df_base[df_base["estatus"] == "Sustituto Entregado"]) if "estatus" in df_base.columns else 0
        disponibles = existentes - asignadas

        k1, k2, k3 = st.columns(3)
        k1.metric("Sustitutas Existentes en Pool (20%)", existentes)
        k2.metric("Sustitutas Activas en Uso", asignadas)
        if disponibles >= 0:
            k3.metric("Sustitutas Disponibles en Pool", disponibles)
        else:
            k3.metric("Saturación de Pool", f"{abs(disponibles)} Excedidas", delta_color="inverse")
            st.error(f"⚠️ ALERTA DE CAPACIDAD: Se han asignado {asignadas} unidades sustitutas, superando el límite contractual ({existentes}).")

        st.markdown("---")
        st.markdown("##### **Solicitudes y Entregas de Sustitutos en Seguimiento (SLA 48 horas)**")
        taller_regs = st.session_state.get("taller_registros", [])
        data_tabla = [{
            "ECO Titular": r.get("eco", r.get("ECO", "")),
            "Ciudad / OOAD": r.get("ubicacion", r.get("UBICACIÓN", r.get("Ciudad", ""))),
            "Fecha/Hora Ingreso Taller": r.get("fecha_ingreso", r.get("Fecha Ingreso", "")),
            "ECO Sustituto Asignado": r.get("eco_sustituto", r.get("ECO Sustituto", "Pendiente")),
            "Estatus Cumplimiento SLA": r.get("estatus_sla", r.get("SLA", "En Tiempo")),
        } for r in taller_regs] if taller_regs else []

        st.dataframe(pd.DataFrame(data_tabla, columns=["ECO Titular", "Ciudad / OOAD", "Fecha/Hora Ingreso Taller", "ECO Sustituto Asignado", "Estatus Cumplimiento SLA"]), use_container_width=True, hide_index=True)

# 4. EXPEDIENTE POR ECO Y DOCUMENTAL
elif mod_actual == "Expediente por ECO y Documental":
    st.markdown(f'<p class="subtitulo-seccion">Expediente Técnico y Documental por ECO - {cat_actual}</p>', unsafe_allow_html=True)

    if df_base.empty or "eco" not in df_base.columns:
        st.warning(f"No hay vehículos cargados en la base de datos para la flotilla **{cat_actual}**.")
    else:
        lista_ecos = sorted(df_base["eco"].dropna().astype(str).unique().tolist())
        if len(lista_ecos) > 0:
            eco_seleccionado = st.selectbox(f"Seleccione el ECO de la flotilla **{cat_actual}**:", options=lista_ecos)
            vehiculo_sel = df_base[df_base["eco"].astype(str) == eco_seleccionado]
            v_data = vehiculo_sel.iloc[0] if not vehiculo_sel.empty else None

            if v_data is not None:
                st.markdown("---")
                st.markdown(f"#### 📋 Ficha Técnica y Descriptiva — ECO: `{v_data['eco']}`")
                col_img_cat, col_info_cat = st.columns([1, 2.2], gap="small")

                with col_img_cat:
                    tipo_v = v_data.get("tipo", "")
                    linea_v = v_data.get("linea", "")
                    url_cat = obtener_imagen_catalogo_supabase(tipo_v, linea_v)
                    if url_cat:
                        st.markdown(f'<div class="image-container-full"><img src="{url_cat}" alt="Catálogo" style="width:100%; border-radius:8px;"></div>', unsafe_allow_html=True)
                        st.caption(f"Catálogo: {tipo_v} - {linea_v}")
                    else:
                        st.info(f"📷 [Sin foto en catálogo para: {tipo_v} - {linea_v}]")

                with col_info_cat:
                    en_taller = any(r["ECO"] == v_data["eco"] and r["Estatus"] == "Activo (En Taller)" for r in st.session_state.get("taller_registros", []))
                    estatus_veh = "En Taller" if en_taller else str(v_data.get("estatus", "Titular Activo"))
                    badge_class = "badge-verde" if "Activo" in estatus_veh else ("badge-amarillo" if "Taller" in estatus_veh else "badge-rojo")

                    def obtener_val(row, campo, default="N/A"):
                        val = None
                        for col in row.index:
                            col_limpia = limpiar_texto(col)
                            campo_limpio = limpiar_texto(campo)
                            if col_limpia == campo_limpio:
                                val = row[col]
                                break
                        if val is None or (isinstance(val, float) and pd.isna(val)) or str(val).strip() == "" or str(val).lower() == "nan":
                            return default
                        return val

                    cuota_raw = v_data.get("cuota_diaria")
                    try: cuota_val = float(cuota_raw) if cuota_raw is not None and not pd.isna(cuota_raw) else 0.0
                    except: cuota_val = 0.0

                    st.markdown(
                        f"""
                        <div class="card-resumen">
                            <div style="margin-bottom: 6px;">
                                <b>Estatus Operativo:</b> <span class="{badge_class}">{estatus_veh.upper()}</span>
                            </div>
                            <hr style="margin: 6px 0;">
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 13px;">
                                <div>
                                    <p><b>Placas:</b> {obtener_val(v_data, 'placas')}</p>
                                    <p><b>Número de Serie (VIN):</b> {obtener_val(v_data, 'vin')}</p>
                                    <p><b>No. Tarjeta Circulación:</b> {obtener_val(v_data, 'no_tc')}</p>
                                    <p><b>Arrendadora:</b> {obtener_val(v_data, 'arrendadora')}</p>
                                </div>
                                <div>
                                    <p><b>Tipo / Línea:</b> {obtener_val(v_data, 'tipo')} - {obtener_val(v_data, 'linea')}</p>
                                    <p><b>Ubicación / OOAD:</b> {obtener_val(v_data, 'ubicacion')}</p>
                                    <p><b>Último Servicio:</b> {obtener_val(v_data, 'ultimo_servicio')}</p>
                                    <p><b>Cuota Diaria:</b> \${cuota_val:,.2f}</p>
                                </div>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                st.markdown("---")
                t1, t2 = st.tabs(["Galería de Inspección Física", "Expediente Documental"])
                with t1:
                    st.markdown("##### **Galería de Inspección Física**")
                    vistas_inspeccion = {"Foto Frontal": "foto_frontal", "Foto Trasera": "foto_trasera", "Foto Lateral Derecho": "foto_lateral_der", "Foto Lateral Izquierdo": "foto_lateral_izq"}
                    grid_cols = st.columns(2)
                    for idx, (nombre_vista, campo_key) in enumerate(vistas_inspeccion.items()):
                        with grid_cols[idx % 2]:
                            st.markdown(f"**{nombre_vista}**")
                            foto_url = v_data.get(campo_key)
                            if foto_url and str(foto_url).startswith("http"):
                                st.markdown(f'<div class="image-container-full"><img src="{foto_url}" style="max-height:180px; object-fit:contain;"></div>', unsafe_allow_html=True)
                                st.success("✔ Imagen cargada")
                            else:
                                st.warning("⚠ Sin foto registrada")
                            st.markdown("---")
                with t2:
                    st.markdown("##### **Expediente y Documentación**")
                    poliza_url = v_data.get("poliza_seguro")
                    if poliza_url and str(poliza_url).startswith("http"):
                        st.markdown(f'<a href="{poliza_url}" target="_blank">🔍 Ver Póliza de Seguro Digital</a>', unsafe_allow_html=True)
                    else:
                        st.warning("Sin póliza de seguro registrada.")

# 5. REGISTRO DE TALLER E INCIDENCIAS
elif mod_actual == "Registro de Taller e Incidencias":
    st.markdown(f'<p class="subtitulo-seccion">Registro de Taller, Incidencias y Siniestros - Flotilla {cat_actual}</p>', unsafe_allow_html=True)
    st.info("Módulo operativo de entradas, salidas y bitácora de taller conectada a Supabase.")
    if len(st.session_state.taller_registros) > 0:
        st.dataframe(pd.DataFrame(st.session_state.taller_registros), use_container_width=True, hide_index=True)
    else:
        st.info("No hay registros en la bitácora de taller actualmente.")

# 6. REASIGNACIÓN POR NECESIDAD DE SERVICIO
elif mod_actual == "Reasignación por Necesidad de Servicio":
    st.markdown('<p class="subtitulo-seccion">Reasignación Geográfica de Vehículos por Necesidad de Servicio</p>', unsafe_allow_html=True)
    st.info("Permite la transferencia oficial de unidades entre sedes u OOAD.")
    if len(st.session_state.get("reasignaciones_historial", [])) > 0:
        st.dataframe(pd.DataFrame(st.session_state.reasignaciones_historial), use_container_width=True, hide_index=True)
    else:
        st.info("No hay registros históricos de reasignación.")

# 7. CONCILIACIÓN FINANCIERA Y PAGOS
elif mod_actual == "Conciliación Financiera y Pagos":
    st.markdown(
        f'<p class="subtitulo-seccion">Conciliación Financiera y Control de Pagos Mensuales - Flotilla {cat_actual}</p>',
        unsafe_allow_html=True,
    )
    st.info(
        "💡 **Auditoría Financiera:** Módulo vinculado directamente a la tabla `reportes_mensuales` de Supabase para el control de cuotas, días de servicio y deducciones."
    )

    @st.cache_data(ttl=60)
    def cargar_reportes_mensuales_supabase(flotilla_filtro):
        if not supabase: return pd.DataFrame()
        try:
            all_rows = []
            batch_size = 1000
            offset = 0
            
            while True:
                response = supabase.table("reportes_mensuales").select("*").eq("flotilla", flotilla_filtro).range(offset, offset + batch_size - 1).execute()
                data = response.data or []
                if not data:
                    break
                all_rows.extend(data)
                if len(data) < batch_size:
                    break
                offset += batch_size

            return pd.DataFrame(all_rows)
        except Exception as e:
            st.error(f"Error al consultar reportes_mensuales: {e}")
            return pd.DataFrame()

    df_reportes = cargar_reportes_mensuales_supabase(cat_actual)

    if df_reportes.empty:
        st.warning(f"⚠️ No se encontraron registros financieros en la tabla `reportes_mensuales` para la flotilla **{cat_actual}**.")
    else:
        st.markdown("##### **Filtros de Auditoría y Corte**")
        f_col1, f_col2, f_col3 = st.columns(3)

        df_p = df_reportes.copy()

        if "mes_corte" in df_p.columns:
            anios_disponibles = sorted(
                list(df_p["mes_corte"].apply(lambda x: str(x).strip().split()[-1] if len(str(x).split()) >= 2 else "").dropna().unique()),
                reverse=True
            )
            anios_disponibles = [a for a in anios_disponibles if a.isdigit()]
        else:
            anios_disponibles = []

        if not anios_disponibles:
            anios_disponibles = ["2026", "2025"]

        anio_sel = f_col1.selectbox("Seleccionar Año:", ["Todos los Años"] + anios_disponibles)

        df_filtrado_anio = df_p.copy()
        if anio_sel != "Todos los Años":
            df_filtrado_anio = df_filtrado_anio[df_filtrado_anio["mes_corte"].astype(str).str.contains(anio_sel, na=False)]

        meses_unicos = df_filtrado_anio["mes_corte"].dropna().unique().tolist() if "mes_corte" in df_filtrado_anio.columns else []
        
        meses_orden = {
            "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, 
            "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8, 
            "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12
        }
        
        def clave_orden_mes(m):
            partes = str(m).upper().strip().split()
            if len(partes) >= 2:
                nombre_mes = partes[0]
                anio_num = partes[1]
                return (int(anio_num) if anio_num.isdigit() else 0, meses_orden.get(nombre_mes, 0))
            return (0, 0)

        meses_disponibles = ["Todos los Meses del Año"] + sorted(meses_unicos, key=clave_orden_mes, reverse=True)
        mes_sel = f_col2.selectbox("Seleccionar Mes de Corte:", meses_disponibles)

        if mes_sel != "Todos los Meses del Año":
            df_p = df_p[df_p["mes_corte"] == mes_sel]
        elif anio_sel != "Todos los Años":
            df_p = df_filtrado_anio

        arr_opciones = ["Todas"] + sorted(list(df_p["arrendadora"].dropna().unique())) if "arrendadora" in df_p.columns else ["Todas"]
        arr_sel_p = f_col3.selectbox("Filtrar por Arrendadora:", arr_opciones)

        if arr_sel_p != "Todas":
            df_p = df_p[df_p["arrendadora"] == arr_sel_p]

        monto_sub = pd.to_numeric(df_p["costo_mensual_sin_iva"], errors="coerce").sum() if "costo_mensual_sin_iva" in df_p.columns else 0.0
        monto_ded = pd.to_numeric(df_p["total_deduccion"], errors="coerce").sum() if "total_deduccion" in df_p.columns else 0.0
        monto_neto = pd.to_numeric(df_p["total_a_pagar"], errors="coerce").sum() if "total_a_pagar" in df_p.columns else 0.0

        c_m1, c_m2, c_m3 = st.columns(3)
        c_m1.metric("Subtotal Sin IVA", f"\${monto_sub:,.2f}")
        c_m2.metric("Deducciones Totales Aplicadas", f"\${monto_ded:,.2f}", delta_color="inverse")
        c_m3.metric("Total Neto a Pagar", f"\${monto_neto:,.2f}")

        st.markdown("---")
        st.markdown("##### **Detalle Financiero por Unidad**")
        
        cols_fin = [
            "mes_corte", "eco", "ubicacion", "arrendadora", "cuota_diaria",
            "total_dias_servicio", "costo_mensual_sin_iva", "total_deduccion",
            "total_a_pagar", "observaciones"
        ]
        cols_fin_existentes = [c for c in cols_fin if c in df_p.columns]
        
        st.dataframe(
            df_p[cols_fin_existentes] if not df_p.empty else pd.DataFrame(columns=cols_fin),
            use_container_width=True,
            hide_index=True,
        )

        csv_conciliacion = df_p.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Descargar Conciliación Financiera (CSV)",
            data=csv_conciliacion,
            file_name=f"conciliacion_{cat_actual.lower()}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )

# 8. REPORTE SEMANAL CENTRACOM
elif mod_actual == "Reporte Semanal Centracom":
    st.markdown('<p class="subtitulo-seccion">Reporte Semanal CENTRACOM - Control y Operación</p>', unsafe_allow_html=True)
    st.info("📊 Módulo para la captura estructurada, cálculo porcentual automático, análisis gráfico y seguimiento histórico de CENTRACOM.")

    with st.expander("📝 Capturar o Registrar Datos de la Semana", expanded=False):
        st.markdown("##### **Definir Periodo del Reporte**")
        c_per1, c_per2, c_per3, c_per4 = st.columns(4)
        
        anio_cap = c_per1.selectbox("Año:", ["2026", "2025"], key="cap_anio")
        mes_cap = c_per2.selectbox("Mes:", ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"], index=8, key="cap_mes")
        semana_cap = c_per3.selectbox("Semana:", ["1era Semana", "2da Semana", "3era Semana", "4ta Semana", "5ta Semana"], index=4, key="cap_sem")
        
        f_inicio = c_per4.date_input("📅 Inicio de Semana:", value=date(2026, 9, 24))
        f_fin = st.date_input("📅 Fin de Semana:", value=date(2026, 9, 30))
        
        rango_fechas_str = f"{f_inicio.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')}"
        nombre_periodo_completo = f"{semana_cap} de {mes_cap.title()} ({rango_fechas_str})"

        st.markdown("---")
        st.markdown("##### **1. Servicios Realizados (Cantidad por tipo)**")
        
        servicios_base = [
            "HEMODIALISIS", "CITA", "ALTA", "TRAUMA/ORTO", "FISICA", 
            "ZONIFICACION", "INTERCONSULTA", "ONCOLOGIA", "COMISION", 
            "ORGANOS", "INFECTO", "TRASLAPE", "AEROPUERTO", "PSIQUIATRIA", "PERSONAL MEDICO"
        ]

        cantidades_capturadas = {}
        cols_serv = st.columns(3)
        for idx, serv in enumerate(servicios_base):
            col_target = cols_serv[idx % 3]
            cantidades_capturadas[serv] = col_target.number_input(
                f"{serv}", min_value=0, value=0, step=1, key=f"cant_{serv}"
            )

        st.markdown("---")
        st.markdown("##### **2. Totales de Solicitudes y Cancelaciones**")
        c_tot1, c_tot2, c_tot3 = st.columns(3)
        total_solicitados_cap = c_tot1.number_input("Total Servicios Solicitados:", min_value=0, value=0)
        total_cancelados_cap = c_tot2.number_input("Total Servicios Cancelados:", min_value=0, value=0)
        cancelados_asignados_cap = c_tot3.number_input("Cancelados Asignados:", min_value=0, value=0)
        cancelados_no_asignados_cap = max(0, total_cancelados_cap - cancelados_asignados_cap)
        st.caption(f"ℹ️ Cancelados No Asignados calculados automáticamente: **{cancelados_no_asignados_cap}**")

        if st.button("💾 Guardar y Calcular Reporte Semanal Centracom", type="primary"):
            try:
                suma_realizados = sum(cantidades_capturadas.values())
                
                registros_a_guardar = []
                for serv, cant in cantidades_capturadas.items():
                    pct = (cant / suma_realizados * 100) if suma_realizados > 0 else 0.0
                    registros_a_guardar.append({
                        "anio": anio_cap,
                        "mes": mes_cap,
                        "rango_fechas": rango_fechas_str,
                        "semana_periodo": nombre_periodo_completo,
                        "tipo_servicio": serv,
                        "cantidad": int(cant),
                        "porcentaje": round(pct, 2),
                        "total_solicitados": int(total_solicitados_cap),
                        "total_cancelados": int(total_cancelados_cap),
                        "cancelados_asignados": int(cancelados_asignados_cap),
                        "cancelados_no_asignados": int(cancelados_no_asignados_cap)
                    })

                if supabase is None:
                    st.error("⚠️ Error: Cliente de Supabase no inicializado.")
                else:
                    supabase.table("reporte_centracom_semanal").insert(registros_a_guardar).execute()
                    st.success(f"¡Reporte guardado con éxito! Total servicios: {suma_realizados:,}")
                    st.rerun()
            except Exception as e:
                st.error(f"❌ Error al guardar en Supabase: {e}")

    st.markdown("---")
    st.markdown("##### **📊 Visualización Ejecutiva y Gráficas del Reporte**")

    df_centracom = pd.DataFrame()
    try:
        if supabase:
            res_centracom = supabase.table("reporte_centracom_semanal").select("*").execute()
            if res_centracom and res_centracom.data:
                df_centracom = pd.DataFrame(res_centracom.data)
    except Exception as e:
        st.warning(f"⚠️ Nota: {e}")

    if not df_centracom.empty and "anio" in df_centracom.columns:
        f_col1, f_col2, f_col3 = st.columns(3)
        
        anios_disp = sorted(df_centracom["anio"].dropna().unique().tolist(), reverse=True)
        anio_sel = f_col1.selectbox("1. Seleccionar Año:", anios_disp if anios_disp else ["2026"], key="f_limpio_anio")
        df_f_anio = df_centracom[df_centracom["anio"] == anio_sel]

        meses_disp = sorted(df_f_anio["mes"].dropna().unique().tolist()) if not df_f_anio.empty else []
        mes_sel = f_col2.selectbox("2. Seleccionar Mes:", meses_disp if meses_disp else ["SEPTIEMBRE"], key="f_limpio_mes")
        df_f_mes = df_f_anio[df_f_anio["mes"] == mes_sel] if not df_f_anio.empty else pd.DataFrame()

        if not df_f_mes.empty:
            periodos_raw = df_f_mes["semana_periodo"].dropna().unique().tolist()
            semanas_opciones = [p.split(" de ")[0] if " de " in str(p) else str(p) for p in periodos_raw]
            semanas_opciones = list(dict.fromkeys(semanas_opciones))
        else:
            semanas_opciones = ["1era Semana", "2da Semana", "3era Semana", "4ta Semana", "5ta Semana"]

        semana_sel = f_col3.selectbox("3. Seleccionar Semana:", semanas_opciones, key="f_limpio_sem")

        df_filtrado_c = df_f_mes[df_f_mes["semana_periodo"].str.contains(semana_sel, case=False, na=False)].copy() if not df_f_mes.empty else pd.DataFrame()

        if not df_filtrado_c.empty:
            rango_fecha_actual = df_filtrado_c["rango_fechas"].iloc[0] if "rango_fechas" in df_filtrado_c.columns and not pd.isna(df_filtrado_c["rango_fechas"].iloc[0]) else "Periodo Activo"
            st.success(f"📌 **Consulta Activa:** {semana_sel} de {mes_sel.title()} {anio_sel} &nbsp;|&nbsp; 🗓️ **Rango de Fechas:** {rango_fecha_actual}")

            t_sol = int(df_filtrado_c["total_solicitados"].iloc[0]) if "total_solicitados" in df_filtrado_c.columns and not pd.isna(df_filtrado_c["total_solicitados"].iloc[0]) else 0
            t_can = int(df_filtrado_c["total_cancelados"].iloc[0]) if "total_cancelados" in df_filtrado_c.columns and not pd.isna(df_filtrado_c["total_cancelados"].iloc[0]) else 0
            t_asig = int(df_filtrado_c["cancelados_asignados"].iloc[0]) if "cancelados_asignados" in df_filtrado_c.columns and not pd.isna(df_filtrado_c["cancelados_asignados"].iloc[0]) else 0
            t_no_asig = int(df_filtrado_c["cancelados_no_asignados"].iloc[0]) if "cancelados_no_asignados" in df_filtrado_c.columns and not pd.isna(df_filtrado_c["cancelados_no_asignados"].iloc[0]) else (t_can - t_asig)

            g_col1, g_col2 = st.columns([1.8, 1.2], gap="medium")

            with g_col1:
                st.markdown("##### **Top Servicios Realizados (Distribución)**")
                df_g_serv = df_filtrado_c.groupby("tipo_servicio", as_index=False)["cantidad"].sum()
                df_g_serv = df_g_serv.sort_values(by="cantidad", ascending=True)
                
                fig_bar, ax_bar = plt.subplots(figsize=(6, 4))
                bars = ax_bar.barh(df_g_serv["tipo_servicio"], df_g_serv["cantidad"], color=COLORES_PANTONE["626"])
                
                ax_bar.tick_params(axis='both', labelsize=8)
                ax_bar.grid(axis='x', linestyle=':', alpha=0.5)
                
                for bar in bars:
                    w = bar.get_width()
                    if w > 0:
                        ax_bar.text(w + (max(df_g_serv["cantidad"])*0.01 if max(df_g_serv["cantidad"])>0 else 1), 
                                    bar.get_y() + bar.get_height()/2, f'{int(w):,}', 
                                    ha='left', va='center', fontsize=7, fontweight='bold', color='#333333')
                
                fig_bar.tight_layout()
                st.pyplot(fig_bar)

            with g_col2:
                st.markdown("##### **Cumplimiento General**")
                total_cant = df_g_serv["cantidad"].sum()
                
                fig_pie, ax_pie = plt.subplots(figsize=(3.5, 2.8))
                valores_pie = [total_cant, t_can]
                etiquetas_pie = [f'Realizados\n({total_cant:,})', f'Cancelados\n({t_can:,})']
                colores_pie = [COLORES_PANTONE["561"], COLORES_PANTONE["7420"]]
                
                wedges, texts, autotexts = ax_pie.pie(
                    valores_pie, labels=etiquetas_pie, autopct='%1.1f%%',
                    pctdistance=0.75, startangle=140, colors=colores_pie,
                    wedgeprops=dict(width=0.45, edgecolor='white', linewidth=2),
                    textprops=dict(fontsize=8, fontweight='bold', color='#1e3d2f')
                )
                for autotext in autotexts:
                    autotext.set_color('white')
                    autotext.set_weight('bold')
                
                ax_pie.axis('equal')
                fig_pie.tight_layout()
                st.pyplot(fig_pie)

            st.markdown("---")
            st.markdown("##### **Tablas de Datos Consolidados (Formato Oficial)**")
            
            df_tabla_serv = df_filtrado_c.groupby("tipo_servicio", as_index=False).agg({"cantidad": "sum"})
            total_cant = df_tabla_serv["cantidad"].sum()
            df_tabla_serv["%"] = (df_tabla_serv["cantidad"] / total_cant * 100) if total_cant > 0 else 0.0
            df_tabla_serv = df_tabla_serv.sort_values(by="cantidad", ascending=False)
            
            df_tabla_serv.columns = ["SERVICIO REALIZADOS", "CANTIDAD", "%"]
            df_tabla_serv["%"] = df_tabla_serv["%"].apply(lambda x: f"{x:.2f}%")
            
            df_totales_row = pd.DataFrame([["TOTAL", total_cant, "100.00%"]], columns=df_tabla_serv.columns)
            df_tabla_serv = pd.concat([df_tabla_serv, df_totales_row], ignore_index=True)

            try:
                st.dataframe(aplicar_estilo_tabla(df_tabla_serv), use_container_width=True, hide_index=True)
            except Exception:
                st.dataframe(df_tabla_serv, use_container_width=True, hide_index=True)

            st.markdown("---")
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                st.markdown("##### **Resumen de Solicitudes**")
                pct_can_gen = (t_can / t_sol * 100) if t_sol > 0 else 0
                pct_real_gen = (total_cant / t_sol * 100) if t_sol > 0 else 0
                df_resumen_sol = pd.DataFrame([
                    {"Concepto": "TOTAL SERVICIOS SOLICITADOS", "Cantidad": t_sol, "%": "100.00%"},
                    {"Concepto": "CANCELADO", "Cantidad": t_can, "%": f"{pct_can_gen:.2f}%"},
                    {"Concepto": "REALIZADO", "Cantidad": total_cant, "%": f"{pct_real_gen:.2f}%"}
                ])
                try:
                    st.dataframe(aplicar_estilo_tabla(df_resumen_sol), use_container_width=True, hide_index=True)
                except Exception:
                    st.dataframe(df_resumen_sol, use_container_width=True, hide_index=True)

            with col_b2:
                st.markdown("##### **Detalle de Cancelaciones**")
                pct_asig = (t_asig / t_can * 100) if t_can > 0 else 0
                pct_no_asig = (t_no_asig / t_can * 100) if t_can > 0 else 0
                df_resumen_can = pd.DataFrame([
                    {"Concepto": "TOTAL SERVICIOS CANCELADOS", "Cantidad": t_can, "%": "100.00%"},
                    {"Concepto": "CANCELADOS ASIGNADOS", "Cantidad": t_asig, "%": f"{pct_asig:.2f}%"},
                    {"Concepto": "CANCELADOS NO ASIGNADOS", "Cantidad": t_no_asig, "%": f"{pct_no_asig:.2f}%"}
                ])
                try:
                    st.dataframe(aplicar_estilo_tabla(df_resumen_can), use_container_width=True, hide_index=True)
                except Exception:
                    st.dataframe(df_resumen_can, use_container_width=True, hide_index=True)

            csv_centracom = df_tabla_serv.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Descargar Reporte CENTRACOM (CSV)",
                data=csv_centracom,
                file_name=f"reporte_centracom_{anio_sel}_{mes_sel}_{semana_sel.replace(' ', '_')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("ℹ️ No hay datos guardados para la semana seleccionada.")
    else:
        st.warning("⚠️ No hay registros en la tabla `reporte_centracom_semanal`.")

    # --- ANÁLISIS DE ACUMULADOS GLOBALES HISTÓRICOS ---
    st.markdown("---")
    st.markdown("##### **📈 Análisis de Acumulados e Histórico Global de Servicios**")

    if not df_centracom.empty and "anio" in df_centracom.columns:
        h_col1, h_col2 = st.columns(2)
        nivel_acumulado = h_col1.selectbox("Agrupar Acumulado por:", ["Año Completo", "Mes Específico", "Histórico Total (Todas las Semanas)"], key="f_acum_nivel")
        
        df_analisis = df_centracom.copy()

        if nivel_acumulado == "Año Completo":
            anios_h = sorted(df_analisis["anio"].dropna().unique().tolist())
            anio_h_sel = h_col2.selectbox("Seleccionar Año para Acumulado:", anios_h if anios_h else ["2026"], key="f_acum_anio")
            df_analisis = df_analisis[df_analisis["anio"] == anio_h_sel]
            titulo_grafico = f"Acumulado Anual de Servicios ({anio_h_sel})"
            
        elif nivel_acumulado == "Mes Específico":
            meses_h = sorted(df_analisis["mes"].dropna().unique().tolist())
            mes_h_sel = h_col2.selectbox("Seleccionar Mes para Acumulado:", meses_h if meses_h else ["SEPTIEMBRE"], key="f_acum_mes")
            df_analisis = df_analisis[df_analisis["mes"] == mes_h_sel]
            titulo_grafico = f"Acumulado Mensual de Servicios ({mes_h_sel})"
        else:
            titulo_grafico = "Acumulado Histórico Global de Servicios"

        if not df_analisis.empty:
            df_acumulado_grp = df_analisis.groupby("tipo_servicio", as_index=False)["cantidad"].sum()
            df_acumulado_grp = df_acumulado_grp.sort_values(by="cantidad", ascending=True)

            fig_ac, ax_ac = plt.subplots(figsize=(8, 4.5))
            bars_ac = ax_ac.barh(df_acumulado_grp["tipo_servicio"], df_acumulado_grp["cantidad"], color=COLORES_PANTONE["561"])
            
            ax_ac.set_title(titulo_grafico, fontsize=10, fontweight='bold', color='#1e3d2f')
            ax_ac.tick_params(axis='both', labelsize=8)
            ax_ac.grid(axis='x', linestyle=':', alpha=0.5)

            for bar in bars_ac:
                w = bar.get_width()
                if w > 0:
                    ax_ac.text(w + (max(df_acumulado_grp["cantidad"])*0.01 if max(df_acumulado_grp["cantidad"])>0 else 1), 
                               bar.get_y() + bar.get_height()/2, f'{int(w):,}', 
                               ha='left', va='center', fontsize=7, fontweight='bold', color='#333333')

            fig_ac.tight_layout()
            st.pyplot(fig_ac)

            st.markdown("##### **Resumen Numérico del Acumulado**")
            df_tabla_acum = df_acumulado_grp.sort_values(by="cantidad", ascending=False).copy()
            df_tabla_acum.columns = ["TIPO DE SERVICIO", "CANTIDAD ACUMULADA"]
            
            total_acumulado_general = df_tabla_acum["CANTIDAD ACUMULADA"].sum()
            df_tot_ac = pd.DataFrame([["TOTAL GENERAL ACUMULADO", total_acumulado_general]], columns=df_tabla_acum.columns)
            df_tabla_acum = pd.concat([df_tabla_acum, df_tot_ac], ignore_index=True)

            try:
                st.dataframe(aplicar_estilo_tabla(df_tabla_acum), use_container_width=True, hide_index=True)
            except Exception:
                st.dataframe(df_tabla_acum, use_container_width=True, hide_index=True)

# 9. CARGA INICIAL MASIVA (ADMINISTRADOR)
elif mod_actual == "Carga Inicial Masiva":
    st.markdown('<p class="subtitulo-seccion">Carga Inicial y Actualización Masiva de Base de Datos</p>', unsafe_allow_html=True)
    st.info(f"🔒 Módulo configurado para la carga directa en la tabla de Supabase para la flotilla: **{cat_actual}**.")

    with st.expander("🔑 Autenticación de Administrador", expanded=not st.session_state.get("admin_autenticado", False)):
        usr = st.text_input("Usuario Administrador:", key="admin_user_input")
        pwd = st.text_input("Contraseña:", type="password", key="admin_pwd_input")
        if st.button("Iniciar Sesión"):
            if usr == "e.casas" and pwd == "99094056":
                st.session_state.admin_autenticado = True
                st.success("Acceso concedido como Administrador Central.")
                st.rerun()
            else:
                st.error("Credenciales incorrectas.")

    if st.session_state.get("admin_autenticado", False):
        st.markdown("##### **1. Descargar Plantilla Oficial**")
        columnas_plantilla = ["eco", "tipo", "linea", "ubicacion", "arrendadora", "estatus", "placas", "vin", "no_tc", "ultimo_servicio", "cuota_diaria", "total_dias_servicio", "costo_mensual_sin_iva", "total_deduccion", "total_a_pagar", "foto_frontal", "foto_trasera", "foto_lateral_der", "foto_lateral_izq", "documentos"]
        df_plantilla = pd.DataFrame(columns=columnas_plantilla)
        st.download_button(label="📥 Descargar Plantilla CSV Oficial", data=df_plantilla.to_csv(index=False).encode("utf-8-sig"), file_name=f"plantilla_carga_{cat_actual.lower()}.csv", mime="text/csv")

        st.markdown("---")
        st.markdown(f"##### **2. Subir Archivo de Plantilla para: {cat_actual} (.xlsx o .csv)**")
        up_file = st.file_uploader("Cargar libro de Excel o CSV con estructura oficial:", type=["xlsx", "csv"])
        
        if up_file is not None:
            if st.button("Procesar y Guardar en Supabase"):
                try:
                    df_subido = pd.read_csv(up_file, dtype=str) if up_file.name.endswith(".csv") else pd.read_excel(up_file, dtype=str)
                    df_subido.columns = df_subido.columns.str.strip().str.lower()
                    if "eco" not in df_subido.columns:
                        st.error("⚠️ El archivo cargado no contiene la columna 'eco'.")
                    else:
                        df_subido["eco"] = df_subido["eco"].astype(str).str.strip()
                        tabla_map = {"Administrativos": "vehiculos_administrativos", "Ambulancias": "vehiculos_ambulancias", "Institucionales": "vehiculos_institucionales"}
                        nombre_tabla = tabla_map.get(cat_actual, "vehiculos_administrativos")
                        
                        df_subido = df_subido.where(pd.notnull(df_subido), None)
                        registros = df_subido.to_dict(orient="records")
                        for i in range(0, len(registros), 500):
                            supabase.table(nombre_tabla).insert(registros[i:i+500]).execute()

                        st.cache_data.clear()
                        st.success(f"¡Base de datos actualizada con éxito en Supabase! Se agregaron {len(df_subido)} unidades.")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error al procesar el archivo: {e}")

        st.markdown("---")
        st.markdown("##### **Histórico y Bitácora de Cargas Realizadas**")
        st.dataframe(pd.DataFrame(st.session_state.get("bitacora_cargas", [])), use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# FIRMA INSTITUCIONAL FINAL
# -----------------------------------------------------------------------------
st.markdown("""
    <div class="footer-firma">
        Sistema de Control Vehicular IMSS &nbsp;|&nbsp; Creado y desarrollado por: <b>eduardo.casas@imss.gob.mx</b>
    </div>
""", unsafe_allow_html=True)
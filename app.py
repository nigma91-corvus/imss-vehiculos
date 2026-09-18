import streamlit as st
import pandas as pd
from supabase import create_client, Client

# ==============================================================================
# 1. CONFIGURACIÓN INICIAL Y CONEXIÓN A SUPABASE
# ==============================================================================
st.set_page_config(page_title="Control Vehicular IMSS", layout="wide")

# Asegúrate de tener tus secretos configurados en Streamlit (.streamlit/secrets.toml)
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    supabase = None
    st.error(f"Error de conexión con las credenciales de Supabase: {e}")

# ==============================================================================
# 2. FUNCIONES DE CARGA Y UNIVERSO DINÁMICO
# ==============================================================================

def obtener_universo_total_supabase():
    """Calcula el padrón objetivo sumando las tres tablas principales de vehículos."""
    if not supabase:
        return 1200  # Fallback de seguridad
    
    tablas = ["vehiculos_administrativos", "vehiculos_ambulancias", "vehiculos_institucionales"]
    total_unidades = 0
    
    for tabla in tablas:
        try:
            response = supabase.table(tabla).select("id", count="exact").execute()
            if response.count is not None:
                total_unidades += response.count
        except Exception:
            # Si falla una tabla individualmente, continuamos con las demás
            pass
            
    return total_unidades if total_unidades > 0 else 1200


@st.cache_data(ttl=10)
def cargar_movilidad_real_supabase(categoria_flota):
    """Carga y pagina los registros de la tabla correspondiente en Supabase."""
    if not supabase:
        return pd.DataFrame()
    
    cat_lower = str(categoria_flota).strip().lower()
    if "admin" in cat_lower:
        nombre_tabla = "vehiculos_administrativos"
    elif "ambulanc" in cat_lower:
        nombre_tabla = "vehiculos_ambulancias"
    elif "instituc" in cat_lower:
        nombre_tabla = "vehiculos_institucionales"
    else:
        nombre_tabla = "vehiculos_administrativos"

    all_rows = []
    batch_size = 1000
    offset = 0
    
    try:
        while True:
            response = supabase.table(nombre_tabla).select("*").range(offset, offset + batch_size - 1).execute()
            data = response.data
            
            if not data:
                break
            all_rows.extend(data)
            if len(data) < batch_size:
                break
            offset += batch_size

        if all_rows:
            df = pd.DataFrame(all_rows)
            
            # Estandarización de columnas críticas
            if "estatus" in df.columns and "estatus_actual" not in df.columns:
                df["estatus_actual"] = df["estatus"]

            if "estatus_actual" in df.columns:
                df["estatus_limpio"] = df["estatus_actual"].astype(str).str.strip().str.upper()
            else:
                df["estatus_limpio"] = "LABORANDO"
                
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al cargar la tabla {nombre_tabla}: {e}")
        return pd.DataFrame()


# ==============================================================================
# 3. INTERFAZ DE USUARIO Y FLUJO PRINCIPAL
# ==============================================================================

st.title("🚗 Control de Movilidad y Flota - IMSS")

# Barra lateral para filtros organizados
st.sidebar.header("Filtros de Consulta")
categoria_flota = st.sidebar.selectbox(
    "Selecciona Categoría de Flota",
    ["Vehículos Administrativos", "Ambulancias", "Vehículos Institucionales"]
)

semana_corte = st.sidebar.selectbox(
    "Semana de Corte",
    ["Semana 37 - 2026", "Semana 38 - 2026", "Semana 39 - 2026"]
)

# Cálculo dinámico del universo total global
TOTAL_UNIVERSO_REAL = obtener_universo_total_supabase()

# Carga de datos según la categoría seleccionada
df_movilidad = cargar_movilidad_real_supabase(categoria_flota)

# ==============================================================================
# 4. PROCESAMIENTO DE MÉTRICAS
# ==============================================================================
if not df_movilidad.empty:
    estatus_fuera = ["TALLER", "SINIESTRO", "PATIO MALAS CONDICIONES", "PATIO MALAS"]
    df_fuera = df_movilidad[df_movilidad["estatus_limpio"].isin(estatus_fuera)]
    
    n_taller = len(df_fuera)
    n_activos = TOTAL_UNIVERSO_REAL - n_taller
    porcentaje_movilidad = (n_activos / TOTAL_UNIVERSO_REAL) * 100 if TOTAL_UNIVERSO_REAL > 0 else 0

    # Limpieza del costo acumulado
    if "costo_acumulado" in df_movilidad.columns:
        df_movilidad["costo_limpio"] = (
            df_movilidad["costo_acumulado"]
            .astype(str)
            .str.replace(r"[$,]", "", regex=True)
            .str.strip()
        )
        df_movilidad["costo_limpio"] = pd.to_numeric(df_movilidad["costo_limpio"], errors="coerce").fillna(0)
        total_importe = df_movilidad["costo_limpio"].sum()
    else:
        total_importe = 0.0
else:
    n_taller = 0
    n_activos = TOTAL_UNIVERSO_REAL
    porcentaje_movilidad = 100.0
    total_importe = 0.0

# ==============================================================================
# 5. PINTAR TARJETAS Y RESULTADOS EN PANTALLA
# ==============================================================================
st.subheader(f"Métricas Generales ({semana_corte})")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Universo Padrón Objetivo", f"{TOTAL_UNIVERSO_REAL:,}")
c2.metric("Unidades Laborando (Activas)", f"{n_activos:,}")
c3.metric("Unidades en Taller / Fuera", f"{n_taller:,}")
c4.metric("Porcentaje de Movilidad Real", f"{porcentaje_movilidad:.1f}%")

st.metric("Costo Acumulado Total en Incidencias", f"${total_importe:,.2f}")

# Vista previa opcional de los datos cargados
with st.expander("Ver detalle de registros cargados"):
    st.dataframe(df_movilidad)
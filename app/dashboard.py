"""Dashboard Ejecutivo de Inteligencia Comercial — Walmart California (FOODS · Diseño Apple Bento)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# Rutas portables relativas a la raíz del proyecto (autocontenido para Streamlit Cloud / Linux)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
METRICS_DIR = OUTPUTS_DIR / "metrics"
TABLES_DIR = OUTPUTS_DIR / "tables"

DASHBOARD_SALES_90D_PATH = DATA_PROCESSED_DIR / "dashboard_sales_90d.parquet"
ACTIVE_SALES_3Y_PATH = DATA_PROCESSED_DIR / "active_sales_3y.parquet"
VAL_WINDOW4_PRED_PATH = DATA_PROCESSED_DIR / "val_window4_predictions.parquet"
FORECAST_28D_PATH = DATA_PROCESSED_DIR / "forecast_28d.parquet"

STORES = ["CA_1", "CA_2", "CA_3", "CA_4"]
DEPARTMENTS = ["FOODS_1", "FOODS_2", "FOODS_3"]

# ---------------------------------------------------------------------------
# Configuración de página y tokens visuales (ver DESIGN.md)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Walmart California · Radar de Promociones e Ingresos en Riesgo",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="auto",
)

# Paleta Apple Bento (DESIGN.md Sección 2)
APPLE_BG = "#F5F5F7"
APPLE_SURFACE = "#FFFFFF"
APPLE_INK = "#1D1D1F"
APPLE_MUTED = "#6E6E73"
APPLE_BLUE = "#0071E3"
APPLE_BLUE_HOVER = "#0077ED"
APPLE_RED = "#D70015"
APPLE_AMBER = "#B25000"
APPLE_ORANGE = "#FF9500"
APPLE_GREEN = "#1E7E34"
APPLE_GREEN_BRIGHT = "#34C759"
APPLE_SNAP = "#9A6700"
APPLE_GRID = "#E5E5EA"
APPLE_BORDER = "#D2D2D7"

RISK_ORDER = ["Riesgo Alto", "Riesgo Medio", "Riesgo Bajo"]
RISK_COLORS = {
    "Riesgo Alto": APPLE_RED,
    "Riesgo Medio": APPLE_ORANGE,
    "Riesgo Bajo": APPLE_GREEN_BRIGHT,
}
STRATEGY_SHORT_LABELS = {
    "Cross-Selling y Visibilidad Omnicanal (Sin Descuento)": "Combos Cross-Selling (Sin descuento)",
    "Precios Dinámicos / Markdown (20%–35%)": "Descuentos Inteligentes (20%–35%)",
    "Sincronización SNAP (Base EDLP)": "Calendario SNAP (Sin descuento)",
    "Mantenimiento EDLP y Producto Ancla": "Precio Habitual (Producto Ancla)",
}
MARKDOWN = "Precios Dinámicos / Markdown (20%–35%)"
CROSS = "Cross-Selling y Visibilidad Omnicanal (Sin Descuento)"

# Supuestos de negocio (no se miden en los datos). Cambiarlos aquí actualiza todo el tablero.
ELASTICIDADES = {"Conservador": 0.4, "Esperado": 0.6, "Optimista": 0.8}
ESCENARIO_HISTORIAL = "Según historial (acotado)"
DESCUENTO_MIN, DESCUENTO_MAX, DESCUENTO_BASE = 20, 35, 25
AJUSTE_REPOSICION = "-20% a -30%"
# Umbrales de la regla documentada en plan/03 y src/config.py
INTERMITENCIA_CRITICA = 70.0
UMBRAL_SNAP_PCT = 15
AVISO_SIN_VENTAS = "Casi sin ventas"
AVISO_SIN_MONTO = "Alerta sin monto en riesgo"

# Vistas por tipo de usuario: cambian pestañas, filtros iniciales y vocabulario, nunca los cálculos.
VISTAS = {
    "gerente": {
        "nombre": "Gerente de marketing",
        "pestanas": [("resumen", "Resumen Ejecutivo"), ("producto", "Decisión por Producto")],
    },
    "gestor": {
        "nombre": "Gestor de categoría o precios",
        "pestanas": [
            ("resumen", "Cartera de Decisiones"),
            ("producto", "Decisión por Producto"),
            ("simulador", "Simulador y Plan"),
        ],
    },
    "analista": {
        "nombre": "Analista o docente",
        "pestanas": [
            ("auditoria", "Respaldo IA (Auditoría Técnica)"),
            ("resumen", "Resumen de Negocio"),
            ("producto", "Decisión por Producto"),
            ("simulador", "Simulador y Plan"),
        ],
    },
}

# Reemplazos en orden: primero las frases largas.
VOCABULARIO = {
    "gerente": [
        ("migración operativa LEFO→FEFO", "rotar primero lo que vence antes"),
        ("Combos Cross-Selling", "Venta conjunta"),
        ("Cross-Selling", "Venta conjunta"),
        ("en base EDLP", "con precio habitual"),
        ("(EDLP)", ""),
        ("rotación FEFO", "rotación de lo que vence antes"),
        ("Markdown", "Rebaja temporal"),
        ("EDLP", "precio habitual"),
    ],
    "gestor": [
        ("migración operativa LEFO→FEFO", "rotación FEFO"),
        ("Combos Cross-Selling", "Venta cruzada (combo)"),
        ("Cross-Selling", "Venta cruzada"),
        ("en base EDLP", "con precio habitual (EDLP)"),
        ("Markdown", "Rebaja táctica (markdown)"),
    ],
    "analista": [],
}


def tr(texto: str, vista: str) -> str:
    """Adapta un texto al vocabulario de la vista activa."""
    texto = str(texto)
    for viejo, nuevo in VOCABULARIO[vista]:
        texto = texto.replace(viejo, nuevo)
    return texto


def escenario_descuento(df: pd.DataFrame, d: float, eps: float | None) -> dict[str, float]:
    """Ingreso de 28 días sin y con rebaja.

    Con `eps` usa una respuesta supuesta igual para todos. Con `eps=None` usa la respuesta histórica de cada
    serie (price_sensitivity), entre 0 y el tope del escenario optimista: es una referencia, no una predicción.
    """
    unidades = df["pred_total_28d_units"].astype(float)
    precio = df["current_price"].astype(float)
    if eps is None:
        tope = (1.0 - d) ** (-max(ELASTICIDADES.values())) - 1.0
        lifts = df["price_sensitivity"].astype(float).fillna(0.0).clip(lower=0.0, upper=tope)
    else:
        lifts = pd.Series((1.0 - d) ** (-eps) - 1.0, index=df.index)
    base = float((unidades * precio).sum())
    rebaja = -d * base
    extra = float((unidades * lifts * precio * (1.0 - d)).sum())
    total_u = float(unidades.sum())
    extra_u = float((unidades * lifts).sum())
    return {
        "lift": extra_u / total_u if total_u else 0.0,
        "unidades_base": total_u,
        "unidades_extra": extra_u,
        "base": base,
        "rebaja": rebaja,
        "extra": extra,
        "con_rebaja": base + rebaja + extra,
        "neto": rebaja + extra,
        "lift_equilibrio": d / (1.0 - d),
    }


def usd_signo(v: float) -> str:
    return f"{'−' if v < 0 else '+'}${abs(v):,.0f}"


CLUSTER_PALETTE = [
    APPLE_RED,
    APPLE_BLUE,
    "#8E8E93",
    APPLE_ORANGE,
    APPLE_GREEN_BRIGHT,
    APPLE_INK,
]

CUSTOM_CSS = f"""
<style>
    /* Tipografía global Apple SF Pro / Inter */
    html, body, [class*="css"], .stApp {{
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Inter", "Segoe UI", sans-serif !important;
        color: {APPLE_INK};
    }}

    /* Ocultar chrome innecesario (Deploy, menú redundante y footer), preservando control del sidebar */
    [data-testid="stAppDeployButton"],
    .stDeployButton,
    #MainMenu,
    [data-testid="stMainMenu"],
    footer {{
        display: none !important;
    }}
    header[data-testid="stHeader"] {{
        background: transparent !important;
    }}

    /* Espaciado general limpio */
    .block-container {{
        padding-top: 1.5rem !important;
        padding-bottom: 2.5rem !important;
        max-width: 1440px;
    }}

    /* Encabezado editorial estilo Apple sobre lienzo #F5F5F7 */
    .apple-hero {{
        padding: 0.35rem 0 1.25rem 0;
        border-bottom: 1px solid rgba(0, 0, 0, 0.08);
        margin-bottom: 1.35rem;
    }}
    .apple-eyebrow {{
        color: {APPLE_BLUE};
        font-size: 0.76rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
    }}
    .apple-title {{
        color: {APPLE_INK};
        font-size: clamp(1.75rem, 2.5vw, 2.35rem);
        font-weight: 700;
        letter-spacing: -0.03em;
        line-height: 1.12;
        margin: 0 0 0.45rem 0;
    }}
    .apple-subtitle {{
        color: {APPLE_MUTED};
        font-size: clamp(0.95rem, 1.1vw, 1.05rem);
        font-weight: 400;
        line-height: 1.45;
        margin: 0;
        max-width: 920px;
    }}

    /* Pestañas estilo Apple minimalista */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 0.45rem;
        background-color: transparent;
        border-bottom: 1px solid rgba(0, 0, 0, 0.08);
        padding-bottom: 0.35rem;
        margin-bottom: 1.25rem;
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: transparent;
        border-radius: 999px;
        padding: 0.5rem 1.05rem;
        color: {APPLE_MUTED};
        font-weight: 600;
        font-size: 0.90rem;
        border: none;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {APPLE_SURFACE} !important;
        color: {APPLE_INK} !important;
        box-shadow: 0 1px 6px rgba(0, 0, 0, 0.08);
    }}
    .stTabs [data-baseweb="tab-highlight"] {{
        display: none !important;
    }}

    /* Rejillas Bento responsivas (cero truncado de cifras) */
    .bento-grid-4 {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 1rem;
        margin-bottom: 1.35rem;
    }}
    .bento-grid-3 {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 1rem;
        margin-bottom: 1.35rem;
    }}
    .bento-grid-5 {{
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 0.9rem;
        margin-bottom: 1.2rem;
    }}
    .bento-grid-6 {{
        display: grid;
        grid-template-columns: repeat(6, minmax(0, 1fr));
        gap: 0.85rem;
        margin-top: 1rem;
        margin-bottom: 1rem;
    }}
    @media (max-width: 1100px) {{
        .bento-grid-6 {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
        .bento-grid-5 {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
        .bento-grid-4 {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 768px) {{
        .bento-grid-3, .bento-grid-4, .bento-grid-5, .bento-grid-6 {{
            grid-template-columns: 1fr;
        }}
    }}

    /* Tarjeta Bento KPI */
    .kpi-card {{
        background: {APPLE_SURFACE};
        border: 1px solid rgba(0, 0, 0, 0.06);
        border-radius: 18px;
        padding: 1.15rem 1.25rem;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        min-height: 116px;
    }}
    .kpi-label {{
        color: {APPLE_MUTED};
        font-size: 0.80rem;
        font-weight: 600;
        line-height: 1.3;
        margin-bottom: 0.35rem;
    }}
    .kpi-value {{
        color: {APPLE_INK};
        font-size: clamp(1.28rem, 1.85vw, 1.80rem);
        font-weight: 700;
        letter-spacing: -0.025em;
        font-variant-numeric: tabular-nums;
        line-height: 1.15;
        white-space: nowrap;
        margin-bottom: 0.3rem;
    }}
    .kpi-value-sm {{
        color: {APPLE_INK};
        font-size: clamp(1.02rem, 1.35vw, 1.32rem);
        font-weight: 700;
        letter-spacing: -0.02em;
        font-variant-numeric: tabular-nums;
        line-height: 1.2;
        margin-bottom: 0.25rem;
    }}
    .kpi-sub {{
        color: {APPLE_MUTED};
        font-size: 0.78rem;
        line-height: 1.35;
    }}
    .kpi-accent-red {{ color: {APPLE_RED}; }}
    .kpi-accent-blue {{ color: {APPLE_BLUE}; }}
    .kpi-accent-amber {{ color: {APPLE_AMBER}; }}
    .kpi-accent-green {{ color: {APPLE_GREEN}; }}

    /* Tarjetas de 3 Decisiones Inmediatas */
    .section-heading {{
        color: {APPLE_INK};
        font-size: 1.12rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        margin: 0.2rem 0 0.75rem 0;
    }}
    .decision-card {{
        background: {APPLE_SURFACE};
        border: 1px solid rgba(0, 0, 0, 0.06);
        border-radius: 18px;
        padding: 1.25rem 1.35rem;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
        display: flex;
        flex-direction: column;
        gap: 0.45rem;
    }}
    .decision-top-blue {{ border-top: 3px solid {APPLE_BLUE}; }}
    .decision-top-amber {{ border-top: 3px solid {APPLE_AMBER}; }}
    .decision-top-green {{ border-top: 3px solid {APPLE_GREEN}; }}
    .decision-kicker {{
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }}
    .decision-title {{
        color: {APPLE_INK};
        font-size: 1.02rem;
        font-weight: 700;
        letter-spacing: -0.015em;
        line-height: 1.25;
    }}
    .decision-metric {{
        color: {APPLE_INK};
        font-size: 1.22rem;
        font-weight: 700;
        font-variant-numeric: tabular-nums;
    }}
    .decision-body {{
        color: {APPLE_MUTED};
        font-size: 0.84rem;
        line-height: 1.45;
    }}

    /* Contenedores Bento de Streamlit */
    div[data-testid="stVerticalBlockBorderWrapper"] {{
        background-color: {APPLE_SURFACE} !important;
        border: 1px solid rgba(0, 0, 0, 0.06) !important;
        border-radius: 18px !important;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04) !important;
        padding: 0.35rem 0.45rem !important;
    }}

    /* Encabezados de gráficos en forma de pregunta */
    .chart-question {{
        color: {APPLE_INK};
        font-size: 1.05rem;
        font-weight: 700;
        letter-spacing: -0.02em;
        margin: 0.15rem 0 0.2rem 0;
    }}
    .chart-takeaway {{
        color: {APPLE_MUTED};
        font-size: 0.84rem;
        margin: 0 0 0.65rem 0;
        line-height: 1.4;
    }}

    /* Tarjeta Semáforo de Decisión por Producto (Tab 2) */
    .semaphore-card {{
        background: {APPLE_SURFACE};
        border: 1px solid rgba(0, 0, 0, 0.06);
        border-radius: 18px;
        padding: 1.2rem 1.4rem;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
        margin: 0.6rem 0 1.1rem 0;
    }}
    .sem-high {{ border-left: 5px solid {APPLE_RED}; background: linear-gradient(90deg, #FFF7F7 0%, #FFFFFF 22%); }}
    .sem-med  {{ border-left: 5px solid {APPLE_AMBER}; background: linear-gradient(90deg, #FFFAF2 0%, #FFFFFF 22%); }}
    .sem-low  {{ border-left: 5px solid {APPLE_GREEN}; background: linear-gradient(90deg, #F3FCF5 0%, #FFFFFF 22%); }}
    .sem-headline {{
        color: {APPLE_INK};
        font-size: clamp(1.05rem, 1.4vw, 1.25rem);
        font-weight: 700;
        letter-spacing: -0.02em;
        margin: 0.45rem 0 0.3rem 0;
        line-height: 1.3;
    }}
    .sem-detail {{
        color: {APPLE_MUTED};
        font-size: 0.88rem;
        line-height: 1.45;
        margin: 0;
    }}

    /* Badges tipo píldora (DESIGN.md Sección 4) */
    .pill {{
        display: inline-block;
        padding: 0.22rem 0.7rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-right: 0.4rem;
        margin-bottom: 0.2rem;
    }}
    .pill-high {{ background: #FFF2F2; color: {APPLE_RED}; }}
    .pill-med  {{ background: #FFF8EB; color: {APPLE_AMBER}; }}
    .pill-low  {{ background: #EFFAF1; color: {APPLE_GREEN}; }}
    .pill-snap {{ background: #FFFBEB; color: {APPLE_SNAP}; border: 1px solid #FDE68A; }}
    .pill-info {{ background: #EFF6FF; color: {APPLE_BLUE}; }}

    /* Pills de multiselect y botón primario estilo Apple */
    span[data-baseweb="tag"] {{
        background-color: {APPLE_BLUE} !important;
        color: #FFFFFF !important;
        border-radius: 999px !important;
        padding-left: 0.55rem !important;
        padding-right: 0.45rem !important;
    }}
    span[data-baseweb="tag"] span,
    span[data-baseweb="tag"] svg {{
        color: #FFFFFF !important;
        fill: #FFFFFF !important;
    }}
    button[kind="primary"] {{
        background-color: {APPLE_BLUE} !important;
        color: #FFFFFF !important;
        border-radius: 999px !important;
        border: none !important;
        font-weight: 600 !important;
        padding: 0.5rem 1.2rem !important;
    }}
    button[kind="primary"]:hover {{
        background-color: {APPLE_BLUE_HOVER} !important;
    }}

    /* Indicador compacto del sidebar */
    .sidebar-counter {{
        background: #F5F5F7;
        border: 1px solid rgba(0, 0, 0, 0.06);
        border-radius: 12px;
        padding: 0.7rem 0.9rem;
        margin-top: 0.75rem;
        font-size: 0.82rem;
        color: {APPLE_MUTED};
        font-variant-numeric: tabular-nums;
    }}
    .sidebar-counter strong {{
        color: {APPLE_INK};
        font-size: 0.92rem;
    }}

    /* Nota sobria al pie */
    .footnote-box {{
        background: rgba(255, 255, 255, 0.75);
        border: 1px solid rgba(0, 0, 0, 0.06);
        border-radius: 14px;
        padding: 0.85rem 1.1rem;
        color: {APPLE_MUTED};
        font-size: 0.82rem;
        line-height: 1.5;
        margin-top: 1.1rem;
    }}
    .footnote-box strong {{
        color: {APPLE_INK};
    }}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers visuales y de formateo humano
# ---------------------------------------------------------------------------
def clean_sku_code(series_id: str) -> str:
    """Elimina el sufijo técnico '_evaluation' y extrae 'FOODS_3_282 · Tienda CA_3'."""
    raw = str(series_id).replace("_evaluation", "")
    parts = raw.rsplit("_", 2)
    if len(parts) == 3 and parts[1] == "CA":
        return f"{parts[0]} · Tienda CA_{parts[2]}"
    return raw


def apply_apple_plotly_theme(
    fig: go.Figure,
    *,
    height: int = 400,
    margin: dict | None = None,
    legend_bottom: bool = True,
    legend_y: float = -0.22,
    show_legend: bool = True,
) -> go.Figure:
    """Aplica estilo Apple minimalista (plotly_white, fondo #FFFFFF puro, grilla mínima #E5E5EA)."""
    default_margin = dict(t=32, b=88 if legend_bottom else 48, l=55, r=24)
    if margin:
        default_margin.update(margin)

    legend_cfg = (
        dict(
            orientation="h",
            yanchor="top",
            y=legend_y,
            xanchor="left",
            x=0.0,
            bgcolor="rgba(255,255,255,0.95)",
            font=dict(size=11.5, color=APPLE_INK),
            title_text="",
        )
        if legend_bottom
        else dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0.0,
            bgcolor="rgba(255,255,255,0.95)",
            font=dict(size=11.5, color=APPLE_INK),
            title_text="",
        )
    )

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor=APPLE_SURFACE,
        plot_bgcolor=APPLE_SURFACE,
        font=dict(
            family='-apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "Segoe UI", sans-serif',
            size=12,
            color=APPLE_INK,
        ),
        height=height,
        margin=default_margin,
        showlegend=show_legend,
        legend=legend_cfg,
        hoverlabel=dict(
            bgcolor=APPLE_SURFACE,
            bordercolor=APPLE_BORDER,
            font=dict(color=APPLE_INK, size=12),
        ),
    )
    fig.update_xaxes(
        showgrid=False,
        linecolor=APPLE_GRID,
        tickfont=dict(color=APPLE_MUTED, size=11),
        title_font=dict(color=APPLE_INK, size=12),
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor=APPLE_GRID,
        gridwidth=1,
        zerolinecolor=APPLE_GRID,
        linecolor=APPLE_GRID,
        tickfont=dict(color=APPLE_MUTED, size=11),
        title_font=dict(color=APPLE_INK, size=12),
    )
    return fig


def risk_pill_html(level: str) -> str:
    cls = {
        "Riesgo Alto": "pill-high",
        "Riesgo Medio": "pill-med",
        "Riesgo Bajo": "pill-low",
    }.get(level, "pill-low")
    return f'<span class="pill {cls}">{level}</span>'


def format_price_response_human(has_hist: bool, val: float) -> tuple[str, str, str]:
    """Traduce sensibilidad al precio a lenguaje gerencial claro sin truncar."""
    if (not has_hist) or pd.isna(val):
        return "Sin historial", "Sin rebajas previas · No descontar", ""
    pct = val * 100.0
    if val >= 0.10:
        return f"+{pct:.1f}%", "Responde bien · Apto para rebaja", "kpi-accent-green"
    if val < 0:
        return f"{pct:.1f}% (No rebajar)", "Vendió menos con rebaja (dato observado)", "kpi-accent-red"
    return f"+{pct:.1f}% (No rebajar)", "Respuesta débil · Usar combos", "kpi-accent-amber"


# ---------------------------------------------------------------------------
# Carga optimizada de datos reales con @st.cache_data
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Cargando diagnóstico comercial...")
def load_diagnosis() -> pd.DataFrame:
    df = pd.read_csv(TABLES_DIR / "sku_store_diagnosis.csv")
    df["suggested_anchor_item"] = df["suggested_anchor_item"].fillna("").astype(str)
    df["snap_priority"] = df["snap_priority"].astype(bool)
    df["stockpiling_alert"] = df["stockpiling_alert"].astype(bool)
    df["has_price_promo_history"] = df["has_price_promo_history"].astype(bool)
    df["strategy_short"] = df["primary_strategy"].map(STRATEGY_SHORT_LABELS).fillna(df["primary_strategy"])
    df["display_name"] = df["id"].map(clean_sku_code)
    # A1 / V8: avisos de presentación; no cambian la regla de riesgo documentada.
    casi_sin = (df["risk_level"] == "Riesgo Bajo") & (df["intermittency_pct"] >= INTERMITENCIA_CRITICA)
    sin_monto = (df["risk_level"] != "Riesgo Bajo") & (df["revenue_at_risk_usd"] <= 0)
    df["aviso"] = np.select([casi_sin, sin_monto], [AVISO_SIN_VENTAS, AVISO_SIN_MONTO], default="")
    # A2 / V7: la misma caída medida contra los últimos 28 días.
    df["riesgo_vs_28d_usd"] = (
        (df["sales_velocity_28d"] - df["pred_velocity_28d"]).clip(lower=0) * 28 * df["current_price"]
    )
    df["caida_previa"] = (df["revenue_at_risk_usd"] > 0) & (df["pred_velocity_28d"] >= df["sales_velocity_28d"])
    # V10: SNAP ocurre los días 1–10; los días 20–31 son un plan de cupones fuera de SNAP.
    df["snap_tactical_plan"] = (
        df["snap_tactical_plan"]
        .str.replace("Fase A (Días 1–10)", "Días SNAP (1–10)", regex=False)
        .str.replace(
            "Fase B (Días 20–31): cupones dirigidos de fin de mes",
            "Fin de mes, fuera de SNAP (días 20–31): cupones dirigidos",
            regex=False,
        )
    )
    df["tactical_action"] = df["tactical_action"].str.replace(
        "demanda inelástica o sin historial promocional",
        "respuesta baja o negativa, o sin historial de rebajas",
        regex=False,
    )
    return df


@st.cache_data(show_spinner="Cargando tablas de auditoría IA...")
def load_validation_and_kmeans() -> dict[str, pd.DataFrame]:
    return {
        "val_summary": pd.read_csv(TABLES_DIR / "validation_metrics_summary.csv"),
        "val_by_window": pd.read_csv(TABLES_DIR / "validation_metrics_by_window.csv"),
        "val_breakdown": pd.read_csv(TABLES_DIR / "validation_breakdown_store_snap.csv"),
        "feature_importance": pd.read_csv(TABLES_DIR / "feature_importance.csv"),
        "kmeans_eval": pd.read_csv(TABLES_DIR / "kmeans_evaluation.csv"),
        "kmeans_profiles": pd.read_csv(TABLES_DIR / "kmeans_cluster_profiles.csv"),
    }


@st.cache_data(show_spinner="Cargando últimos 90 días reales...")
def load_history_90d() -> pd.DataFrame:
    """Lee el dataset ligero de 90 días; usa active_sales_3y.parquet como respaldo local."""
    cols = ["id", "date", "units_sold", "sell_price", "snap_CA"]
    if DASHBOARD_SALES_90D_PATH.exists():
        df = pd.read_parquet(DASHBOARD_SALES_90D_PATH, columns=cols)
    elif ACTIVE_SALES_3Y_PATH.exists():
        df = pd.read_parquet(
            ACTIVE_SALES_3Y_PATH,
            columns=cols,
            filters=[("date", ">=", pd.read_parquet(FORECAST_28D_PATH, columns=["date"])["date"].min() - pd.Timedelta(days=90))],
        )
    else:
        raise FileNotFoundError(
            "No se encontró ni 'data/processed/dashboard_sales_90d.parquet' "
            "ni 'data/processed/active_sales_3y.parquet'."
        )
    df["id"] = df["id"].astype(str)
    return df


@st.cache_data(show_spinner="Cargando pronóstico de 28 días...")
def load_predictions() -> tuple[pd.DataFrame, pd.DataFrame]:
    val_w4 = pd.read_parquet(
        VAL_WINDOW4_PRED_PATH,
        columns=["id", "date", "units_sold", "pred_rf", "pred_ses", "pred_ma28", "pred_snaive"],
    )
    val_w4["id"] = val_w4["id"].astype(str)
    forecast = pd.read_parquet(
        FORECAST_28D_PATH,
        columns=["id", "date", "sell_price", "snap_CA", "pred_units"],
    )
    forecast["id"] = forecast["id"].astype(str)
    return val_w4, forecast


@st.cache_data(show_spinner=False)
def load_audits() -> dict[str, dict]:
    audits: dict[str, dict] = {}
    for key, fname in (
        ("etl", "etl_audit.json"),
        ("validation", "validation_audit.json"),
        ("diagnosis", "diagnosis_audit.json"),
    ):
        path = METRICS_DIR / fname
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                audits[key] = json.load(f)
        else:
            audits[key] = {}
    return audits


def get_contiguous_iso_spans(dates: pd.Series) -> list[tuple[str, str]]:
    """Agrupa fechas consecutivas en pares ISO ('YYYY-MM-DD', 'YYYY-MM-DD') para add_shape."""
    sorted_dates = sorted(pd.to_datetime(dates.dropna().unique()))
    if not sorted_dates:
        return []
    spans: list[tuple[str, str]] = []
    start = prev = sorted_dates[0]
    for dt in sorted_dates[1:]:
        if (dt - prev).days == 1:
            prev = dt
        else:
            spans.append((start.strftime("%Y-%m-%d"), (prev + pd.Timedelta(days=1)).strftime("%Y-%m-%d")))
            start = prev = dt
    spans.append((start.strftime("%Y-%m-%d"), (prev + pd.Timedelta(days=1)).strftime("%Y-%m-%d")))
    return spans


def build_forecast_figure(
    selected_id: str,
    h_sub: pd.DataFrame,
    w4_sub: pd.DataFrame,
    f_sub: pd.DataFrame,
    show_baselines: bool = False,
) -> go.Figure:
    """Construye la curva temporal de Tab 2 con fechas ISO string ('YYYY-MM-DD') y estética Apple."""
    h_sub = h_sub.sort_values("date").copy()
    w4_sub = w4_sub.sort_values("date").copy()
    f_sub = f_sub.sort_values("date").copy()

    h_dates = pd.to_datetime(h_sub["date"]).dt.strftime("%Y-%m-%d").tolist()
    h_sales = h_sub["units_sold"].astype(float).tolist()

    w4_dates = pd.to_datetime(w4_sub["date"]).dt.strftime("%Y-%m-%d").tolist()
    w4_rf = w4_sub["pred_rf"].astype(float).tolist()

    f_dates = pd.to_datetime(f_sub["date"]).dt.strftime("%Y-%m-%d").tolist()
    f_pred = f_sub["pred_units"].astype(float).tolist()

    price_series = (
        pd.concat(
            [h_sub[["date", "sell_price", "snap_CA"]], f_sub[["date", "sell_price", "snap_CA"]]],
            ignore_index=True,
        )
        .drop_duplicates(subset=["date"])
        .sort_values("date")
    )
    p_dates = pd.to_datetime(price_series["date"]).dt.strftime("%Y-%m-%d").tolist()
    p_vals = price_series["sell_price"].astype(float).tolist()
    snap_spans = get_contiguous_iso_spans(price_series.loc[price_series["snap_CA"] == 1, "date"])

    fig_ts = make_subplots(specs=[[{"secondary_y": True}]])

    # Franjas amarillas muy suaves (#FEF3C7) para días de pago SNAP
    for x0_iso, x1_iso in snap_spans:
        fig_ts.add_shape(
            type="rect",
            xref="x",
            yref="paper",
            x0=x0_iso,
            x1=x1_iso,
            y0=0.0,
            y1=1.0,
            fillcolor="rgba(254, 243, 199, 0.58)",
            line=dict(width=0),
            layer="below",
        )

    fig_ts.add_trace(
        go.Scatter(
            x=[None],
            y=[None],
            mode="markers",
            marker=dict(size=10, color="#FDE68A", symbol="square"),
            name="Días de pago SNAP",
        ),
        secondary_y=False,
    )

    fig_ts.add_trace(
        go.Scatter(
            x=h_dates,
            y=h_sales,
            mode="lines",
            name="Ventas reales (90 días)",
            line=dict(color=APPLE_INK, width=2.0),
            hovertemplate="Ventas reales: %{y:.0f} u.<extra></extra>",
        ),
        secondary_y=False,
    )
    fig_ts.add_trace(
        go.Scatter(
            x=w4_dates,
            y=w4_rf,
            mode="lines",
            name="Prueba reciente del pronóstico",
            line=dict(color=APPLE_BLUE, width=2.2, dash="dash"),
            hovertemplate="Prueba reciente: %{y:.2f} u.<extra></extra>",
        ),
        secondary_y=False,
    )

    if show_baselines:
        fig_ts.add_trace(
            go.Scatter(
                x=w4_dates,
                y=w4_sub["pred_ses"].astype(float).tolist(),
                mode="lines",
                name="Referencia SES",
                line=dict(color=APPLE_GREEN_BRIGHT, width=1.6, dash="dot"),
                hovertemplate="SES: %{y:.2f} u.<extra></extra>",
            ),
            secondary_y=False,
        )
        fig_ts.add_trace(
            go.Scatter(
                x=w4_dates,
                y=w4_sub["pred_ma28"].astype(float).tolist(),
                mode="lines",
                name="Referencia MA28",
                line=dict(color=APPLE_ORANGE, width=1.6, dash="dot"),
                hovertemplate="MA28: %{y:.2f} u.<extra></extra>",
            ),
            secondary_y=False,
        )

    fig_ts.add_trace(
        go.Scatter(
            x=f_dates,
            y=f_pred,
            mode="lines+markers",
            name="Pronóstico próximos 28 días",
            line=dict(color=APPLE_RED, width=2.6),
            marker=dict(size=4.5, color=APPLE_RED),
            hovertemplate="Pronóstico IA: %{y:.2f} u.<extra></extra>",
        ),
        secondary_y=False,
    )
    fig_ts.add_trace(
        go.Scatter(
            x=p_dates,
            y=p_vals,
            mode="lines",
            name="Precio en tienda (USD)",
            line=dict(color="#8E8E93", width=1.4, dash="dot"),
            hovertemplate="Precio: $%{y:.2f} USD<extra></extra>",
        ),
        secondary_y=True,
    )

    # Línea vertical de corte en formato ISO (cero timestamps numéricos)
    cierre = pd.to_datetime(f_sub["date"]).min() - pd.Timedelta(days=1)
    cutoff_iso = cierre.strftime("%Y-%m-%d")
    fig_ts.add_shape(
        type="line",
        xref="x",
        yref="paper",
        x0=cutoff_iso,
        x1=cutoff_iso,
        y0=0.0,
        y1=1.0,
        line=dict(color="#8E8E93", width=1.5, dash="dot"),
    )
    fig_ts.add_annotation(
        x=cutoff_iso,
        y=1.05,
        xref="x",
        yref="paper",
        text=f"Cierre histórico ({cierre:%d/%m/%Y}) · Inicio pronóstico 28d",
        showarrow=False,
        xanchor="right",
        font=dict(size=11, color=APPLE_MUTED),
        bgcolor=APPLE_BG,
        bordercolor=APPLE_GRID,
        borderwidth=1,
        borderpad=4,
    )

    apply_apple_plotly_theme(
        fig_ts,
        height=440,
        margin=dict(t=46, b=88, l=55, r=58),
        legend_bottom=True,
        legend_y=-0.20,
    )
    fig_ts.update_layout(hovermode="x unified")
    fig_ts.update_xaxes(
        type="date",
        tickformat="%d %b %Y",
        title_text="",
        range=[
            (cierre - pd.Timedelta(days=90)).strftime("%Y-%m-%d"),
            (pd.to_datetime(f_sub["date"]).max() + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
        ],
    )
    fig_ts.update_yaxes(
        title_text="Unidades por día",
        secondary_y=False,
        rangemode="tozero",
    )
    if p_vals:
        p_min, p_max = min(p_vals), max(p_vals)
        p_pad = max((p_max - p_min) * 0.35, 0.15)
        p_range = [max(0.0, round(p_min - p_pad, 2)), round(p_max + p_pad, 2)]
    else:
        p_range = None
    fig_ts.update_yaxes(
        title_text="Precio (USD)",
        secondary_y=True,
        showgrid=False,
        tickformat="$.2f",
        range=p_range,
    )
    return fig_ts


VACIO = "-"  # marca en la URL para una selección sin opciones
ESTRATEGIA_URL = {
    "rebaja": MARKDOWN,
    "combo": CROSS,
    "snap": "Sincronización SNAP (Base EDLP)",
    "habitual": "Mantenimiento EDLP y Producto Ancla",
}


def valores_por_defecto(vista: str, clusters: list[str]) -> dict:
    gestor = vista == "gestor"
    return {
        "tienda": list(STORES),
        "depto": list(DEPARTMENTS),
        f"riesgo_{vista}": RISK_ORDER[:2] if gestor else list(RISK_ORDER),
        "q": "",
        f"estrategia_{vista}": [MARKDOWN, CROSS] if gestor else list(ESTRATEGIA_URL.values()),
        "grupo": list(clusters),
        "snap": False,
        f"usd_{vista}": gestor,
    }


def _codigos(clave: str, clusters: list[str]) -> dict[str, str] | None:
    """Relación código de URL -> valor para los filtros de selección múltiple."""
    if clave == "tienda":
        return {v: v for v in STORES}
    if clave == "depto":
        return {v: v for v in DEPARTMENTS}
    if clave.startswith("riesgo"):
        return {v.split()[-1].lower(): v for v in RISK_ORDER}
    if clave.startswith("estrategia"):
        return ESTRATEGIA_URL
    if clave == "grupo":
        return {str(i): v for i, v in enumerate(clusters)}
    return None


def _nombre_url(clave: str) -> str:
    return clave.split("_")[0]


def iniciar_filtros(vista: str, clusters: list[str]) -> None:
    """Carga cada filtro desde la URL (primera vez) o su valor por defecto, y conserva lo elegido."""
    cambio_de_vista = st.session_state.get("_vista_previa") not in (None, vista)
    if cambio_de_vista:
        # Estos filtros son propios de cada vista: la URL de la vista anterior no se aplica.
        for nombre in ("riesgo", "estrategia", "usd"):
            st.query_params.pop(nombre, None)
    st.session_state["_vista_previa"] = vista
    for clave, defecto in valores_por_defecto(vista, clusters).items():
        if clave in st.session_state:
            # Reasignar evita que Streamlit descarte el valor de un control que no se dibujó.
            st.session_state[clave] = st.session_state[clave]
            continue
        valor = defecto
        nombre = _nombre_url(clave)
        if nombre in st.query_params:
            codigos = _codigos(clave, clusters)
            if codigos is not None:
                crudos = st.query_params.get_all(nombre)
                validos = [codigos[c] for c in crudos if c in codigos]
                if validos or crudos == [VACIO]:
                    valor = validos
            elif isinstance(defecto, bool):
                valor = st.query_params[nombre] == "1"
            else:
                valor = st.query_params[nombre]
        st.session_state[clave] = valor


def guardar_filtros_en_url(vista: str, clusters: list[str]) -> None:
    """La URL refleja solo lo que difiere del valor por defecto, para poder compartirla."""
    for clave, defecto in valores_por_defecto(vista, clusters).items():
        nombre = _nombre_url(clave)
        if clave not in st.session_state:
            continue
        valor = st.session_state[clave]
        codigos = _codigos(clave, clusters)
        igual = sorted(valor) == sorted(defecto) if codigos is not None else valor == defecto
        if igual:
            st.query_params.pop(nombre, None)
        elif codigos is not None:
            inverso = {v: c for c, v in codigos.items()}
            st.query_params[nombre] = [inverso[v] for v in valor] or [VACIO]
        elif isinstance(defecto, bool):
            st.query_params[nombre] = "1" if valor else "0"
        else:
            st.query_params[nombre] = valor


def restablecer_filtros(vista: str, clusters: list[str]) -> None:
    for clave, defecto in valores_por_defecto(vista, clusters).items():
        st.session_state[clave] = defecto
        st.query_params.pop(_nombre_url(clave), None)


def motivo_sin_resultados(mascaras: dict[str, pd.Series]) -> str:
    """Indica qué filtro, al quitarse, devolvería resultados."""
    culpables = []
    for nombre in mascaras:
        resto = [m for n, m in mascaras.items() if n != nombre]
        if resto and np.logical_and.reduce(resto).any():
            culpables.append(nombre)
    if culpables:
        return "Revisa: **" + "**, **".join(culpables) + "**. Al ampliar cualquiera de ellos vuelven los resultados."
    return "Hay más de un filtro que deja la selección vacía. Usa **Restablecer filtros**."


def _slot(tab, aviso: str | None = None):
    """Dibuja el bloque solo si la vista activa tiene esa pestaña; si no hay datos, explica por qué."""
    if tab is not None:
        with tab:
            if aviso:
                st.warning(aviso)
            else:
                yield


def grafico_riesgo_evidencia(df: pd.DataFrame, vista: str) -> None:
    """G5: cuánto del riesgo tiene evidencia sobre la respuesta a rebajas."""
    cs = df["primary_strategy"] == CROSS
    hist = df["has_price_promo_history"]
    grupos = [
        ("Respondió a rebajas", df["primary_strategy"] == MARKDOWN, APPLE_BLUE),
        ("Respuesta baja<br>o negativa", cs & hist, APPLE_ORANGE),
        ("Sin historial<br>de rebajas", cs & ~hist, "#8E8E93"),
        ("Riesgo bajo", df["risk_level"] == "Riesgo Bajo", APPLE_GREEN_BRIGHT),
    ]
    nombres = [g[0] for g in grupos]
    montos = [float(df.loc[g[1], "revenue_at_risk_usd"].sum()) for g in grupos]
    series = [int(g[1].sum()) for g in grupos]
    total = sum(montos)
    sin_hist_pct = montos[2] / total * 100.0 if total > 0 else 0.0
    st.markdown('<div class="chart-question">¿Qué sabemos sobre el ingreso en riesgo?</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="chart-takeaway">El <strong>{sin_hist_pct:.1f}%</strong> está en productos por tienda '
        "sin historial suficiente de rebajas: no se sabe si responderían.</div>",
        unsafe_allow_html=True,
    )
    fig = go.Figure(
        go.Bar(
            x=montos,
            y=nombres,
            orientation="h",
            marker_color=[g[2] for g in grupos],
            text=[f"${m:,.0f} · {n:,}" for m, n in zip(montos, series)],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}<br>$%{x:,.0f} en riesgo<extra></extra>",
        )
    )
    apply_apple_plotly_theme(fig, height=370, margin=dict(l=125, r=95, t=20, b=45), show_legend=False)
    fig.update_xaxes(title_text="USD en riesgo · productos por tienda", tickprefix="$", nticks=4, tickangle=0,
                     range=[0, max(max(montos) * 1.55, 10.0)])
    fig.update_yaxes(autorange="reversed", showgrid=False, automargin=False)
    st.plotly_chart(fig, width="stretch", theme=None)


def grafico_caidas_subidas(df: pd.DataFrame) -> None:
    """G1: las caídas (riesgo) frente a las subidas pronosticadas."""
    caidas = float(df["revenue_at_risk_usd"].sum())
    delta = (df["pred_velocity_28d"] - df["sales_velocity_90d"]) * 28 * df["current_price"]
    subidas = float(delta.clip(lower=0).sum())
    neto = subidas - caidas
    st.markdown('<div class="chart-question">¿Cae toda la venta o solo parte del catálogo?</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="chart-takeaway">Frente al ritmo de los últimos 90 días: caídas por <strong>${caidas:,.0f}</strong>, '
        f"subidas por <strong>${subidas:,.0f}</strong> y saldo de <strong>{usd_signo(neto)}</strong>. "
        "El ingreso en riesgo suma solo las caídas. Aquí solo aplican tienda, departamento y búsqueda.</div>",
        unsafe_allow_html=True,
    )
    fig = go.Figure(
        go.Waterfall(
            x=["Caídas", "Subidas", "Saldo"],
            y=[-caidas, subidas, neto],
            measure=["relative", "relative", "total"],
            text=[usd_signo(-caidas), usd_signo(subidas), usd_signo(neto)],
            textposition="outside",
            decreasing=dict(marker=dict(color=APPLE_RED)),
            increasing=dict(marker=dict(color=APPLE_GREEN_BRIGHT)),
            totals=dict(marker=dict(color=APPLE_BLUE)),
            cliponaxis=False,
        )
    )
    apply_apple_plotly_theme(fig, height=340, margin=dict(t=30, b=40, l=70, r=24), show_legend=False)
    alto = max(subidas - caidas, 0.0)
    holgura = max(caidas, subidas, 1.0) * 0.25
    fig.update_yaxes(title_text="USD en 28 días", tickprefix="$",
                     range=[-caidas - holgura, alto + holgura])
    st.plotly_chart(fig, width="stretch", theme=None)


def grafico_tienda_departamento(df: pd.DataFrame) -> None:
    """G4: ingreso en riesgo por tienda y departamento."""
    tabla = df.pivot_table(index="dept_id", columns="store_id", values="revenue_at_risk_usd", aggfunc="sum", fill_value=0)
    pila = tabla.stack()
    depto, tienda = pila.idxmax()
    st.markdown('<div class="chart-question">¿Qué departamento de qué tienda pesa más?</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="chart-takeaway"><strong>{depto}</strong> en <strong>{tienda}</strong> suma ${pila.max():,.0f} en riesgo.</div>',
        unsafe_allow_html=True,
    )
    fig = px.imshow(
        tabla,
        text_auto=",.0f",
        aspect="auto",
        color_continuous_scale=["#EFF6FF", APPLE_BLUE],
        labels=dict(x="", y="", color="USD"),
    )
    apply_apple_plotly_theme(fig, height=340, margin=dict(t=20, b=40, l=80, r=20), show_legend=False)
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(fig, width="stretch", theme=None)


def grafico_series_por_riesgo(df: pd.DataFrame, vista: str) -> None:
    """Distribución de series por estrategia y nivel de riesgo."""
    datos = df.groupby(["strategy_short", "risk_level"], as_index=False).size()
    mayor = datos.groupby("strategy_short")["size"].sum()
    st.markdown('<div class="chart-question">¿Cuántos productos por tienda hay en cada acción?</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="chart-takeaway">La acción con más casos es <strong>{mayor.idxmax()}</strong> ({mayor.max():,}).</div>',
        unsafe_allow_html=True,
    )
    fig = px.bar(
        datos,
        x="size",
        y="strategy_short",
        color="risk_level",
        orientation="h",
        category_orders={"risk_level": RISK_ORDER},
        color_discrete_map=RISK_COLORS,
        labels={"size": "Productos por tienda", "strategy_short": "", "risk_level": ""},
    )
    apply_apple_plotly_theme(fig, height=340, margin=dict(t=20, b=80, l=150, r=20), legend_y=-0.24)
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(fig, width="stretch", theme=None)


def grafico_error_por_ventana(val_by_window: pd.DataFrame) -> None:
    """A1: error de cada método en cada ventana de validación."""
    metrica = st.radio("Métrica de error:", ["RMSE", "MAE", "RMSSE"], horizontal=True)
    col = metrica.lower()
    rf = val_by_window.loc[val_by_window["model"] == "Random Forest"].set_index("window")[col]
    mejor = val_by_window.groupby("window")[col].min()
    ganadas = int((rf <= mejor.reindex(rf.index)).sum())
    st.markdown(
        f'<div class="chart-takeaway">Random Forest tiene el menor {metrica} en <strong>{ganadas} de {len(rf)}</strong> '
        "ventanas. Menor es mejor. El eje no empieza en cero para ver las diferencias.</div>",
        unsafe_allow_html=True,
    )
    fig = px.line(
        val_by_window,
        x="window",
        y=col,
        color="model",
        markers=True,
        color_discrete_map={
            "Random Forest": APPLE_BLUE,
            "SES (NumPy)": APPLE_GREEN_BRIGHT,
            "MA28": APPLE_ORANGE,
            "Seasonal Naïve (lag_28)": "#8E8E93",
        },
        labels={"window": "Ventana de 28 días", col: metrica, "model": ""},
    )
    apply_apple_plotly_theme(fig, height=360, legend_y=-0.22)
    fig.update_xaxes(dtick=1)
    st.plotly_chart(fig, width="stretch", theme=None)


def calcular_senal_caida(hist90: pd.DataFrame, w4: pd.DataFrame, umbral: float) -> pd.DataFrame:
    """A2: ¿las caídas anunciadas en la ventana 4 ocurrieron? Compara tres periodos base."""
    inicio = w4["date"].min()
    previo = hist90.loc[hist90["date"] < inicio]
    dias = previo["date"].nunique()
    bases = {
        f"{dias} días previos": previo,
        "28 días previos": previo.loc[previo["date"] >= inicio - pd.Timedelta(days=28)],
        f"Primeros {dias - 28} días": previo.loc[previo["date"] < inicio - pd.Timedelta(days=28)],
    }
    real = w4.groupby("id")["units_sold"].mean()
    pred = {
        "Random Forest": w4.groupby("id")["pred_rf"].mean(),
        "SES": w4.groupby("id")["pred_ses"].mean(),
        "MA28": w4.groupby("id")["pred_ma28"].mean(),
    }
    filas = []
    for nombre_base, tramo in bases.items():
        base = tramo.groupby("id")["units_sold"].mean()
        base = base[base > 0]
        cayo = (base - real.reindex(base.index)) / base >= umbral
        for modelo, p in pred.items():
            aviso = (base - p.reindex(base.index)) / base >= umbral
            n_aviso, n_cayo = int(aviso.sum()), int(cayo.sum())
            aciertos = int((aviso & cayo).sum())
            filas.append(
                {
                    "Periodo base": nombre_base,
                    "Método": modelo,
                    "Avisos": n_aviso,
                    "Acierto (%)": aciertos / n_aviso * 100.0 if n_aviso else np.nan,
                    "Series que cayeron, referencia (%)": cayo.mean() * 100.0,
                    "Caídas detectadas (%)": aciertos / n_cayo * 100.0 if n_cayo else np.nan,
                }
            )
    return pd.DataFrame(filas)


def grafico_senal_caida(hist90: pd.DataFrame, w4: pd.DataFrame) -> None:
    umbral = st.select_slider("Caída mínima que se considera aviso:", options=[10, 20, 30], value=20, format_func=lambda v: f"{v}%")
    res = calcular_senal_caida(hist90, w4, umbral / 100.0)
    st.markdown(
        '<div class="chart-takeaway">Compare cada barra con el rombo: es la proporción de series que cayó, '
        "se avisara o no. <strong>El resultado cambia mucho según el periodo base</strong>; es una sola ventana y "
        "no usa la regla de riesgo del tablero (90 días e intermitencia). Con la base de 28 días, MA28 no emite avisos "
        "porque su pronóstico es esa misma base.</div>",
        unsafe_allow_html=True,
    )
    fig = px.bar(
        res,
        x="Periodo base",
        y="Acierto (%)",
        color="Método",
        barmode="group",
        hover_data={"Avisos": True, "Caídas detectadas (%)": ":.1f"},
        color_discrete_map={"Random Forest": APPLE_BLUE, "SES": APPLE_GREEN_BRIGHT, "MA28": APPLE_ORANGE},
    )
    ref = res.drop_duplicates("Periodo base")
    fig.add_trace(
        go.Scatter(
            x=ref["Periodo base"],
            y=ref["Series que cayeron, referencia (%)"],
            mode="markers",
            marker=dict(symbol="diamond", size=13, color=APPLE_INK),
            name="Proporción que cayó (referencia)",
        )
    )
    apply_apple_plotly_theme(fig, height=370, legend_y=-0.22)
    fig.update_yaxes(range=[0, 100], title_text="Avisos que sí cayeron (%)")
    st.plotly_chart(fig, width="stretch", theme=None)
    st.dataframe(
        res,
        width="stretch",
        hide_index=True,
        column_config={c: st.column_config.NumberColumn(c, format="%.1f") for c in res.columns if "(%)" in c},
    )


def main() -> None:
    # -----------------------------------------------------------------------
    # Encabezado editorial estilo Apple (sin banner oscuro ni cajas de pasos)
    # -----------------------------------------------------------------------
    st.markdown(
        """
        <div class="apple-hero">
            <div class="apple-eyebrow">WALMART CALIFORNIA · INTELIGENCIA COMERCIAL</div>
            <h1 class="apple-title">Radar de Promociones e Ingresos en Riesgo</h1>
            <p class="apple-subtitle">
                Identifica qué alimentos venderían menos que en sus últimos 90 días según el pronóstico a 28 días, cuánto ingreso representa y qué acción conviene probar.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    diag_df = load_diagnosis()
    tables = load_validation_and_kmeans()
    audits = load_audits()

    # -----------------------------------------------------------------------
    # Sidebar minimalista y amigable para marketing
    # -----------------------------------------------------------------------
    claves = list(VISTAS)
    if "vista" not in st.session_state:
        inicial = st.query_params.get("vista", "gerente")
        st.session_state["vista"] = inicial if inicial in claves else "gerente"
    vista = st.sidebar.selectbox(
        "Ver como",
        options=claves,
        format_func=lambda k: VISTAS[k]["nombre"],
        key="vista",
    )
    st.query_params["vista"] = vista
    es_gestor = vista == "gestor"

    st.sidebar.markdown("#### Filtrar catálogo")

    cluster_options = tables["kmeans_profiles"]["cluster_name"].tolist()
    iniciar_filtros(vista, cluster_options)

    def con_total(columna: str, etiqueta=str):
        totales = diag_df[columna].value_counts()
        return lambda x: f"{etiqueta(x)} ({totales.get(x, 0):,})"

    def estrategia_corta(x: str) -> str:
        return tr(STRATEGY_SHORT_LABELS.get(x, x).split(" (")[0], vista)

    sel_stores = st.sidebar.multiselect("Tiendas", options=STORES, format_func=con_total("store_id"), key="tienda")
    sel_depts = st.sidebar.multiselect("Departamentos", options=DEPARTMENTS, format_func=con_total("dept_id"), key="depto")
    sel_risks = st.sidebar.multiselect(
        "Nivel de prioridad", options=RISK_ORDER, format_func=con_total("risk_level"), key=f"riesgo_{vista}"
    )
    search_sku = st.sidebar.text_input("Buscar producto", placeholder="Ej. FOODS_3_282 o CA_3", key="q")
    sel_strategies = st.sidebar.multiselect(
        "Estrategia recomendada",
        options=list(ESTRATEGIA_URL.values()),
        format_func=con_total("primary_strategy", estrategia_corta),
        key=f"estrategia_{vista}",
    )
    sel_clusters = st.sidebar.multiselect(
        "Grupo comercial", options=cluster_options, format_func=con_total("cluster_name"), key="grupo"
    )
    only_snap_prio = st.sidebar.toggle("Solo sensibles a pagos SNAP", key="snap")
    only_usd = es_gestor and st.sidebar.toggle("Solo con ingreso en riesgo mayor que $0", key=f"usd_{vista}")
    st.sidebar.button(
        "Restablecer filtros", on_click=restablecer_filtros, args=(vista, cluster_options), width="stretch"
    )
    st.sidebar.caption("Entre paréntesis: total de productos por tienda en todo el portafolio.")
    guardar_filtros_en_url(vista, cluster_options)

    mascaras = {
        "Tiendas": diag_df["store_id"].isin(sel_stores),
        "Departamentos": diag_df["dept_id"].isin(sel_depts),
        "Nivel de prioridad": diag_df["risk_level"].isin(sel_risks),
        "Estrategia recomendada": diag_df["primary_strategy"].isin(sel_strategies),
        "Grupo comercial": diag_df["cluster_name"].isin(sel_clusters),
    }
    if only_usd:
        mascaras["Solo con ingreso en riesgo"] = diag_df["revenue_at_risk_usd"] > 0
    if only_snap_prio:
        mascaras["Solo sensibles a SNAP"] = diag_df["snap_priority"]
    if search_sku.strip():
        q = search_sku.strip().lower()
        mascaras["Buscar producto"] = (
            diag_df["id"].str.lower().str.contains(q, regex=False)
            | diag_df["item_id"].str.lower().str.contains(q, regex=False)
            | diag_df["display_name"].str.lower().str.contains(q, regex=False)
        )
    mask = pd.Series(np.logical_and.reduce(list(mascaras.values())), index=diag_df.index)

    filtered_df = diag_df.loc[mask].copy()
    # Alcance por tienda, departamento y búsqueda: base del gráfico de caídas y subidas.
    alcance = diag_df["store_id"].isin(sel_stores) & diag_df["dept_id"].isin(sel_depts)
    if search_sku.strip():
        q = search_sku.strip().lower()
        alcance &= diag_df["id"].str.lower().str.contains(q, regex=False) | diag_df["display_name"].str.lower().str.contains(q, regex=False)
    alcance_df = diag_df.loc[alcance]
    filtered_df["strategy_short"] = filtered_df["strategy_short"].map(lambda x: tr(x, vista))

    st.sidebar.markdown(
        f"""
        <div class="sidebar-counter">
            Mostrando <strong>{len(filtered_df):,}</strong> de <strong>{len(diag_df):,}</strong> productos por tienda
            <br><span>({len(filtered_df) / len(diag_df) * 100:.1f}% del portafolio de alimentos CA)</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    aviso_vacio = None
    if filtered_df.empty:
        aviso_vacio = "Ningún producto coincide con los filtros actuales. " + motivo_sin_resultados(mascaras)

    # -----------------------------------------------------------------------
    # Pestañas según la vista activa
    # -----------------------------------------------------------------------
    pestanas = VISTAS[vista]["pestanas"]
    slots = dict(zip([k for k, _ in pestanas], st.tabs([n for _, n in pestanas])))
    tab1, tab2, tab3, tab4 = (slots.get(k) for k in ("resumen", "producto", "simulador", "auditoria"))

    # =======================================================================
    # TAB 1 — 1. RESUMEN EJECUTIVO (100% GERENCIAL)
    # =======================================================================
    for _ in _slot(tab1, aviso_vacio):
        n_filt = len(filtered_df)
        total_rev = float(filtered_df["revenue_at_risk_usd"].sum())
        total_units = float(filtered_df["units_at_risk_28d"].sum())

        high_df = filtered_df.loc[filtered_df["risk_level"] == "Riesgo Alto"]
        n_high = len(high_df)
        pct_high = n_high / n_filt * 100.0
        rev_high = float(high_df["revenue_at_risk_usd"].sum())

        por_grupo = filtered_df.groupby("cluster_name")["revenue_at_risk_usd"].sum()
        if total_rev > 0:
            grupo_top = str(por_grupo.idxmax())
            grupo_valor = f"{por_grupo.max() / total_rev * 100.0:.1f}%"
            grupo_series = int((filtered_df["cluster_name"] == grupo_top).sum())
            grupo_texto = f"del riesgo visible en {grupo_series:,} productos por tienda del grupo «{grupo_top}»"
        else:
            grupo_valor, grupo_texto = "—", "No hay ingreso en riesgo en la selección"

        snap_df = filtered_df.loc[filtered_df["snap_priority"]]
        n_snap = len(snap_df)
        rev_snap = float(snap_df["revenue_at_risk_usd"].sum())
        snap_rev_share = (rev_snap / total_rev * 100.0) if total_rev > 0 else 0.0

        # Fila de 4 tarjetas KPI Bento HTML (cero st.metric, cero truncado)
        st.markdown(
            f"""
            <div class="bento-grid-4">
                <div class="kpi-card">
                    <div class="kpi-label">Ingreso en riesgo (frente a 90 días)</div>
                    <div class="kpi-value kpi-accent-red">${total_rev:,.0f}</div>
                    <div class="kpi-sub">{total_units:,.0f} unidades menos en los próximos 28 días</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Productos por tienda en alerta crítica</div>
                    <div class="kpi-value">{n_high:,}</div>
                    <div class="kpi-sub">{pct_high:.1f}% del catálogo visible · ${rev_high:,.0f} en riesgo</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Grupo con más riesgo</div>
                    <div class="kpi-value kpi-accent-blue">{grupo_valor}</div>
                    <div class="kpi-sub">{grupo_texto}</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Impacto de días SNAP</div>
                    <div class="kpi-value kpi-accent-amber">{snap_rev_share:.1f}%</div>
                    <div class="kpi-sub">${rev_snap:,.0f} en riesgo en {n_snap:,} productos por tienda</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        medio_df = filtered_df.loc[filtered_df["risk_level"] == "Riesgo Medio"]
        n_sin_ventas = int((filtered_df["aviso"] == AVISO_SIN_VENTAS).sum())
        n_sin_monto = int((filtered_df["aviso"] == AVISO_SIN_MONTO).sum())
        vs28 = float(filtered_df["riesgo_vs_28d_usd"].sum())
        ya_caido = float(filtered_df.loc[filtered_df["caida_previa"], "revenue_at_risk_usd"].sum())
        st.markdown(
            f"""
            <div class="bento-grid-4">
                <div class="kpi-card">
                    <div class="kpi-label">Productos por tienda en riesgo medio</div>
                    <div class="kpi-value">{len(medio_df):,}</div>
                    <div class="kpi-sub">{len(medio_df) / n_filt * 100:.1f}% de lo visible · ${medio_df["revenue_at_risk_usd"].sum():,.0f} en riesgo</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Sensibles a SNAP ({UMBRAL_SNAP_PCT}% o más)</div>
                    <div class="kpi-value">{n_snap / n_filt * 100:.1f}%</div>
                    <div class="kpi-sub">{n_snap:,} productos por tienda</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Casi sin ventas, en riesgo bajo</div>
                    <div class="kpi-value kpi-accent-amber">{n_sin_ventas:,}</div>
                    <div class="kpi-sub">Sin venta {INTERMITENCIA_CRITICA:.0f}% de los días o más: revisar surtido</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Alertas sin monto</div>
                    <div class="kpi-value">{n_sin_monto:,}</div>
                    <div class="kpi-sub">Riesgo alto o medio por rotación, con $0 en riesgo</div>
                </div>
            </div>
            <div class="footnote-box" style="margin:0 0 1.1rem 0;">
                <strong>Cómo leer el ingreso en riesgo:</strong> compara el pronóstico con los últimos 90 días.
                De ${total_rev:,.0f}, <strong>${ya_caido:,.0f}</strong> corresponde a caídas ya ocurridas (el pronóstico no baja
                frente a los últimos 28 días). Medida contra esos 28 días, la caída sería de <strong>${vs28:,.0f}</strong>.
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Bloque: 3 Decisiones Inmediatas para Marketing
        md_sub = filtered_df.loc[filtered_df["primary_strategy"] == MARKDOWN]
        cs_sub = filtered_df.loc[filtered_df["primary_strategy"] == CROSS]

        md_count = len(md_sub)
        md_rev_risk = float(md_sub["revenue_at_risk_usd"].sum())
        # Escenario supuesto: 25% de descuento y respuesta 0.6
        esc25 = escenario_descuento(md_sub, DESCUENTO_BASE / 100.0, ELASTICIDADES["Esperado"])

        cs_count = len(cs_sub)
        cs_rev_risk = float(cs_sub["revenue_at_risk_usd"].sum())
        cs_sin = int((~cs_sub["has_price_promo_history"]).sum())
        cs_baja = cs_count - cs_sin

        sin_productos = "No hay productos de este grupo con los filtros actuales."
        texto_rebaja = (
            f"Con {DESCUENTO_BASE}% de descuento y una respuesta supuesta, el ingreso de 28 días pasaría de "
            f'<strong>${esc25["base"]:,.0f}</strong> a <strong>${esc25["con_rebaja"]:,.0f}</strong> '
            f'({usd_signo(esc25["neto"])}). No incluye costos ni merma evitada.'
        ) if md_count else sin_productos
        texto_combo = (
            f"<strong>{cs_sin:,}</strong> no tienen historial suficiente de rebajas y "
            f"<strong>{cs_baja:,}</strong> mostraron respuesta baja o negativa. "
            "El efecto del combo no está probado con estos datos."
        ) if cs_count else sin_productos
        texto_snap = (
            "<strong>Días 1–10 (pagos SNAP):</strong> reforzar exhibición, multipacks y stock.<br>"
            "<strong>Días 20–31 (fuera de SNAP):</strong> plan de cupones de fin de mes."
        ) if n_snap else sin_productos

        st.markdown('<div class="section-heading">3 Decisiones para Marketing</div>', unsafe_allow_html=True)
        st.markdown(
            tr(f"""
            <div class="bento-grid-3">
                <div class="decision-card decision-top-blue">
                    <div class="decision-kicker" style="color:{APPLE_BLUE};">Decisión 1 · Rebajas a prueba</div>
                    <div class="decision-title">Probar la rebaja antes de extenderla: vende más, pero ingresa menos</div>
                    <div class="decision-metric">{md_count:,} productos por tienda · ${md_rev_risk:,.0f} en riesgo</div>
                    <div class="decision-body">
                        {texto_rebaja}
                    </div>
                </div>
                <div class="decision-card decision-top-amber">
                    <div class="decision-kicker" style="color:{APPLE_AMBER};">Decisión 2 · Combos sin rebajar precio</div>
                    <div class="decision-title">Probar combos con un producto de alta rotación</div>
                    <div class="decision-metric">{cs_count:,} productos por tienda · ${cs_rev_risk:,.0f} en riesgo</div>
                    <div class="decision-body">
                        {texto_combo}
                    </div>
                </div>
                <div class="decision-card decision-top-green">
                    <div class="decision-kicker" style="color:{APPLE_GREEN};">Decisión 3 · Calendario SNAP</div>
                    <div class="decision-title">Sincronizar stock y cupones con el ciclo mensual</div>
                    <div class="decision-metric">{n_snap:,} productos por tienda · ${rev_snap:,.0f} en riesgo</div>
                    <div class="decision-body">
                        {texto_snap}
                    </div>
                </div>
            </div>
            """, vista),
            unsafe_allow_html=True,
        )

        # 2 Gráficos limpios lado a lado dentro de tarjetas Bento
        col_l, col_r = st.columns(2, gap="medium")

        with col_l:
            with st.container(border=True):
                store_tot = (
                    filtered_df.groupby("store_id", as_index=False)["revenue_at_risk_usd"]
                    .sum()
                    .sort_values("revenue_at_risk_usd", ascending=False)
                )
                top_st = str(store_tot.iloc[0]["store_id"])
                top_st_val = float(store_tot.iloc[0]["revenue_at_risk_usd"])
                top_st_pct = (top_st_val / total_rev * 100.0) if total_rev > 0 else 0.0

                st.markdown('<div class="chart-question">¿En qué tienda actuar primero?</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="chart-takeaway"><strong>{top_st}</strong> concentra el {top_st_pct:.1f}% del ingreso en riesgo (${top_st_val:,.0f}), liderando la prioridad de campaña.</div>',
                    unsafe_allow_html=True,
                )

                store_risk = (
                    filtered_df.groupby(["store_id", "risk_level"], as_index=False)["revenue_at_risk_usd"]
                    .sum()
                )
                fig_store = px.bar(
                    store_risk,
                    x="store_id",
                    y="revenue_at_risk_usd",
                    color="risk_level",
                    category_orders={"store_id": STORES, "risk_level": RISK_ORDER},
                    color_discrete_map=RISK_COLORS,
                    barmode="stack",
                    labels={
                        "store_id": "",
                        "revenue_at_risk_usd": "Ingreso en riesgo (USD)",
                        "risk_level": "",
                    },
                )
                fig_store.update_traces(
                    marker_line_width=0,
                    hovertemplate="<b>Tienda %{x}</b> · %{fullData.name}<br>En riesgo: $%{y:,.0f} USD<extra></extra>",
                )
                # Totales limpios encima de cada columna
                st_totals_map = dict(zip(store_tot["store_id"], store_tot["revenue_at_risk_usd"]))
                max_st = max(st_totals_map.values()) if st_totals_map else 1.0
                for st_name in STORES:
                    if st_name in st_totals_map:
                        val_s = st_totals_map[st_name]
                        fig_store.add_annotation(
                            x=st_name,
                            y=val_s,
                            text=f"<b>${val_s:,.0f}</b>",
                            showarrow=False,
                            yshift=10,
                            font=dict(size=11.5, color=APPLE_INK),
                        )

                apply_apple_plotly_theme(
                    fig_store,
                    height=370,
                    margin=dict(t=24, b=72, l=58, r=16),
                    legend_bottom=True,
                    legend_y=-0.16,
                )
                fig_store.update_yaxes(tickprefix="$", range=[0, max_st * 1.18])
                st.plotly_chart(fig_store, width="stretch", theme=None)

        with col_r:
            with st.container(border=True):
                grafico_riesgo_evidencia(filtered_df, vista)

        extra_l, extra_r = st.columns(2, gap="medium")
        with extra_l:
            with st.container(border=True):
                grafico_tienda_departamento(filtered_df)
        with extra_r:
            with st.container(border=True):
                grafico_series_por_riesgo(filtered_df, vista)

        with st.container(border=True):
            grafico_caidas_subidas(alcance_df)

        st.markdown(
            """
            <div class="footnote-box">
                <strong>Transparencia de datos (Walmart M5):</strong> Todas las cifras se calculan exclusivamente sobre ventas diarias reales,
                precios de góndola y calendario SNAP de las 4 tiendas de California. Al no existir datos públicos de stock físico ni costos
                de compra, la exposición comercial se expresa rigurosamente como <strong>Ingreso en Riesgo (USD)</strong> proyectado a 28 días.
            </div>
            """,
            unsafe_allow_html=True,
        )

    # =======================================================================
    # TAB 2 — 2. DECISIÓN POR PRODUCTO (RADIOGRAFÍA ACCIONABLE)
    # =======================================================================
    for _ in _slot(tab2, aviso_vacio):
        hist90_df = load_history_90d()
        val_w4_df, forecast_df = load_predictions()

        sorted_for_select = filtered_df.sort_values("revenue_at_risk_usd", ascending=False)
        sku_ids_ordered = sorted_for_select["id"].tolist()
        sku_labels = {
            r.id: f"{r.display_name}  |  {r.risk_level}  |  ${r.revenue_at_risk_usd:,.2f} en riesgo"
            for r in sorted_for_select.itertuples(index=False)
        }

        # Conserva la serie elegida; si los filtros la excluyen, avisa.
        recordada = st.session_state.get("serie_memoria")
        if recordada in sku_labels:
            st.session_state["serie_sel"] = recordada
        else:
            if recordada is not None:
                st.info(
                    f"La serie que veías ({clean_sku_code(recordada)}) quedó fuera de los filtros. "
                    "Ahora se muestra la de mayor ingreso en riesgo."
                )
            st.session_state["serie_sel"] = sku_ids_ordered[0]

        sel_c1, sel_c2 = st.columns([3.3, 1.0])
        with sel_c1:
            selected_id = st.selectbox(
                "Elegir producto y tienda (de mayor a menor ingreso en riesgo):",
                options=sku_ids_ordered,
                format_func=lambda x: sku_labels[x],
                key="serie_sel",
                on_change=lambda: st.session_state.update(serie_memoria=st.session_state["serie_sel"]),
            )
        st.session_state["serie_memoria"] = selected_id
        with sel_c2:
            st.write("")
            show_baselines = vista == "analista" and st.checkbox("Ver referencias", value=False, help="Suavizado exponencial (SES) y media de 28 días (MA28)")

        sku_row = filtered_df.loc[filtered_df["id"] == selected_id].iloc[0]
        h_sub = hist90_df.loc[hist90_df["id"] == selected_id]
        w4_sub = val_w4_df.loc[val_w4_df["id"] == selected_id]
        f_sub = forecast_df.loc[forecast_df["id"] == selected_id]

        # Tarjeta Semáforo de Decisión Comercial (inmediatamente visible arriba del gráfico)
        sem_cls = {
            "Riesgo Alto": "sem-high",
            "Riesgo Medio": "sem-med",
            "Riesgo Bajo": "sem-low",
        }.get(sku_row["risk_level"], "sem-low")

        strat_raw = str(sku_row["primary_strategy"])
        if "Markdown" in strat_raw:
            decision_headline = (
                f"Estrategia recomendada: Aplicar Markdown {sku_row['discount_range']} "
                f"+ revisar pedido post-oferta ({AJUSTE_REPOSICION}, supuesto)"
            )
            decision_sub = (
                "Este artículo responde positivamente a rebajas. Activar rotación FEFO en góndola "
                "y ajustar a la baja la orden de compra posterior para evitar sobrestock por acaparamiento."
            )
        elif "Cross-Selling" in strat_raw:
            anchor = sku_row["suggested_anchor_item"]
            decision_headline = (
                f"Estrategia recomendada: Cross-Selling sin descuento — "
                f"Empaquetar junto al producto ancla {anchor}"
            )
            motivo = (
                "Su respuesta observada a rebajas fue baja o negativa."
                if bool(sku_row["has_price_promo_history"])
                else "No hay historial suficiente para saber si responde a rebajas."
            )
            decision_sub = (
                f"{motivo} Probar combo o cabecera junto a {anchor}, líder de rotación en "
                f"{sku_row['store_id']} ({sku_row['dept_id']})."
            )
        elif "SNAP" in strat_raw:
            decision_headline = (
                "Estrategia recomendada: Sincronización SNAP sin descuento — "
                "Reforzar stock y multipacks del día 1 al 10"
            )
            decision_sub = (
                "Demanda saludable con pico fuerte en fechas de pago SNAP. Conservar precio habitual y asegurar disponibilidad."
            )
        else:
            decision_headline = (
                "Estrategia recomendada: Mantener precio habitual (EDLP) y usar como producto ancla"
            )
            decision_sub = (
                "Producto estable sin urgencia promocional. Ideal para traccionar combos junto a artículos en desaceleración."
            )

        if sku_row["aviso"] == AVISO_SIN_VENTAS:
            decision_headline = "Revisar surtido y disponibilidad: casi no registra ventas"
            decision_sub = (
                f"No vendió en el {sku_row['intermittency_pct']:.1f}% de los días. La regla documentada lo clasifica en "
                "riesgo bajo, pero no debe tratarse como estable ni usarse como ancla. Verificar stock antes de decidir."
            )

        pills_html = risk_pill_html(sku_row["risk_level"])
        if sku_row["aviso"]:
            pills_html += f'<span class="pill pill-med">{sku_row["aviso"]}</span>'
        if bool(sku_row["caida_previa"]):
            pills_html += '<span class="pill pill-info">La caída ya ocurrió en los últimos 28 días</span>'
        if sku_row["snap_priority"]:
            pills_html += f'<span class="pill pill-snap">Prioridad SNAP (+{UMBRAL_SNAP_PCT}% o más)</span>'
        if sku_row["stockpiling_alert"]:
            pills_html += f'<span class="pill pill-info">Revisar pedido post-oferta: {AJUSTE_REPOSICION}</span>'
        pills_html += f'<span class="pill pill-info">{sku_row["cluster_name"]}</span>'

        st.markdown(
            f"""
            <div class="semaphore-card {sem_cls}">
                <div>{pills_html}</div>
                <div class="sem-headline">{tr(decision_headline, vista)}</div>
                <p class="sem-detail">{tr(decision_sub, vista)} <strong>Calendario:</strong> {tr(sku_row['snap_tactical_plan'], vista)}.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Gráfico temporal dentro de tarjeta Bento blanca
        with st.container(border=True):
            st.markdown(
                f'<div class="chart-question">Evolución de ventas y pronóstico a 28 días — {sku_row["display_name"]}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div class="chart-takeaway">Línea negra: ventas reales recientes · Línea roja: demanda proyectada próximos 28 días · Franjas amarillas: días de pago SNAP.</div>',
                unsafe_allow_html=True,
            )
            fig_ts = build_forecast_figure(selected_id, h_sub, w4_sub, f_sub, show_baselines=show_baselines)
            st.plotly_chart(fig_ts, width="stretch", theme=None)

        # 6 Tarjetas HTML Bento debajo con cifras completas (NUNCA truncadas)
        pr_val, pr_sub, pr_cls = format_price_response_human(
            bool(sku_row["has_price_promo_history"]),
            sku_row["price_sensitivity"],
        )
        snap_pct = float(sku_row["snap_sensitivity"]) * 100.0
        snap_cls = "kpi-accent-amber" if sku_row["snap_priority"] else ""
        snap_sub = "Prioridad SNAP activa" if sku_row["snap_priority"] else "Impacto moderado o bajo"
        decline_val = float(sku_row["projected_decline_pct"])
        decline_txt = f"-{decline_val:.1f}% vs ritmo reciente" if decline_val > 0 else "Sin caída proyectada"

        st.markdown(
            f"""
            <div class="bento-grid-6">
                <div class="kpi-card">
                    <div class="kpi-label">Venta reciente (90d)</div>
                    <div class="kpi-value-sm">{sku_row['sales_velocity_90d']:.2f} u/día</div>
                    <div class="kpi-sub">Últimos 28d: {sku_row['sales_velocity_28d']:.2f} u/día</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Pronóstico (28 días)</div>
                    <div class="kpi-value-sm kpi-accent-blue">{sku_row['pred_velocity_28d']:.2f} u/día</div>
                    <div class="kpi-sub">{decline_txt}</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Ingreso en riesgo (vs. 90d)</div>
                    <div class="kpi-value-sm kpi-accent-red">${sku_row['revenue_at_risk_usd']:,.2f}</div>
                    <div class="kpi-sub">Vs. 28d: ${sku_row['riesgo_vs_28d_usd']:,.2f} · Precio ${sku_row['current_price']:.2f}</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Días sin ventas (3 años)</div>
                    <div class="kpi-value-sm">{sku_row['intermittency_pct']:.1f}%</div>
                    <div class="kpi-sub">Frecuencia de días en cero</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Respuesta a rebajas</div>
                    <div class="kpi-value-sm {pr_cls}">{pr_val}</div>
                    <div class="kpi-sub">{pr_sub}</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Impulso en días SNAP</div>
                    <div class="kpi-value-sm {snap_cls}">{snap_pct:+.1f}%</div>
                    <div class="kpi-sub">{snap_sub}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # =======================================================================
    # TAB 3 — 3. SIMULADOR DE CAMPAÑAS (SUBIDA A POSICIÓN 3)
    # =======================================================================
    for _ in _slot(tab3, aviso_vacio):
        st.markdown('<div class="section-heading">Simulador de Descuentos</div>', unsafe_allow_html=True)
        st.caption(
            "Escenarios supuestos, no medidos en estos datos. Calcula ingreso, no ganancia: no hay costos ni merma. "
            "Solo incluye productos por tienda en riesgo que respondieron a rebajas en el pasado."
        )

        markdown_df = filtered_df.loc[filtered_df["primary_strategy"] == MARKDOWN].copy()

        if markdown_df.empty:
            if MARKDOWN not in sel_strategies:
                causa = f"Agrega «{estrategia_corta(MARKDOWN)}» en el filtro de estrategia."
            elif not {"Riesgo Alto", "Riesgo Medio"} & set(sel_risks):
                causa = "Las rebajas solo aplican a riesgo alto o medio: agrega uno en «Nivel de prioridad»."
            else:
                causa = "Ningún producto de la selección respondió a rebajas en el pasado."
            st.info(f"No hay productos para simular. {causa}")
        else:
            with st.container(border=True):
                sc1, sc2 = st.columns([1.25, 1.35])
                with sc1:
                    disc_pct = st.slider(
                        "Nivel de descuento a simular:",
                        min_value=DESCUENTO_MIN,
                        max_value=DESCUENTO_MAX,
                        value=DESCUENTO_BASE,
                        step=1,
                        format="%d%%",
                    )
                eps_map = {**ELASTICIDADES, ESCENARIO_HISTORIAL: None}
                with sc2:
                    elast_label = st.radio(
                        "Respuesta supuesta del consumidor:",
                        options=list(eps_map),
                        index=1,
                        horizontal=True,
                        format_func=lambda k: f"{k} (ε={eps_map[k]})" if vista == "analista" and eps_map[k] else k,
                    )
                if eps_map[elast_label] is None:
                    st.caption(
                        "Usa la venta observada con rebajas de cada producto, limitada al escenario optimista. Mezcla "
                        "cualquier rebaja mayor de 5% y no prueba causa."
                    )

            eps = eps_map[elast_label]
            d = disc_pct / 100.0
            esc = escenario_descuento(markdown_df, d, eps)

            st.markdown(
                f"""
                <div class="bento-grid-5">
                    <div class="kpi-card">
                        <div class="kpi-label">Ingreso sin rebaja (28 días)</div>
                        <div class="kpi-value-sm">${esc["base"]:,.0f}</div>
                        <div class="kpi-sub">{len(markdown_df):,} productos por tienda</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Ingreso con rebaja</div>
                        <div class="kpi-value-sm kpi-accent-blue">${esc["con_rebaja"]:,.0f}</div>
                        <div class="kpi-sub">Descuento {disc_pct}%</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Diferencia neta</div>
                        <div class="kpi-value-sm {'kpi-accent-red' if esc['neto'] < 0 else 'kpi-accent-green'}">{usd_signo(esc["neto"])}</div>
                        <div class="kpi-sub">{esc["neto"] / esc["base"] * 100 if esc["base"] else 0:+.1f}% sobre el ingreso base</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Más unidades supuestas</div>
                        <div class="kpi-value-sm">+{esc["lift"] * 100:.1f}%</div>
                        <div class="kpi-sub">+{esc["unidades_extra"]:,.0f} sobre {esc["unidades_base"]:,.0f}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Necesario para no perder ingreso</div>
                        <div class="kpi-value-sm kpi-accent-amber">+{esc["lift_equilibrio"] * 100:.1f}%</div>
                        <div class="kpi-sub">unidades adicionales</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            sim_l, sim_r = st.columns(2, gap="medium")
            with sim_l:
                with st.container(border=True):
                    st.markdown('<div class="chart-question">¿Qué pasa con el ingreso al rebajar?</div>', unsafe_allow_html=True)
                    st.markdown(
                        f'<div class="chart-takeaway">Lo que se vende de más ({usd_signo(esc["extra"])}) '
                        f'{"no compensa" if esc["neto"] < 0 else "compensa"} la rebaja sobre lo que ya se vendía ({usd_signo(esc["rebaja"])}).</div>',
                        unsafe_allow_html=True,
                    )
                    fig_casc = go.Figure(
                        go.Waterfall(
                            x=["Sin rebaja", "Rebaja", "Unidades extra", "Con rebaja"],
                            y=[esc["base"], esc["rebaja"], esc["extra"], esc["con_rebaja"]],
                            measure=["absolute", "relative", "relative", "total"],
                            text=[f"${esc['base']:,.0f}", usd_signo(esc["rebaja"]), usd_signo(esc["extra"]), f"${esc['con_rebaja']:,.0f}"],
                            textposition="outside",
                            decreasing=dict(marker=dict(color=APPLE_RED)),
                            increasing=dict(marker=dict(color=APPLE_GREEN_BRIGHT)),
                            totals=dict(marker=dict(color=APPLE_BLUE)),
                            cliponaxis=False,
                        )
                    )
                    apply_apple_plotly_theme(fig_casc, height=360, margin=dict(t=30, b=40, l=70, r=24), show_legend=False)
                    fig_casc.update_yaxes(tickprefix="$", range=[0, esc["base"] * 1.18])
                    st.plotly_chart(fig_casc, width="stretch", theme=None)

            with sim_r:
                with st.container(border=True):
                    st.markdown('<div class="chart-question">¿Cuánto cambia el ingreso según el descuento?</div>', unsafe_allow_html=True)
                    st.markdown(
                        '<div class="chart-takeaway">Diferencia frente a no rebajar. Bajo la línea cero se ingresa menos.</div>',
                        unsafe_allow_html=True,
                    )
                    sim_curve_df = pd.DataFrame(
                        [
                            {
                                "Descuento (%)": dv,
                                "Escenario": label_e,
                                "Diferencia neta (USD)": escenario_descuento(markdown_df, dv / 100.0, e_val)["neto"],
                            }
                            for label_e, e_val in eps_map.items()
                            for dv in range(DESCUENTO_MIN, DESCUENTO_MAX + 1)
                        ]
                    )
                    fig_sim = px.line(
                        sim_curve_df,
                        x="Descuento (%)",
                        y="Diferencia neta (USD)",
                        color="Escenario",
                        markers=True,
                        color_discrete_map={"Conservador": "#8E8E93", "Esperado": APPLE_BLUE, "Optimista": APPLE_GREEN_BRIGHT, ESCENARIO_HISTORIAL: APPLE_ORANGE},
                    )
                    fig_sim.add_hline(y=0, line=dict(color=APPLE_INK, width=1.2))
                    fig_sim.add_vline(x=disc_pct, line=dict(color=APPLE_RED, width=1.4, dash="dash"))
                    apply_apple_plotly_theme(fig_sim, height=360, margin=dict(t=30, b=78, l=70, r=24), legend_y=-0.22)
                    fig_sim.update_yaxes(tickprefix="$", rangemode="tozero")
                    st.plotly_chart(fig_sim, width="stretch", theme=None)

            with st.container(border=True):
                req = esc["lift_equilibrio"] * 100.0
                puntos = markdown_df.loc[markdown_df["revenue_at_risk_usd"] > 0].copy()
                puntos["resp_pct"] = puntos["price_sensitivity"] * 100.0
                st.markdown('<div class="chart-question">¿Qué respuesta pasada tuvo cada producto frente al equilibrio?</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="chart-takeaway">La línea marca el +{req:.1f}% necesario con {disc_pct}% de descuento. '
                    "<strong>Estar encima no garantiza ganancia:</strong> la respuesta pasada mezcla cualquier rebaja "
                    "mayor de 5% en 3 años y puede deberse a otras causas. Solo se muestran productos por tienda con ingreso en riesgo.</div>",
                    unsafe_allow_html=True,
                )
                if puntos.empty:
                    st.info("No hay productos aptos con ingreso en riesgo.")
                else:
                    fig_eq = px.scatter(
                        puntos,
                        x="revenue_at_risk_usd",
                        y="resp_pct",
                        hover_name="display_name",
                        hover_data={"revenue_at_risk_usd": ":$.2f", "resp_pct": ":.1f", "promo_days_count": True},
                        labels={
                            "revenue_at_risk_usd": "Ingreso en riesgo (USD, escala logarítmica)",
                            "resp_pct": "Venta con rebaja frente a precio normal (%, escala logarítmica)",
                            "promo_days_count": "Días con rebaja",
                        },
                        log_x=True,
                        log_y=True,
                        opacity=0.7,
                    )
                    fig_eq.update_traces(marker=dict(color=APPLE_BLUE, size=8))
                    fig_eq.add_hline(y=req, line=dict(color=APPLE_RED, width=1.6, dash="dash"))
                    apply_apple_plotly_theme(fig_eq, height=400, margin=dict(t=24, b=60, l=70, r=24), show_legend=False)
                    st.plotly_chart(fig_eq, width="stretch", theme=None)

        st.markdown('<div class="section-heading" style="margin-top:1.1rem;">Plan de Acción Comercial (Lista Priorizada)</div>', unsafe_allow_html=True)

        plan_table_raw = filtered_df.sort_values("revenue_at_risk_usd", ascending=False).copy()
        ver_todo = st.toggle("Ver todas las columnas", value=False)
        plan_display = plan_table_raw[
            [
                "display_name",
                "risk_level",
                "revenue_at_risk_usd",
                "projected_decline_pct",
                "strategy_short",
                "suggested_anchor_item",
                "current_price",
                "store_id",
                "dept_id",
                "cluster_name",
                "sales_velocity_90d",
                "pred_velocity_28d",
                "price_sensitivity",
                "snap_sensitivity",
                "snap_priority",
                "aviso",
            ]
        ].copy()
        if not ver_todo:
            plan_display = plan_display[
                ["display_name", "risk_level", "revenue_at_risk_usd", "strategy_short", "suggested_anchor_item", "aviso"]
            ]

        export_cols = [
            "id",
            "store_id",
            "dept_id",
            "risk_level",
            "cluster_name",
            "current_price",
            "sales_velocity_90d",
            "pred_velocity_28d",
            "projected_decline_pct",
            "intermittency_pct",
            "revenue_at_risk_usd",
            "price_sensitivity",
            "snap_sensitivity",
            "snap_priority",
            "primary_strategy",
            "discount_range",
            "suggested_anchor_item",
            "snap_tactical_plan",
            "tactical_action",
            "aviso",
            "riesgo_vs_28d_usd",
        ]
        csv_bytes = plan_table_raw[export_cols].to_csv(index=False).encode("utf-8-sig")

        dl_l, dl_r = st.columns([2.6, 1.0])
        with dl_l:
            st.caption(f"Mostrando **{len(plan_display):,}** productos por tienda, ordenados de mayor a menor ingreso en riesgo.")
        with dl_r:
            st.download_button(
                label="Descargar plan (.CSV para Excel)",
                data=csv_bytes,
                file_name="plan_promociones_walmart_ca.csv",
                mime="text/csv",
                type="primary",
                width="stretch",
            )

        reposicion = plan_table_raw.loc[
            plan_table_raw["stockpiling_alert"],
            ["id", "store_id", "dept_id", "risk_level", "discount_range", "pred_total_28d_units"],
        ].assign(ajuste_sugerido_post_oferta=AJUSTE_REPOSICION)
        if not reposicion.empty:
            st.download_button(
                label=f"Descargar lista de revisión de reposición ({len(reposicion):,})",
                data=reposicion.to_csv(index=False).encode("utf-8-sig"),
                file_name="revision_reposicion_post_oferta.csv",
                mime="text/csv",
            )
            st.caption(
                f"Solo para revisión manual tras una rebaja: el ajuste {AJUSTE_REPOSICION} es un supuesto de la "
                "literatura y el tablero no envía alertas a ningún sistema."
            )

        st.dataframe(
            plan_display,
            width="stretch",
            hide_index=True,
            height=450,
            column_config={
                "display_name": "Producto y Tienda",
                "risk_level": "Prioridad",
                "revenue_at_risk_usd": st.column_config.NumberColumn("Ingreso en riesgo (USD)", format="$%.2f"),
                "projected_decline_pct": st.column_config.NumberColumn("Caída (%)", format="%.1f%%"),
                "strategy_short": "Estrategia Recomendada",
                "suggested_anchor_item": "Producto Ancla",
                "current_price": st.column_config.NumberColumn("Precio", format="$%.2f"),
                "store_id": "Tienda",
                "dept_id": "Departamento",
                "cluster_name": "Grupo Comercial",
                "sales_velocity_90d": st.column_config.NumberColumn("Venta 90d", format="%.2f"),
                "pred_velocity_28d": st.column_config.NumberColumn("Pronóstico 28d", format="%.2f"),
                "price_sensitivity": st.column_config.NumberColumn("Sensibilidad Precio", format="%+.2f"),
                "snap_sensitivity": st.column_config.NumberColumn("Sensibilidad SNAP", format="%+.2f"),
                "snap_priority": st.column_config.CheckboxColumn("Prioridad SNAP"),
                "aviso": "Aviso",
            },
        )

    # =======================================================================
    # TAB 4 — 4. RESPALDO IA (AUDITORÍA TÉCNICA PARA DOCENTE)
    # =======================================================================
    for _ in _slot(tab4):
        st.markdown('<div class="section-heading">A. Validación Temporal por Origen Rodante (4 Ventanas × 28 Días)</div>', unsafe_allow_html=True)
        st.caption(
            f"Evaluación cronológica sobre las {len(diag_df):,} series. Auditoría anti-fuga por muestreo en el paso de preparación."
        )

        st.info(
            "Las métricas, la importancia de variables y la tabla de grupos son globales: los filtros no cambian "
            "esas cifras. Solo el mapa de grupos responde a los filtros."
        )

        val_summary = tables["val_summary"]
        val_by_window = tables["val_by_window"]
        val_breakdown = tables["val_breakdown"]
        fi_df = tables["feature_importance"]

        ventanas = tables["val_by_window"].drop_duplicates("window").sort_values("window")
        win_choice = st.selectbox(
            "Corte de validación:",
            options=["Promedio 4 Ventanas"]
            + [f"Ventana {r.window} ({r.start_date} a {r.end_date})" for r in ventanas.itertuples(index=False)],
        )

        if win_choice == "Promedio 4 Ventanas":
            display_val = val_summary.copy()
        else:
            w_num = int(win_choice.split()[1])
            display_val = val_by_window.loc[val_by_window["window"] == w_num, ["model", "mae", "rmse", "rmsse"]].copy()
            rf_w = display_val.loc[display_val["model"] == "Random Forest"].iloc[0]
            for met in ("mae", "rmse", "rmsse"):
                display_val[f"rf_improvement_vs_model_{met}_pct"] = (
                    (display_val[met] - float(rf_w[met])) / display_val[met] * 100.0
                )

        display_val["_ord"] = np.where(display_val["model"] == "Random Forest", 0, 1)
        display_val = display_val.sort_values(["_ord", "rmsse"]).drop(columns=["_ord"])

        st.dataframe(
            display_val,
            width="stretch",
            hide_index=True,
            column_config={
                "model": "Modelo",
                "mae": st.column_config.NumberColumn("MAE", format="%.4f"),
                "rmse": st.column_config.NumberColumn("RMSE", format="%.4f"),
                "rmsse": st.column_config.NumberColumn("RMSSE (M5)", format="%.4f"),
                "rf_improvement_vs_model_mae_pct": st.column_config.NumberColumn("Mejora RF MAE (%)", format="%+.2f%%"),
                "rf_improvement_vs_model_rmse_pct": st.column_config.NumberColumn("Mejora RF RMSE (%)", format="%+.2f%%"),
                "rf_improvement_vs_model_rmsse_pct": st.column_config.NumberColumn("Mejora RF RMSSE (%)", format="%+.2f%%"),
            },
        )

        with st.container(border=True):
            st.markdown('<div class="chart-question">¿Gana Random Forest en todas las ventanas?</div>', unsafe_allow_html=True)
            grafico_error_por_ventana(val_by_window)

        with st.container(border=True):
            st.markdown('<div class="chart-question">Cuando el modelo avisa una caída, ¿ocurre?</div>', unsafe_allow_html=True)
            grafico_senal_caida(load_history_90d(), load_predictions()[0])

        vc1, vc2 = st.columns(2, gap="medium")
        with vc1:
            with st.container(border=True):
                st.markdown(f'<div class="chart-question">Comparativa de Error por Modelo ({win_choice})</div>', unsafe_allow_html=True)
                melted_val = display_val.melt(
                    id_vars="model", value_vars=["mae", "rmse", "rmsse"], var_name="Métrica", value_name="Valor"
                )
                melted_val["Métrica"] = melted_val["Métrica"].str.upper()
                fig_val = px.bar(
                    melted_val,
                    x="Métrica",
                    y="Valor",
                    color="model",
                    barmode="group",
                    color_discrete_map={
                        "Random Forest": APPLE_BLUE,
                        "SES (NumPy)": APPLE_GREEN_BRIGHT,
                        "MA28": APPLE_ORANGE,
                        "Seasonal Naïve (lag_28)": "#8E8E93",
                    },
                    labels={"model": ""},
                )
                fig_val.update_traces(
                    texttemplate="%{y:.2f}",
                    textposition="outside",
                    textfont=dict(size=9, color=APPLE_INK),
                    cliponaxis=False,
                    marker_line_width=0,
                )
                apply_apple_plotly_theme(
                    fig_val,
                    height=405,
                    margin=dict(t=30, b=95, l=50, r=20),
                    legend_bottom=True,
                    legend_y=-0.22,
                )
                fig_val.update_yaxes(range=[0, float(melted_val["Valor"].max()) * 1.18])
                st.plotly_chart(fig_val, width="stretch", theme=None)

        with vc2:
            with st.container(border=True):
                st.markdown('<div class="chart-question">Desglose de RMSSE de Random Forest (Tienda, Depto y SNAP)</div>', unsafe_allow_html=True)
                bd_plot = val_breakdown.copy()
                bd_plot["Grupo"] = bd_plot["dimension"].map(
                    {"store_id": "Tienda", "dept_id": "Departamento", "snap_CA": "Condición SNAP"}
                )
                fig_bd = px.bar(
                    bd_plot,
                    x="segment",
                    y="rmsse",
                    color="Grupo",
                    color_discrete_map={
                        "Tienda": APPLE_BLUE,
                        "Departamento": APPLE_INK,
                        "Condición SNAP": APPLE_ORANGE,
                    },
                    text_auto=".3f",
                    labels={"segment": "Segmento", "rmsse": "RMSSE promedio (4 ventanas)", "Grupo": ""},
                )
                fig_bd.update_traces(textposition="outside", marker_line_width=0)
                rf_global_rmsse = float(val_summary.loc[val_summary["model"] == "Random Forest", "rmsse"].iloc[0])

                # Línea horizontal global + anotación limpia en esquina superior derecha fuera de barras
                fig_bd.add_shape(
                    type="line",
                    xref="paper",
                    yref="y",
                    x0=0.0,
                    x1=1.0,
                    y0=rf_global_rmsse,
                    y1=rf_global_rmsse,
                    line=dict(color=APPLE_RED, width=1.6, dash="dash"),
                )
                fig_bd.add_annotation(
                    x=0.99,
                    y=0.99,
                    xref="paper",
                    yref="y",
                    text=f"Promedio global: {rf_global_rmsse:.3f}",
                    showarrow=False,
                    xanchor="right",
                    yanchor="bottom",
                    font=dict(size=11, color=APPLE_RED),
                    bgcolor="#FFF2F2",
                    bordercolor="#FECACA",
                    borderwidth=1,
                    borderpad=3,
                )
                apply_apple_plotly_theme(
                    fig_bd,
                    height=405,
                    margin=dict(t=32, b=108, l=52, r=20),
                    legend_bottom=True,
                    legend_y=-0.30,
                )
                fig_bd.update_yaxes(range=[0, 1.08])
                st.plotly_chart(fig_bd, width="stretch", theme=None)

        # Importancia de las 16 variables (height holgado = 500 para cero recorte)
        with st.container(border=True):
            st.markdown('<div class="chart-question">Importancia de las 16 Variables Predictoras — Random Forest Final</div>', unsafe_allow_html=True)
            fi_sorted = fi_df.sort_values("importance_pct", ascending=True).copy()
            fi_sorted["Familia"] = fi_sorted["feature"].apply(
                lambda f: "Rezagos / Medias (>= t-28)"
                if f.startswith(("lag_", "rolling_"))
                else (
                    "Precios"
                    if "price" in f
                    else (
                        "Calendario / SNAP"
                        if f in ("snap_CA", "wday", "month", "year", "event_type_1_code")
                        else "Identificadores"
                    )
                )
            )
            fig_fi = px.bar(
                fi_sorted,
                x="importance_pct",
                y="feature",
                color="Familia",
                orientation="h",
                color_discrete_map={
                    "Rezagos / Medias (>= t-28)": APPLE_BLUE,
                    "Precios": APPLE_ORANGE,
                    "Calendario / SNAP": APPLE_GREEN_BRIGHT,
                    "Identificadores": "#8E8E93",
                },
                text=fi_sorted["importance_pct"].map(lambda v: f"{v:.2f}%"),
                labels={"importance_pct": "Importancia relativa (%)", "feature": "", "Familia": ""},
            )
            fig_fi.update_traces(textposition="outside", textfont=dict(color=APPLE_INK, size=11), marker_line_width=0)
            apply_apple_plotly_theme(
                fig_fi,
                height=500,
                margin=dict(t=24, b=88, l=135, r=68),
                legend_bottom=True,
                legend_y=-0.16,
            )
            fig_fi.update_xaxes(showgrid=True, gridcolor=APPLE_GRID, range=[0, float(fi_sorted["importance_pct"].max()) * 1.16])
            fig_fi.update_yaxes(showgrid=False)
            st.plotly_chart(fig_fi, width="stretch", theme=None)

        st.markdown('<div class="section-heading" style="margin-top:1.25rem;">B. Segmentación No Supervisada K-Means (K = 4)</div>', unsafe_allow_html=True)
        km_eval = tables["kmeans_eval"]
        km_prof = tables["kmeans_profiles"]
        selected_k = int(audits.get("diagnosis", {}).get("kmeans", {}).get("selected_k", 4))

        st.caption(
            "K se eligió por utilidad comercial. La silueta más alta no corresponde necesariamente al K elegido: "
            "compare la curva."
        )
        km_c1, km_c2 = st.columns([1.0, 1.35], gap="medium")
        with km_c1:
            with st.container(border=True):
                st.markdown('<div class="chart-question">Método del Codo (WCSS) y Coeficiente de Silueta</div>', unsafe_allow_html=True)
                fig_km = make_subplots(specs=[[{"secondary_y": True}]])
                fig_km.add_trace(
                    go.Scatter(
                        x=km_eval["k"].tolist(),
                        y=km_eval["wcss"].tolist(),
                        mode="lines+markers",
                        name="WCSS (Inercia)",
                        line=dict(color=APPLE_BLUE, width=2.4),
                        marker=dict(size=7.5),
                    ),
                    secondary_y=False,
                )
                fig_km.add_trace(
                    go.Scatter(
                        x=km_eval["k"].tolist(),
                        y=km_eval["silhouette_score"].tolist(),
                        mode="lines+markers",
                        name="Coeficiente de Silueta",
                        line=dict(color=APPLE_INK, width=2.4, dash="dash"),
                        marker=dict(size=7.5, symbol="square"),
                    ),
                    secondary_y=True,
                )
                fig_km.add_shape(
                    type="line",
                    xref="x",
                    yref="paper",
                    x0=selected_k,
                    x1=selected_k,
                    y0=0.0,
                    y1=1.0,
                    line=dict(color=APPLE_RED, width=1.5, dash="dot"),
                )
                fig_km.add_annotation(
                    x=selected_k,
                    y=1.06,
                    xref="x",
                    yref="paper",
                    text=f"K elegido = {selected_k}",
                    showarrow=False,
                    font=dict(size=11, color=APPLE_RED),
                    bgcolor="#FFF2F2",
                    bordercolor="#FECACA",
                    borderwidth=1,
                    borderpad=3,
                )
                apply_apple_plotly_theme(
                    fig_km,
                    height=440,
                    margin=dict(t=46, b=88, l=58, r=52),
                    legend_bottom=True,
                    legend_y=-0.22,
                )
                fig_km.update_layout(hovermode="x unified")
                fig_km.update_xaxes(title_text="Número de clústeres (K)", dtick=1)
                fig_km.update_yaxes(title_text="WCSS", secondary_y=False)
                fig_km.update_yaxes(title_text="Silueta", secondary_y=True, showgrid=False)
                st.plotly_chart(fig_km, width="stretch", theme=None)

        with km_c2:
            with st.container(border=True):
                st.markdown('<div class="chart-question">Mapa de Clústeres: Intermitencia vs Declive Proyectado</div>', unsafe_allow_html=True)
                if filtered_df.empty:
                    st.caption("Sin productos con los filtros actuales: el mapa aparece vacío.")
                scatter_df = filtered_df.copy()
                scatter_df["size_marker"] = np.clip(scatter_df["revenue_at_risk_usd"], 1.0, None)
                color_map_clusters = {
                    name: CLUSTER_PALETTE[i % len(CLUSTER_PALETTE)]
                    for i, name in enumerate(km_prof["cluster_name"].tolist())
                }
                fig_sc = px.scatter(
                    scatter_df,
                    x="intermittency_pct",
                    y="projected_decline_pct",
                    size="size_marker",
                    size_max=34,
                    color="cluster_name",
                    color_discrete_map=color_map_clusters,
                    hover_name="display_name",
                    hover_data={
                        "store_id": True,
                        "dept_id": True,
                        "risk_level": True,
                        "revenue_at_risk_usd": ":$.2f",
                        "sales_velocity_28d": ":.2f",
                        "strategy_short": True,
                        "size_marker": False,
                    },
                    labels={
                        "intermittency_pct": "Intermitencia (% días en cero)",
                        "projected_decline_pct": "Declive proyectado (%)",
                        "cluster_name": "",
                    },
                    opacity=0.72,
                )
                apply_apple_plotly_theme(
                    fig_sc,
                    height=440,
                    margin=dict(t=24, b=118, l=55, r=20),
                    legend_bottom=True,
                    legend_y=-0.28,
                )
                st.plotly_chart(fig_sc, width="stretch", theme=None)

        st.markdown("**Perfiles Empíricos de los 4 Clústeres (centroides reales en escala original):**")
        st.dataframe(
            km_prof,
            width="stretch",
            hide_index=True,
            column_config={
                "cluster_id": "ID",
                "cluster_name": "Nombre del Clúster",
                "sku_count": st.column_config.NumberColumn("SKUs", format="%d"),
                "portfolio_pct": st.column_config.NumberColumn("% Portafolio", format="%.2f%%"),
                "sales_velocity_28d_mean": st.column_config.NumberColumn("Vel. 28d (u/d)", format="%.2f"),
                "intermittency_pct_mean": st.column_config.NumberColumn("Intermit. (%)", format="%.1f%%"),
                "projected_decline_pct_mean": st.column_config.NumberColumn("Declive (%)", format="%.1f%%"),
                "revenue_at_risk_usd_mean": st.column_config.NumberColumn("Riesgo/SKU", format="$%.2f"),
                "revenue_at_risk_usd_total": st.column_config.NumberColumn("Riesgo Total", format="$%.2f"),
                "revenue_at_risk_share_pct": st.column_config.NumberColumn("% Riesgo Total", format="%.1f%%"),
                "price_sensitivity_mean": st.column_config.NumberColumn("Sensib. Precio", format="%+.2f"),
                "snap_sensitivity_mean": st.column_config.NumberColumn("Sensib. SNAP", format="%+.2f"),
                "pct_high_risk": st.column_config.NumberColumn("% Riesgo Alto", format="%.1f%%"),
                "pct_med_risk": st.column_config.NumberColumn("% Riesgo Medio", format="%.1f%%"),
                "pct_low_risk": st.column_config.NumberColumn("% Riesgo Bajo", format="%.1f%%"),
            },
        )


if __name__ == "__main__":
    main()

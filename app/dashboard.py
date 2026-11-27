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
    initial_sidebar_state="expanded",
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
STRATEGY_AXIS_LABELS = {
    "Cross-Selling y Visibilidad Omnicanal (Sin Descuento)": "Cross-Selling<br>(Sin descuento)",
    "Mantenimiento EDLP y Producto Ancla": "Precio Habitual<br>(Producto Ancla)",
    "Precios Dinámicos / Markdown (20%–35%)": "Descuentos<br>(20%–35%)",
    "Sincronización SNAP (Base EDLP)": "Calendario SNAP<br>(Base EDLP)",
}
STRATEGY_AXIS_COLORS = {
    "Cross-Selling<br>(Sin descuento)": APPLE_BLUE,
    "Descuentos<br>(20%–35%)": APPLE_RED,
    "Calendario SNAP<br>(Base EDLP)": APPLE_ORANGE,
    "Precio Habitual<br>(Producto Ancla)": APPLE_GREEN_BRIGHT,
}
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
    @media (max-width: 1180px) {{
        .bento-grid-6 {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
        .bento-grid-5 {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
        .bento-grid-4 {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 820px) {{
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
        return f"{pct:.1f}% (No rebajar)", "Inelástico · Proteger margen", "kpi-accent-red"
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
    """Lee el dataset ultra-ligero de 90 días (2016-02-23..2016-05-22); usa active_sales_3y.parquet como fallback local."""
    cols = ["id", "date", "units_sold", "sell_price", "snap_CA"]
    if DASHBOARD_SALES_90D_PATH.exists():
        df = pd.read_parquet(DASHBOARD_SALES_90D_PATH, columns=cols)
    elif ACTIVE_SALES_3Y_PATH.exists():
        df = pd.read_parquet(
            ACTIVE_SALES_3Y_PATH,
            columns=cols,
            filters=[("date", ">=", pd.Timestamp("2016-02-23"))],
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
        columns=["id", "date", "pred_rf", "pred_ses", "pred_ma28", "pred_snaive"],
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
            name="Validación IA reciente",
            line=dict(color=APPLE_BLUE, width=2.2, dash="dash"),
            hovertemplate="Validación IA: %{y:.2f} u.<extra></extra>",
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

    # Línea vertical de corte en ISO exacto "2016-05-22" (cero timestamps numéricos)
    cutoff_iso = "2016-05-22"
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
        text="Cierre histórico (22 May 2016) · Inicio pronóstico 28d",
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
        range=["2016-02-22", "2016-06-20"],
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
                Anticipa qué alimentos perderán ventas en los próximos 28 días, cuánto dinero está en riesgo y qué promoción aplicar sin destruir margen.
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
    st.sidebar.markdown("#### Filtrar catálogo")

    sel_stores = st.sidebar.multiselect("Tiendas", options=STORES, default=STORES)
    sel_depts = st.sidebar.multiselect("Departamentos", options=DEPARTMENTS, default=DEPARTMENTS)
    sel_risks = st.sidebar.multiselect("Nivel de prioridad", options=RISK_ORDER, default=RISK_ORDER)
    search_sku = st.sidebar.text_input("Buscar producto", value="", placeholder="Ej. FOODS_3_282 o CA_3")

    cluster_options = tables["kmeans_profiles"]["cluster_name"].tolist()
    strategy_options = sorted(diag_df["primary_strategy"].unique().tolist())

    with st.sidebar.expander("Filtros avanzados", expanded=False):
        sel_clusters = st.multiselect("Grupo comercial (Clúster)", options=cluster_options, default=cluster_options)
        sel_strategies = st.multiselect("Estrategia recomendada", options=strategy_options, default=strategy_options)
        only_snap_prio = st.toggle("Solo productos sensibles a pagos SNAP", value=False)

    mask = (
        diag_df["store_id"].isin(sel_stores)
        & diag_df["dept_id"].isin(sel_depts)
        & diag_df["risk_level"].isin(sel_risks)
        & diag_df["cluster_name"].isin(sel_clusters)
        & diag_df["primary_strategy"].isin(sel_strategies)
    )
    if only_snap_prio:
        mask &= diag_df["snap_priority"]
    if search_sku.strip():
        q = search_sku.strip().lower()
        mask &= (
            diag_df["id"].str.lower().str.contains(q, regex=False)
            | diag_df["item_id"].str.lower().str.contains(q, regex=False)
            | diag_df["display_name"].str.lower().str.contains(q, regex=False)
        )

    filtered_df = diag_df.loc[mask].copy()

    st.sidebar.markdown(
        f"""
        <div class="sidebar-counter">
            Mostrando <strong>{len(filtered_df):,}</strong> de <strong>{len(diag_df):,}</strong> productos
            <br><span>({len(filtered_df) / len(diag_df) * 100:.1f}% del portafolio de alimentos CA)</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if filtered_df.empty:
        st.info(
            "Ningún producto coincide con los filtros actuales. Ajusta las opciones en el panel izquierdo para volver a ver resultados."
        )
        st.stop()

    # -----------------------------------------------------------------------
    # 4 Pestañas ordenadas de Negocio -> Producto -> Simulador -> Auditoría IA
    # -----------------------------------------------------------------------
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "1. Resumen Ejecutivo",
            "2. Decisión por Producto",
            "3. Simulador de Campañas",
            "4. Respaldo IA (Auditoría Técnica)",
        ]
    )

    # =======================================================================
    # TAB 1 — 1. RESUMEN EJECUTIVO (100% GERENCIAL)
    # =======================================================================
    with tab1:
        n_filt = len(filtered_df)
        total_rev = float(filtered_df["revenue_at_risk_usd"].sum())
        total_units = float(filtered_df["units_at_risk_28d"].sum())

        high_df = filtered_df.loc[filtered_df["risk_level"] == "Riesgo Alto"]
        n_high = len(high_df)
        pct_high = n_high / n_filt * 100.0
        rev_high = float(high_df["revenue_at_risk_usd"].sum())

        c3_df = filtered_df.loc[filtered_df["cluster_id"] == 3]
        c3_count = len(c3_df)
        c3_rev = float(c3_df["revenue_at_risk_usd"].sum())
        c3_share = (c3_rev / total_rev * 100.0) if total_rev > 0 else 0.0

        snap_df = filtered_df.loc[filtered_df["snap_priority"]]
        n_snap = len(snap_df)
        rev_snap = float(snap_df["revenue_at_risk_usd"].sum())
        snap_rev_share = (rev_snap / total_rev * 100.0) if total_rev > 0 else 0.0

        # Fila de 4 tarjetas KPI Bento HTML (cero st.metric, cero truncado)
        st.markdown(
            f"""
            <div class="bento-grid-4">
                <div class="kpi-card">
                    <div class="kpi-label">Dinero en riesgo (próximos 28 días)</div>
                    <div class="kpi-value kpi-accent-red">${total_rev:,.0f}</div>
                    <div class="kpi-sub">{total_units:,.0f} unidades en desaceleración proyectada</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Productos en alerta crítica</div>
                    <div class="kpi-value">{n_high:,}</div>
                    <div class="kpi-sub">{pct_high:.1f}% del catálogo visible · ${rev_high:,.0f} en riesgo</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Foco Pareto (Grupo prioritario)</div>
                    <div class="kpi-value kpi-accent-blue">{c3_share:.1f}%</div>
                    <div class="kpi-sub">del riesgo concentrado en solo {c3_count:,} productos</div>
                </div>
                <div class="kpi-card">
                    <div class="kpi-label">Impacto de días SNAP</div>
                    <div class="kpi-value kpi-accent-amber">{snap_rev_share:.1f}%</div>
                    <div class="kpi-sub">${rev_snap:,.0f} en riesgo en {n_snap:,} productos sensibles</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Bloque: 3 Decisiones Inmediatas para Marketing
        md_sub = filtered_df.loc[filtered_df["primary_strategy"] == "Precios Dinámicos / Markdown (20%–35%)"]
        cs_sub = filtered_df.loc[filtered_df["primary_strategy"] == "Cross-Selling y Visibilidad Omnicanal (Sin Descuento)"]

        md_count = len(md_sub)
        md_rev_risk = float(md_sub["revenue_at_risk_usd"].sum())
        # Recuperación estimada al 25% de descuento en escenario esperado (ε=0.6)
        sim_lift_25 = (1.0 - 0.25) ** (-0.6) - 1.0
        md_est_rec = float((md_sub["pred_total_28d_units"] * sim_lift_25 * md_sub["current_price"] * 0.75).sum())

        cs_count = len(cs_sub)
        cs_rev_risk = float(cs_sub["revenue_at_risk_usd"].sum())

        st.markdown('<div class="section-heading">3 Decisiones Inmediatas para Marketing</div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="bento-grid-3">
                <div class="decision-card decision-top-blue">
                    <div class="decision-kicker" style="color:{APPLE_BLUE};">Decisión 1 · Descuentos Inteligentes</div>
                    <div class="decision-title">Aplicar rebaja del 20%–35% solo en productos que reaccionan al precio</div>
                    <div class="decision-metric">{md_count:,} productos · ${md_rev_risk:,.0f} en riesgo</div>
                    <div class="decision-body">
                        Con un descuento táctico del 25% se proyecta recuperar <strong>${md_est_rec:,.0f}</strong> en ventas incrementales.
                        Activar rotación FEFO y bajar la reposición posterior en <strong>-20% a -30%</strong>.
                    </div>
                </div>
                <div class="decision-card decision-top-amber">
                    <div class="decision-kicker" style="color:{APPLE_AMBER};">Decisión 2 · Combos sin rebajar precio</div>
                    <div class="decision-title">Armar paquetes Cross-Selling junto a productos ancla de alta rotación</div>
                    <div class="decision-metric">{cs_count:,} productos · ${cs_rev_risk:,.0f} en riesgo</div>
                    <div class="decision-body">
                        Estos artículos no responden a rebajas directas. Empaquetarlos con líderes de su misma tienda
                        y pasillo protege el margen bruto mientras acelera su salida de góndola.
                    </div>
                </div>
                <div class="decision-card decision-top-green">
                    <div class="decision-kicker" style="color:{APPLE_GREEN};">Decisión 3 · Calendario SNAP</div>
                    <div class="decision-title">Sincronizar stock y cupones con el ciclo mensual de pagos SNAP</div>
                    <div class="decision-metric">{n_snap:,} productos · ${rev_snap:,.0f} en riesgo</div>
                    <div class="decision-body">
                        <strong>Días 1–10:</strong> reforzar exhibición, multipacks y stock en picos de pago.<br>
                        <strong>Días 20–31:</strong> activar cupones de fin de mes en productos en desaceleración.
                    </div>
                </div>
            </div>
            """,
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
                    f'<div class="chart-takeaway"><strong>{top_st}</strong> concentra el {top_st_pct:.1f}% del dinero en riesgo (${top_st_val:,.0f}), liderando la prioridad de campaña.</div>',
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
                strat_agg = (
                    filtered_df.groupby(["primary_strategy", "strategy_short"], as_index=False)
                    .agg(
                        revenue_at_risk_usd=("revenue_at_risk_usd", "sum"),
                        sku_count=("id", "count"),
                    )
                    .sort_values("revenue_at_risk_usd", ascending=True)
                )
                strat_agg["axis_label"] = strat_agg["primary_strategy"].map(STRATEGY_AXIS_LABELS).fillna(strat_agg["strategy_short"])
                strat_agg["share_pct"] = (
                    strat_agg["revenue_at_risk_usd"] / total_rev * 100.0 if total_rev > 0 else 0.0
                )
                strat_agg["label_txt"] = strat_agg.apply(
                    lambda r: f"${r['revenue_at_risk_usd']:,.0f} · {r['share_pct']:.1f}%",
                    axis=1,
                )
                lead_row = strat_agg.iloc[-1]

                st.markdown('<div class="chart-question">¿Qué estrategia protege más ingresos?</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="chart-takeaway"><strong>{lead_row["strategy_short"]}</strong> cubre el {lead_row["share_pct"]:.1f}% del riesgo ({int(lead_row["sku_count"]):,} productos).</div>',
                    unsafe_allow_html=True,
                )

                fig_strat = px.bar(
                    strat_agg,
                    x="revenue_at_risk_usd",
                    y="axis_label",
                    orientation="h",
                    color="axis_label",
                    color_discrete_map=STRATEGY_AXIS_COLORS,
                    text="label_txt",
                    custom_data=["strategy_short", "sku_count", "share_pct"],
                    labels={"revenue_at_risk_usd": "Ingreso en riesgo (USD)", "axis_label": ""},
                )
                fig_strat.update_traces(
                    textposition="outside",
                    cliponaxis=False,
                    textfont=dict(size=11, color=APPLE_INK),
                    marker_line_width=0,
                    hovertemplate="<b>%{customdata[0]}</b><br>En riesgo: $%{x:,.0f} USD (%{customdata[2]:.1f}%)<br>Productos: %{customdata[1]:,}<extra></extra>",
                )
                max_strat = float(strat_agg["revenue_at_risk_usd"].max()) if len(strat_agg) else 1.0
                apply_apple_plotly_theme(
                    fig_strat,
                    height=370,
                    margin=dict(l=135, r=105, t=20, b=45),
                    show_legend=False,
                )
                fig_strat.update_xaxes(
                    showgrid=True,
                    gridcolor=APPLE_GRID,
                    tickprefix="$",
                    tickangle=0,
                    range=[0, max(max_strat * 1.38, 10.0)],
                )
                fig_strat.update_yaxes(showgrid=False, automargin=False)
                st.plotly_chart(fig_strat, width="stretch", theme=None)

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
    with tab2:
        hist90_df = load_history_90d()
        val_w4_df, forecast_df = load_predictions()

        sorted_for_select = filtered_df.sort_values("revenue_at_risk_usd", ascending=False)
        sku_ids_ordered = sorted_for_select["id"].tolist()
        sku_labels = {
            r.id: f"{r.display_name}  |  {r.risk_level}  |  ${r.revenue_at_risk_usd:,.2f} en riesgo"
            for r in sorted_for_select.itertuples(index=False)
        }

        sel_c1, sel_c2 = st.columns([3.3, 1.0])
        with sel_c1:
            selected_id = st.selectbox(
                "Elegir producto (ordenado de mayor a menor dinero en riesgo):",
                options=sku_ids_ordered,
                format_func=lambda x: sku_labels[x],
            )
        with sel_c2:
            st.write("")
            show_baselines = st.checkbox("Mostrar referencias (SES / MA28)", value=False)

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
                "+ reducir pedido post-oferta en 20%–30%"
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
            decision_sub = (
                f"No conviene rebajar precio (sin respuesta favorable a descuentos). "
                f"Exhibir en combo o cabecera junto a {anchor}, líder de rotación en {sku_row['store_id']} ({sku_row['dept_id']})."
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

        pills_html = risk_pill_html(sku_row["risk_level"])
        if sku_row["snap_priority"]:
            pills_html += '<span class="pill pill-snap">Prioridad SNAP (+15% o más)</span>'
        if sku_row["stockpiling_alert"]:
            pills_html += '<span class="pill pill-info">Alerta post-oferta: -20% a -30% pedido</span>'
        pills_html += f'<span class="pill pill-info">{sku_row["cluster_name"]}</span>'

        st.markdown(
            f"""
            <div class="semaphore-card {sem_cls}">
                <div>{pills_html}</div>
                <div class="sem-headline">{decision_headline}</div>
                <p class="sem-detail">{decision_sub} <strong>Calendario SNAP:</strong> {sku_row['snap_tactical_plan']}.</p>
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
                    <div class="kpi-label">Dinero en riesgo (28d)</div>
                    <div class="kpi-value-sm kpi-accent-red">${sku_row['revenue_at_risk_usd']:,.2f}</div>
                    <div class="kpi-sub">Precio actual: ${sku_row['current_price']:.2f}</div>
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
    with tab3:
        st.markdown('<div class="section-heading">Simulador de Descuentos Inteligentes (20%–35%)</div>', unsafe_allow_html=True)
        st.caption(
            "Simula el impacto de una rebaja únicamente sobre los productos en riesgo que demostraron responder positivamente a promociones (escenarios basados en Riesenegger y Hübner, 2026)."
        )

        markdown_df = filtered_df.loc[
            filtered_df["primary_strategy"] == "Precios Dinámicos / Markdown (20%–35%)"
        ].copy()

        if markdown_df.empty:
            st.info(
                "Los filtros actuales no incluyen productos elegibles para descuentos inteligentes. "
                "Abre 'Filtros avanzados' en el panel izquierdo para incluir esa estrategia."
            )
        else:
            with st.container(border=True):
                sc1, sc2 = st.columns([1.25, 1.35])
                with sc1:
                    disc_pct = st.slider(
                        "Nivel de descuento a simular:",
                        min_value=20,
                        max_value=35,
                        value=25,
                        step=1,
                        format="%d%%",
                    )
                with sc2:
                    elast_label = st.radio(
                        "Escenario de respuesta del consumidor:",
                        options=[
                            "Conservador (ε=0.4)",
                            "Esperado (ε=0.6)",
                            "Optimista (ε=0.8)",
                        ],
                        index=1,
                        horizontal=True,
                    )

            eps_map = {
                "Conservador (ε=0.4)": 0.4,
                "Esperado (ε=0.6)": 0.6,
                "Optimista (ε=0.8)": 0.8,
            }
            eps = eps_map[elast_label]
            d = disc_pct / 100.0
            demand_lift = (1.0 - d) ** (-eps) - 1.0

            base_units_28d = float(markdown_df["pred_total_28d_units"].sum())
            extra_units_28d = base_units_28d * demand_lift
            promo_unit_prices = markdown_df["current_price"] * (1.0 - d)
            recovered_rev_usd = float((markdown_df["pred_total_28d_units"] * demand_lift * promo_unit_prices).sum())
            eligible_risk_usd = float(markdown_df["revenue_at_risk_usd"].sum())
            coverage_pct = (recovered_rev_usd / eligible_risk_usd * 100.0) if eligible_risk_usd > 0 else 0.0

            # 5 Tarjetas HTML Bento (elimina definitivamente el recorte '-20% a -3...')
            st.markdown(
                f"""
                <div class="bento-grid-5">
                    <div class="kpi-card">
                        <div class="kpi-label">Productos aptos para rebaja</div>
                        <div class="kpi-value-sm">{len(markdown_df):,}</div>
                        <div class="kpi-sub">${eligible_risk_usd:,.0f} en riesgo elegible</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Aumento de demanda</div>
                        <div class="kpi-value-sm kpi-accent-blue">+{demand_lift * 100:.2f}%</div>
                        <div class="kpi-sub">Descuento {disc_pct}% · {elast_label}</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Unidades extra (28 días)</div>
                        <div class="kpi-value-sm">+{extra_units_28d:,.0f}</div>
                        <div class="kpi-sub">Sobre {base_units_28d:,.0f} unidades base</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Ingreso recuperado</div>
                        <div class="kpi-value-sm kpi-accent-green">${recovered_rev_usd:,.2f}</div>
                        <div class="kpi-sub">{coverage_pct:.1f}% del riesgo elegible</div>
                    </div>
                    <div class="kpi-card">
                        <div class="kpi-label">Ajuste de reposición</div>
                        <div class="kpi-value-sm kpi-accent-amber">-20% a -30%</div>
                        <div class="kpi-sub">Post-oferta (evitar sobrestock)</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.container(border=True):
                st.markdown(
                    '<div class="chart-question">¿Cómo cambia el ingreso recuperado según el porcentaje de descuento?</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div class="chart-takeaway">Regla operativa: al aplicar <strong>{disc_pct}%</strong> de rebaja en {len(markdown_df):,} productos, activar rotación FEFO y bajar la orden posterior en <strong>-20% a -30%</strong>.</div>',
                    unsafe_allow_html=True,
                )

                d_grid = np.arange(20, 36) / 100.0
                sim_rows = []
                for label_e, e_val in eps_map.items():
                    for dv in d_grid:
                        lift_v = (1.0 - dv) ** (-e_val) - 1.0
                        rec_v = float((markdown_df["pred_total_28d_units"] * lift_v * markdown_df["current_price"] * (1.0 - dv)).sum())
                        sim_rows.append(
                            {
                                "Descuento (%)": int(round(dv * 100)),
                                "Escenario": label_e,
                                "Incremento Demanda (%)": lift_v * 100.0,
                                "Ingreso Recuperado (USD)": rec_v,
                            }
                        )
                sim_curve_df = pd.DataFrame(sim_rows)
                fig_sim = px.line(
                    sim_curve_df,
                    x="Descuento (%)",
                    y="Ingreso Recuperado (USD)",
                    color="Escenario",
                    markers=True,
                    color_discrete_map={
                        "Conservador (ε=0.4)": "#8E8E93",
                        "Esperado (ε=0.6)": APPLE_BLUE,
                        "Optimista (ε=0.8)": APPLE_GREEN_BRIGHT,
                    },
                    hover_data={"Incremento Demanda (%)": ":.2f"},
                )
                fig_sim.add_shape(
                    type="line",
                    xref="x",
                    yref="paper",
                    x0=disc_pct,
                    x1=disc_pct,
                    y0=0.0,
                    y1=1.0,
                    line=dict(color=APPLE_RED, width=1.6, dash="dash"),
                )
                fig_sim.add_annotation(
                    x=disc_pct,
                    y=1.06,
                    xref="x",
                    yref="paper",
                    text=f"Descuento actual: {disc_pct}%",
                    showarrow=False,
                    font=dict(size=11, color=APPLE_RED),
                    bgcolor="#FFF2F2",
                    bordercolor="#FECACA",
                    borderwidth=1,
                    borderpad=3,
                )
                apply_apple_plotly_theme(
                    fig_sim,
                    height=330,
                    margin=dict(t=42, b=78, l=60, r=24),
                    legend_bottom=True,
                    legend_y=-0.22,
                )
                fig_sim.update_yaxes(tickprefix="$")
                st.plotly_chart(fig_sim, width="stretch", theme=None)

        st.markdown('<div class="section-heading" style="margin-top:1.1rem;">Plan de Acción Comercial (Lista Priorizada)</div>', unsafe_allow_html=True)

        plan_table_raw = filtered_df.sort_values("revenue_at_risk_usd", ascending=False).copy()
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
            ]
        ].copy()

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
        ]
        csv_bytes = plan_table_raw[export_cols].to_csv(index=False).encode("utf-8-sig")

        dl_l, dl_r = st.columns([2.6, 1.0])
        with dl_l:
            st.caption(f"Mostrando **{len(plan_display):,}** productos ordenados de mayor a menor dinero en riesgo.")
        with dl_r:
            st.download_button(
                label="Descargar plan (.CSV para Excel)",
                data=csv_bytes,
                file_name="plan_promociones_walmart_ca.csv",
                mime="text/csv",
                type="primary",
                width="stretch",
            )

        st.dataframe(
            plan_display,
            width="stretch",
            hide_index=True,
            height=450,
            column_config={
                "display_name": "Producto y Tienda",
                "risk_level": "Prioridad",
                "revenue_at_risk_usd": st.column_config.NumberColumn("Dinero en riesgo (USD)", format="$%.2f"),
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
            },
        )

    # =======================================================================
    # TAB 4 — 4. RESPALDO IA (AUDITORÍA TÉCNICA PARA DOCENTE)
    # =======================================================================
    with tab4:
        st.markdown('<div class="section-heading">A. Validación Temporal por Origen Rodante (4 Ventanas × 28 Días)</div>', unsafe_allow_html=True)
        st.caption(
            "Evaluación metodológica estrictamente cronológica sobre las 5,748 series (d_1830–d_1941) con cero data leakage."
        )

        val_summary = tables["val_summary"]
        val_by_window = tables["val_by_window"]
        val_breakdown = tables["val_breakdown"]
        fi_df = tables["feature_importance"]

        win_choice = st.selectbox(
            "Corte de validación:",
            options=[
                "Promedio 4 Ventanas",
                "Ventana 1 (2016-02-01 a 2016-02-28)",
                "Ventana 2 (2016-02-29 a 2016-03-27)",
                "Ventana 3 (2016-03-28 a 2016-04-24)",
                "Ventana 4 (2016-04-25 a 2016-05-22)",
            ],
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
                    text=f"K óptimo = {selected_k}",
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

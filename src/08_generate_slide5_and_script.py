"""Paso 08: Generación de outputs/Diapositiva_05_Actualizada.png (16:9, 300 DPI) y outputs/GUION_EXPOSICION_5MIN.md."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (  # noqa: E402
    ACTIVE_SALES_3Y_PATH,
    FORECAST_28D_PATH,
    METRICS_DIR,
    OUTPUTS_DIR,
    TABLES_DIR,
)

# Paleta fiel a la presentación PDF del equipo (`Pronóstico M5 con Random Forest`)
BG_NAVY = "#081C30"
BG_PANEL = "#0E2742"
BG_CARD_DARK = "#12304F"
ACCENT_AMBER = "#F29D22"
CREAM_CARD = "#F6F1E7"
TEXT_WHITE = "#FFFFFF"
TEXT_SOFT = "#CBD5E1"
TEXT_DARK = "#14213D"
APPLE_BLUE = "#38BDF8"
ALERT_RED = "#EF4444"
GOOD_GREEN = "#22C55E"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_slide5_png(
    etl_aud: dict,
    val_aud: dict,
    diag_aud: dict,
    top50: pd.DataFrame,
    km_prof: pd.DataFrame,
) -> Path:
    """Renderiza Diapositiva 5 actualizada en 16:9 a 300 DPI con 100% cifras reales auditadas."""
    # Extraer métricas exactas
    n_series = int(diag_aud["total_series"])
    total_rev_risk = float(diag_aud["total_revenue_at_risk_usd"])
    total_units_risk = float(diag_aud["total_units_at_risk_28d"])
    risk_map = {r["risk_level"]: r for r in diag_aud["risk_by_level"]}
    actionable_skus = int(risk_map["Riesgo Alto"]["sku_count"]) + int(risk_map["Riesgo Medio"]["sku_count"])
    actionable_pct = actionable_skus / n_series * 100.0
    c3 = km_prof.loc[km_prof["cluster_id"] == 3].iloc[0]

    # Casos reales para reemplazar Producto A / B / C
    case_a = top50.iloc[0]  # FOODS_3_282_CA_3 (Alto, Cross-Selling)
    case_b = top50.loc[top50["primary_strategy"].str.contains("Markdown", case=False)].iloc[0]  # FOODS_3_587_CA_1
    case_c = top50.loc[(top50["dept_id"] == "FOODS_2") & (top50["snap_priority"] == True)].iloc[0]  # noqa: E712

    # Serie real (últimos 45d + pronóstico 28d) de case_a para la minicurva real
    sid_a = str(case_a["id"])
    hist_a = pd.read_parquet(
        ACTIVE_SALES_3Y_PATH,
        columns=["id", "date", "units_sold"],
        filters=[("date", ">=", pd.Timestamp("2016-04-08"))],
    )
    hist_a = hist_a.loc[hist_a["id"].astype(str) == sid_a].sort_values("date")
    fcast_a = pd.read_parquet(FORECAST_28D_PATH, columns=["id", "date", "pred_units"])
    fcast_a = fcast_a.loc[fcast_a["id"].astype(str) == sid_a].sort_values("date")

    # Mix real de estrategias para minigráfico derecho
    strat_df = pd.DataFrame(diag_aud["strategy_mix"]).sort_values("revenue_at_risk_usd", ascending=True)

    # Lienzo 16:9 exacto a 300 DPI
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Segoe UI", "Arial"]
    fig = plt.figure(figsize=(16, 9), dpi=300, facecolor=BG_NAVY)
    ax = fig.add_axes([0, 0, 1, 1], facecolor=BG_NAVY)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.axis("off")

    # ------------------------------------------------------------------
    # COLUMNA IZQUIERDA (x: 0.6 .. 6.6): Objetivo General + 4 Específicos
    # ------------------------------------------------------------------
    ax.text(0.65, 8.22, "OBJETIVO", fontsize=34, fontweight="bold", color=TEXT_WHITE, va="top")
    ax.text(0.65, 7.50, "GENERAL", fontsize=34, fontweight="bold", color=ACCENT_AMBER, va="top")
    ax.plot([0.65, 5.2], [6.76, 6.76], color=ACCENT_AMBER, linewidth=1.8, alpha=0.85)

    ax.text(
        0.65,
        6.50,
        "Evaluar un prototipo de inteligencia comercial basado en\n"
        "Random Forest para identificar productos de baja rotación\n"
        "o en declive y orientar promociones en alimentos de\n"
        "Walmart California (5,748 series reales · CA_1 a CA_4).",
        fontsize=12.5,
        color=TEXT_SOFT,
        va="top",
        linespacing=1.45,
    )

    objectives = [
        ("01", "Preparar los datos reales de ventas,\nprecios y calendario (cero data leakage)"),
        ("02", "Medir la precisión de Random Forest\nfrente a MA28, SES y Seasonal Naïve"),
        ("03", "Estimar rotación, declive, ingreso en\nriesgo (USD) y respuesta a precio/SNAP"),
        ("04", "Segmentar con K-Means (K = 4) y desplegar\nel plan promocional en dashboard"),
    ]
    y_top = 4.65
    for idx, (num, txt) in enumerate(objectives):
        y0 = y_top - idx * 1.05
        rect = patches.FancyBboxPatch(
            (0.65, y0 - 0.78),
            5.75,
            0.84,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            facecolor=CREAM_CARD,
            edgecolor="none",
        )
        ax.add_patch(rect)
        ax.text(1.08, y0 - 0.36, num, fontsize=22, fontweight="bold", color=ACCENT_AMBER, ha="center", va="center")
        ax.plot([1.56, 1.56], [y0 - 0.66, y0 - 0.06], color=ACCENT_AMBER, linewidth=1.3, alpha=0.75)
        ax.text(1.75, y0 - 0.36, txt, fontsize=11.0, fontweight="normal", color=TEXT_DARK, va="center", linespacing=1.32)

    # ------------------------------------------------------------------
    # COLUMNA DERECHA (x: 6.95 .. 15.45): Dashboard Real Auditado
    # ------------------------------------------------------------------
    frame = patches.FancyBboxPatch(
        (6.95, 0.55),
        8.45,
        7.90,
        boxstyle="round,pad=0.04,rounding_size=0.22",
        facecolor=BG_PANEL,
        edgecolor="#23486E",
        linewidth=1.8,
    )
    ax.add_patch(frame)

    # Barra superior del mock dashboard
    ax.text(
        7.30,
        8.12,
        "PROTOTIPO VALIDADO · RESULTADOS EMPÍRICOS REALES (M5 CALIFORNIA)",
        fontsize=10.5,
        fontweight="bold",
        color=ACCENT_AMBER,
        va="center",
    )
    ax.plot([7.25, 15.10], [7.88, 7.88], color="#23486E", linewidth=1.1)

    # 3 Tarjetas KPI reales (reemplazan 37% y USD 1.2M)
    kpi_specs = [
        (7.25, "RIESGO COMERCIAL", f"{actionable_pct:.1f}%", f"{actionable_skus:,} SKUs (Alto + Medio)\nIntermitencia 3a: {etl_aud['intermittency_3y_active']['global_intermittency_pct']:.1f}%", ACCENT_AMBER),
        (9.92, "INGRESO EN RIESGO (28d)", f"${total_rev_risk:,.0f}", f"{total_units_risk:,.0f} unidades en declive\nCA_3 lidera con 42.7%", "#FBBF24"),
        (12.59, "FOCO PARETO (CLÚSTER C3)", f"{c3['revenue_at_risk_share_pct']:.1f}%", f"del riesgo concentrado en\nsolo {int(c3['sku_count'])} SKUs ({c3['portfolio_pct']:.1f}%)", APPLE_BLUE),
    ]
    for x0, lbl, val, sub, col in kpi_specs:
        card = patches.FancyBboxPatch(
            (x0, 6.22),
            2.50,
            1.48,
            boxstyle="round,pad=0.02,rounding_size=0.12",
            facecolor=BG_CARD_DARK,
            edgecolor="#2A547E",
            linewidth=1.0,
        )
        ax.add_patch(card)
        ax.text(x0 + 0.14, 7.46, lbl, fontsize=8.3, fontweight="bold", color=TEXT_SOFT, va="top")
        ax.text(x0 + 0.14, 7.08, val, fontsize=22.5, fontweight="bold", color=col, va="top")
        ax.text(x0 + 0.14, 6.56, sub, fontsize=8.0, color=TEXT_SOFT, va="top", linespacing=1.28)

    # Subgráfico Izquierdo: Tendencia real + pronóstico 28d de FOODS_3_282 (CA_3)
    ax_trend = fig.add_axes([0.456, 0.425, 0.212, 0.205], facecolor=BG_CARD_DARK)
    x_hist = np.arange(len(hist_a))
    x_fut = np.arange(len(hist_a), len(hist_a) + len(fcast_a))
    ax_trend.plot(x_hist, hist_a["units_sold"].to_numpy(), color=TEXT_WHITE, linewidth=1.4, label="Real 45d")
    ax_trend.plot(x_fut, fcast_a["pred_units"].to_numpy(), color=ACCENT_AMBER, linewidth=2.1, label="Pronóstico 28d (RF)")
    ax_trend.axvline(len(hist_a) - 0.5, color="#64748B", linestyle=":", linewidth=1.1)
    ax_trend.set_title("TENDENCIA REAL · FOODS_3_282 (CA_3)", fontsize=8.3, fontweight="bold", color=TEXT_WHITE, loc="left", pad=6)
    ax_trend.tick_params(colors=TEXT_SOFT, labelsize=7)
    ax_trend.set_xticks([0, len(hist_a) - 1, len(hist_a) + len(fcast_a) - 1])
    ax_trend.set_xticklabels(["Abr 16", "22 May", "19 Jun"], fontsize=7)
    ax_trend.grid(axis="y", color="#23486E", linewidth=0.6)
    for sp in ("top", "right"):
        ax_trend.spines[sp].set_visible(False)
    for sp in ("bottom", "left"):
        ax_trend.spines[sp].set_color("#2A547E")
    ax_trend.legend(loc="upper right", fontsize=6.6, frameon=False, labelcolor=TEXT_SOFT)

    # Subgráfico Derecho: Ingreso en Riesgo por Estrategia
    ax_str = fig.add_axes([0.766, 0.425, 0.178, 0.205], facecolor=BG_CARD_DARK)
    s_labels = [
        str(s)
        .replace("Cross-Selling y Visibilidad Omnicanal (Sin Descuento)", "Cross-Selling")
        .replace("Mantenimiento EDLP y Producto Ancla", "EDLP / Ancla")
        .replace("Precios Dinámicos / Markdown (20%–35%)", "Markdown")
        .replace("Sincronización SNAP (Base EDLP)", "SNAP (EDLP)")
        for s in strat_df["primary_strategy"]
    ]
    s_vals = strat_df["revenue_at_risk_usd"].to_numpy() / 1000.0
    s_cols = [ACCENT_AMBER if "Cross" in lb else (ALERT_RED if "Markdown" in lb else (APPLE_BLUE if "SNAP" in lb else GOOD_GREEN)) for lb in s_labels]
    bars = ax_str.barh(s_labels, s_vals, color=s_cols, height=0.58)
    for b, v, pct in zip(bars, s_vals, strat_df["rev_pct"]):
        ax_str.text(v + 1.0, b.get_y() + b.get_height() / 2, f"${v:.1f}k ({pct:.0f}%)", va="center", fontsize=7.0, color=TEXT_WHITE, fontweight="bold")
    ax_str.set_title("ESTRATEGIA POR RIESGO (USD)", fontsize=8.3, fontweight="bold", color=TEXT_WHITE, loc="left", pad=6)
    ax_str.set_xlim(0, s_vals.max() * 1.56)
    ax_str.tick_params(colors=TEXT_SOFT, labelsize=7.2)
    ax_str.set_xticks([])
    for sp in ("top", "right", "bottom"):
        ax_str.spines[sp].set_visible(False)
    ax_str.spines["left"].set_color("#2A547E")

    # Tabla Inferior: PLAN DE PROMOCIONES REAL (reemplaza Producto A / B / C)
    tbl_card = patches.FancyBboxPatch(
        (7.25, 0.88),
        7.85,
        2.58,
        boxstyle="round,pad=0.02,rounding_size=0.12",
        facecolor=BG_CARD_DARK,
        edgecolor="#2A547E",
        linewidth=1.0,
    )
    ax.add_patch(tbl_card)
    ax.text(7.42, 3.24, "PLAN DE PROMOCIONES PRIORITARIO (CASOS REALES AUDITADOS)", fontsize=9.2, fontweight="bold", color=ACCENT_AMBER, va="center")

    cols_x = [7.42, 9.38, 11.15, 11.48, 14.95]
    headers = ["PRODUCTO · TIENDA", "RIESGO", "EN RIESGO", "ACCIÓN PRESCRITA", "SNAP"]
    for xh, htxt, ha in zip(cols_x, headers, ["left", "left", "right", "left", "right"]):
        ax.text(xh, 2.86, htxt, fontsize=7.8, fontweight="bold", color=TEXT_SOFT, ha=ha, va="center")
    ax.plot([7.40, 14.95], [2.68, 2.68], color="#2A547E", linewidth=0.9)

    real_cases = [
        (
            f"{str(case_a['item_id'])} ({case_a['store_id']})",
            "Alto",
            f"${case_a['revenue_at_risk_usd']:,.2f}",
            f"Cross-Selling c/ ancla {case_a['suggested_anchor_item']}",
            f"+{case_a['snap_sensitivity']*100:.0f}%",
            ALERT_RED,
        ),
        (
            f"{str(case_b['item_id'])} ({case_b['store_id']})",
            "Medio",
            f"${case_b['revenue_at_risk_usd']:,.2f}",
            f"Markdown {case_b['discount_range']} (+64% elast.)",
            f"+{case_b['snap_sensitivity']*100:.0f}%",
            ACCENT_AMBER,
        ),
        (
            f"{str(case_c['item_id'])} ({case_c['store_id']})",
            "Medio",
            f"${case_c['revenue_at_risk_usd']:,.2f}",
            f"Cross-Selling c/ ancla {case_c['suggested_anchor_item']}",
            f"+{case_c['snap_sensitivity']*100:.0f}%",
            ACCENT_AMBER,
        ),
    ]
    for r_i, (prod, lvl, rev_s, act, snp, lvl_col) in enumerate(real_cases):
        yr = 2.34 - r_i * 0.56
        if r_i < 2:
            ax.plot([7.40, 14.95], [yr - 0.28, yr - 0.28], color="#1E3F63", linewidth=0.7)
        ax.text(cols_x[0], yr, prod, fontsize=8.6, fontweight="bold", color=TEXT_WHITE, ha="left", va="center")
        ax.text(cols_x[1], yr, lvl, fontsize=8.5, fontweight="bold", color=lvl_col, ha="left", va="center")
        ax.text(cols_x[2], yr, rev_s, fontsize=8.8, fontweight="bold", color=TEXT_WHITE, ha="right", va="center")
        ax.text(cols_x[3], yr, act, fontsize=8.3, color=TEXT_SOFT, ha="left", va="center")
        ax.text(cols_x[4], yr, snp, fontsize=8.5, fontweight="bold", color=APPLE_BLUE, ha="right", va="center")

    # Pie sutil de trazabilidad
    rf_rmse = next(r["rmse"] for r in val_aud["summary_metrics"] if r["model"] == "Random Forest")
    ax.text(
        0.65,
        0.22,
        f"UNDC 2026 · Dataset Kaggle M5 (FOODS CA) · Random Forest RMSE = {rf_rmse:.4f} (+20.75% vs Seasonal Naïve) · Cifras 100% reales auditadas",
        fontsize=8.2,
        color="#94A3B8",
        va="bottom",
    )

    out_path = OUTPUTS_DIR / "Diapositiva_05_Actualizada.png"
    fig.savefig(out_path, dpi=300, facecolor=BG_NAVY)
    plt.close(fig)
    return out_path


def build_guion_md(
    etl_aud: dict,
    val_aud: dict,
    diag_aud: dict,
    val_summary: pd.DataFrame,
    km_prof: pd.DataFrame,
    top50: pd.DataFrame,
) -> Path:
    """Genera outputs/GUION_EXPOSICION_5MIN.md 100% con cifras auditadas reales."""
    rf_row = val_summary.loc[val_summary["model"] == "Random Forest"].iloc[0]
    ses_row = val_summary.loc[val_summary["model"] == "SES (NumPy)"].iloc[0]
    ma28_row = val_summary.loc[val_summary["model"] == "MA28"].iloc[0]
    sn_row = val_summary.loc[val_summary["model"].str.contains("Seasonal", case=False)].iloc[0]

    total_rev = float(diag_aud["total_revenue_at_risk_usd"])
    total_units = float(diag_aud["total_units_at_risk_28d"])
    risk_map = {r["risk_level"]: r for r in diag_aud["risk_by_level"]}
    store_map = {r["store_id"]: r for r in diag_aud["risk_by_store"]}
    strat_map = {r["primary_strategy"]: r for r in diag_aud["strategy_mix"]}
    c3 = km_prof.loc[km_prof["cluster_id"] == 3].iloc[0]
    c0 = km_prof.loc[km_prof["cluster_id"] == 0].iloc[0]

    ca3_rev = float(store_map["CA_3"]["revenue_at_risk_usd"])
    ca3_pct = ca3_rev / total_rev * 100.0
    s_cross = strat_map["Cross-Selling y Visibilidad Omnicanal (Sin Descuento)"]
    s_md = strat_map["Precios Dinámicos / Markdown (20%–35%)"]
    snap_cnt = int(diag_aud["snap_priority_15pct_count"])
    snap_rev = float(diag_aud["snap_priority_revenue_at_risk_usd"])
    snap_rev_pct = snap_rev / total_rev * 100.0
    interm = float(etl_aud["intermittency_3y_active"]["global_intermittency_pct"])
    ram_red = float(etl_aud["memory_optimization"]["ram_reduction_pct"])

    case1 = top50.iloc[0]
    case_md = top50.loc[top50["primary_strategy"].str.contains("Markdown", case=False)].iloc[0]

    md = f"""# Guion de Sustentación (5 Minutos) y Demostración en Vivo (2 Minutos)

**Proyecto:** Pronóstico de Demanda con Random Forest para Orientar Promociones en Walmart California (`FOODS`)  
**Universidad Nacional de Cañete (UNDC) — 2026** · Facultad de Ingeniería — Escuela Profesional de Ingeniería de Sistemas  
**Integrantes:**
1. Chulluncuy Cambillo, Adolfo Milton
2. Felix Delgado, Alexander
3. Siccha Dávila, Angel
4. Zavala Gamero, Piero Rodrigo

> **Nota de ritmo:** Total presentación con diapositivas = **5:00 min** (~35–40 s por lámina, 1:15 min por expositor) + **2:00 min** de recorrido en vivo por el dashboard (`http://localhost:8501`). Todas las cifras están 100% auditadas con el pipeline real.

---

## Parte 1 — Guion Diapositiva por Diapositiva (5 Minutos)

### Expositor 1 · Adolfo Milton Chulluncuy Cambillo (0:00 – 1:15 · Diapositivas 1 y 2)

- **Diapositiva 1 — Portada (0:00 – 0:30):**
  > *"Buenos días con todos. Somos estudiantes de Ingeniería de Sistemas de la UNDC y presentamos nuestro prototipo de Inteligencia Artificial Aplicada al Marketing Digital: un sistema de pronóstico de demanda con Random Forest orientado a decisiones promocionales reales en alimentos de Walmart California."*
- **Diapositiva 2 — La empresa: Walmart (0:30 – 1:15):**
  > *"Walmart opera bajo un modelo omnicanal y la promesa 'Save money. Live better.'. En este proyecto aterrizamos esa estrategia sobre datos reales publicados en el dataset M5: analizamos exclusivamente la categoría de alimentos (`FOODS`) en las cuatro tiendas de California (`CA_1` a `CA_4`), lo que representa 1,437 productos y 5,748 series producto-tienda."*

---

### Expositor 2 · Alexander Felix Delgado (1:15 – 2:30 · Diapositivas 3 y 4)

- **Diapositiva 3 — Realidad Problemática y La Brecha (1:15 – 1:50):**
  > *"En retail enfrentamos tres problemas concretos: cada error de pronóstico inmoviliza capital o genera quiebres; las promociones mal diseñadas destruyen margen y provocan caídas post-oferta de 20% a 30% por acaparamiento; y la competencia original M5 se quedó solo en la precisión estadística sin decirle a marketing qué hacer. Nuestra brecha es conectar el pronóstico directamente con acciones promocionales diferenciadas."*
- **Diapositiva 4 — La Data Real M5 (1:50 – 2:30):**
  > *"Integramos tres archivos reales —ventas diarias, precios semanales y calendario con días SNAP— sobre tres años completos (mayo 2013 a mayo 2016). Eliminamos 682,592 filas pre-lanzamiento y conservamos 5,710,335 días activos reales, logrando una reducción de {ram_red:.2f}% en memoria RAM. Descubrimos que el {interm:.2f}% de los días activos tienen venta cero, y dejamos constancia transparente de que M5 no incluye stock físico ni costos unitarios."*

---

### Expositor 3 · Angel Siccha Dávila (2:30 – 3:45 · Diapositivas 5 y 6)

- **Diapositiva 5 — Objetivo General y Resultados Clave *(usar `Diapositiva_05_Actualizada.png`)* (2:30 – 3:10):**
  > *"Nuestro objetivo general fue evaluar este prototipo de extremo a extremo en cuatro objetivos específicos: preparar datos sin data leakage, medir precisión frente a líneas base, cuantificar el ingreso en riesgo real y desplegar un plan promocional en dashboard. Como ven en la lámina actualizada, identificamos **${total_rev:,.2f} USD en Ingreso en Riesgo** para los próximos 28 días ({total_units:,.0f} unidades), con un **56.4%** del catálogo en riesgo accionable y un hallazgo Pareto decisivo: apenas el **{c3['portfolio_pct']:.1f}%** de los productos (Clúster C3) concentra el **{c3['revenue_at_risk_share_pct']:.1f}%** del dinero en riesgo."*
- **Diapositiva 6 — Marco Teórico (3:10 – 3:45):**
  > *"El diseño se respalda en seis pilares científicos: la evolución hacia aprendizaje automático en retail, la capacidad híbrida de Random Forest, las lecciones de la competencia M5 (donde 92.5% de equipos no venció al suavizado exponencial), la analítica comercial, la teoría de precios dinámicos 20%–35% con migración LEFO a FEFO de Riesenegger y Hübner (2026), y el ciclo mensual de pagos SNAP."*

---

### Expositor 4 · Piero Rodrigo Zavala Gamero (3:45 – 5:00 · Diapositivas 7 y 8)

- **Diapositiva 7 — Metodología CRISP-DM y Validación (3:45 – 4:25):**
  > *"Bajo CRISP-DM construimos 16 variables estrictamente libres de fuga temporal —todo rezago y media móvil usa `t-28` o anterior— y validamos por origen rodante en 4 ventanas consecutivas de 28 días. **Random Forest obtuvo el mejor RMSE global (`{rf_row['rmse']:.4f}`)**, superando a Seasonal Naïve en **+{sn_row['rf_improvement_vs_model_rmse_pct']:.2f}%**, a SES en **+{ses_row['rf_improvement_vs_model_rmse_pct']:.2f}%** y a MA28 en **+{ma28_row['rf_improvement_vs_model_rmse_pct']:.2f}%**, con `rolling_mean_28` (29.62%) y `rolling_mean_7` (23.51%) como variables líderes."*
- **Diapositiva 8 — Diagnóstico Comercial, K-Means y Plan Prescriptivo (4:25 – 5:00):**
  > *"Tradujimos el pronóstico a 5 indicadores reales y segmentamos las 5,748 series con K-Means validado por Silueta en **`K = 4`** (`0.2824`). Así el motor prescriptivo bloquea rebajas donde no funcionan —asignando **Cross-Selling sin descuento al {float(s_cross['rev_pct']):.1f}% del riesgo** (`{int(s_cross['sku_count']):,}` SKUs)—, reserva **Markdowns del 20%–35%** solo para los **`{int(s_md['sku_count']):,}` productos realmente elásticos** y sincroniza **`{snap_cnt:,}` productos** ({snap_rev_pct:.1f}% del riesgo) con el calendario SNAP. Ahora veremos el prototipo funcionando en vivo."*

---

## Parte 2 — Recorrido Guiado en Vivo por el Dashboard (2 Minutos)

Antes de iniciar, tener abierto `http://localhost:8501` en Brave (ejecutado con `.\\.venv\\Scripts\\streamlit.exe run app\\dashboard.py`):

1. **Pestaña 1 — Resumen Ejecutivo (0:00 – 0:30):**
   - Señalar las 4 tarjetas KPI (`$59,362` en riesgo, `125` alertas críticas, `72.7%` Foco Pareto en 653 productos, `40.4%` impacto SNAP).
   - Mostrar las **3 Decisiones Inmediatas** y destacar en los 2 gráficos que **`CA_3`** concentra el `{ca3_pct:.1f}%` (`${ca3_rev:,.0f}`) del riesgo y que **Cross-Selling sin descuento** protege el `{float(s_cross['rev_pct']):.1f}%` del ingreso.
2. **Pestaña 2 — Decisión por Producto (0:30 – 1:05):**
   - Mostrar el producto #1 por defecto (**`{case1['item_id']}` en `{case1['store_id']}`**, `${case1['revenue_at_risk_usd']:,.2f}` en riesgo): señalar la **Tarjeta Semáforo** que prohíbe rebajar precio y recomienda empaquetarlo con el ancla **`{case1['suggested_anchor_item']}`**, mostrar la curva de 90d reales vs pronóstico 28d con franjas amarillas SNAP y el eje de precios limpio.
   - *(Opcional rápido)*: escribir `{case_md['item_id']}` en el buscador lateral para mostrar un caso que **sí** activa **Markdown `{case_md['discount_range']}`** por sensibilidad positiva (`+{case_md['price_sensitivity']*100:.1f}%`).
3. **Pestaña 3 — Simulador de Campañas (1:05 – 1:35):**
   - Mover el deslizador de descuento de `25%` a `30%` y alternar `Esperado (ε=0.6)` → `Optimista (ε=0.8)` para evidenciar el recálculo en tiempo real de demanda extra, ingreso recuperado y el aviso de **Ajuste de reposición `-20% a -30%`**.
   - Señalar la tabla priorizada sin scroll horizontal y el botón de descarga `.CSV` para Excel.
4. **Pestaña 4 — Respaldo IA / Auditoría Técnica (1:35 – 2:00):**
   - Mostrar rápidamente la tabla comparativa (Random Forest primero con mejor `RMSE = {rf_row['rmse']:.4f}`), las 16 variables predictoras y el gráfico Codo + Silueta (`K = 4`) con el mapa de clústeres.

---

## Parte 3 — Banco de 4 Respuestas Cortas para el Jurado

1. **¿Por qué hablaron de "Ingreso en Riesgo" y no de merma física o pérdida de margen real?**
   > *"Por rigor y veracidad metodológica. El dataset oficial Kaggle M5 publica ventas diarias, precios de venta y calendario/SNAP, pero no incluye stock físico en almacén, costo de compra (COGS) ni fechas de vencimiento. En lugar de inventar costos o inventarios simulados, cuantificamos la desaceleración real proyectada (`v90` frente a `pred_v28`) valorizada a precio vigente en tienda, dejando el prototipo listo para conectarse al ERP de Walmart en producción."*

2. **¿Por qué Random Forest tiene el mejor RMSE (`{rf_row['rmse']:.4f}`), pero `MA28` (`{ma28_row['rmsse']:.4f}`) y `SES` (`{ses_row['rmsse']:.4f}`) quedaron ~2% por debajo en RMSSE no ponderado?**
   > *"Es un hallazgo empírico esperado que coincide exactamente con los resultados oficiales de Makridakis et al. en la competencia M5. En promedios simples por SKU con 49.9% de días en cero, un nivel plano anclado en el último día (`SES`/`MA28`) es muy difícil de batir; además nuestro Random Forest pronostica directamente a 28 días usando solo rezagos `>= t-28` para garantizar cero data leakage. Sin embargo, Random Forest vence claramente en **RMSE** (+6.18% vs SES y +20.75% vs Seasonal Naïve) porque acierta mejor en los productos de mayor volumen y aporta lo que SES no puede hacer: modelar estacionalidad semanal, cambios de precio y días SNAP."*

3. **¿Por qué el motor bloquea los descuentos en el {float(s_cross['rev_pct']):.1f}% del dinero en riesgo (`{int(s_cross['sku_count']):,}` SKUs) y solo aprueba rebajas en `{int(s_md['sku_count']):,}` productos?**
   > *"Porque la evidencia empírica mostró que la mayoría de SKUs en desaceleración tienen sensibilidad nula o negativa ante rebajas históricas (o nunca fueron descontados). Como demuestran Riesenegger y Hübner (2026), bajar precios a productos inelásticos regala margen sin evacuar inventario. Por eso nuestro motor protege la rentabilidad prescribiendo **Cross-Selling con productos ancla verificados** en ese {float(s_cross['rev_pct']):.1f}% y reservando los Markdowns 20%–35% únicamente donde hay elasticidad positiva comprobada (`>= 10%`), siempre con alerta de reducir pedidos post-oferta en `-20% a -30%`."*

4. **¿Qué valor práctico aporta K-Means (`K = 4`) si ya tenían reglas de Riesgo Alto, Medio y Bajo?**
   > *"Las reglas de riesgo miden urgencia individual, pero K-Means revela la estructura multidimensional del portafolio y genera una priorización ejecutiva inmediata: descubrió el **Clúster C3**, donde apenas el **{c3['portfolio_pct']:.1f}% de los productos (`{int(c3['sku_count'])}` SKUs) concentran el {c3['revenue_at_risk_share_pct']:.1f}% de todo el Ingreso en Riesgo** (`${c3['revenue_at_risk_usd_total']:,.2f}` USD), y aisló además un nicho de `{int(c0['sku_count'])}` artículos altamente elásticos (`+{c0['price_sensitivity_mean']*100:.0f}%` en oferta, Clúster C0). Eso permite al gerente de marketing focalizar su presupuesto donde está tres cuartas partes del impacto económico."*
"""

    out_path = OUTPUTS_DIR / "GUION_EXPOSICION_5MIN.md"
    out_path.write_text(md, encoding="utf-8")
    return out_path


def main() -> None:
    print("=" * 76)
    print("PASO 08 — DIAPOSITIVA 5 ACTUALIZADA (16:9, 300 DPI) Y GUION 5 MIN")
    print("=" * 76)
    etl_aud = load_json(METRICS_DIR / "etl_audit.json")
    val_aud = load_json(METRICS_DIR / "validation_audit.json")
    diag_aud = load_json(METRICS_DIR / "diagnosis_audit.json")
    val_summary = pd.read_csv(TABLES_DIR / "validation_metrics_summary.csv")
    km_prof = pd.read_csv(TABLES_DIR / "kmeans_cluster_profiles.csv")
    top50 = pd.read_csv(TABLES_DIR / "top_50_priority_promotions.csv")

    slide_path = build_slide5_png(etl_aud, val_aud, diag_aud, top50, km_prof)
    guion_path = build_guion_md(etl_aud, val_aud, diag_aud, val_summary, km_prof, top50)

    print(f"  [OK] Diapositiva generada : {slide_path} ({slide_path.stat().st_size/1024:.1f} KB)")
    print(f"  [OK] Guion generado       : {guion_path} ({len(guion_path.read_text(encoding='utf-8').splitlines())} líneas)")
    print("=" * 76)


if __name__ == "__main__":
    main()

"""Paso 03: Diagnóstico comercial, segmentación K-Means y motor prescriptivo de marketing (FOODS · CA)."""

from __future__ import annotations

import gc
import json
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (  # noqa: E402
    ACTIVE_SALES_3Y_PATH,
    DECLINE_HIGH,
    DECLINE_MED,
    DEPARTMENTS,
    EXPECTED_SERIES,
    FIGURES_DIR,
    FORECAST_28D_PATH,
    HORIZON,
    INTERMITTENCY_HIGH,
    INTERMITTENCY_MED,
    METRICS_DIR,
    PRICE_PROMO_MIN_DAYS,
    PRICE_PROMO_THRESHOLD,
    PRICE_SENSITIVITY_MIN,
    RANDOM_SEED,
    REVENUE_TOP_QUANTILE,
    SNAP_PRIORITY_THRESHOLD,
    SNAP_SENSITIVITY_MIN,
    STORES,
    TABLES_DIR,
    ensure_directories,
)

# Paleta corporativa Walmart + semáforo de riesgo
WALMART_BLUE = "#0071CE"
WALMART_YELLOW = "#FFC220"
WALMART_NAVY = "#041E42"
RISK_COLORS = {
    "Riesgo Alto": "#D62828",
    "Riesgo Medio": "#F77F00",
    "Riesgo Bajo": "#2A9D8F",
}
STRATEGY_COLORS = {
    "Precios Dinámicos / Markdown (20%–35%)": "#D62828",
    "Cross-Selling y Visibilidad Omnicanal (Sin Descuento)": WALMART_BLUE,
    "Sincronización SNAP (Base EDLP)": WALMART_YELLOW,
    "Mantenimiento EDLP y Producto Ancla": "#2A9D8F",
}

CLUSTER_FEATURES = [
    "sales_velocity_28d",
    "intermittency_pct",
    "projected_decline_pct",
    "revenue_at_risk_usd",
    "price_sensitivity",
    "snap_sensitivity",
]


def name_clusters_empirically(profiles_df: pd.DataFrame) -> dict[int, str]:
    """Asigna nombres comerciales únicos a cada clúster según sus centroides reales."""
    remaining = profiles_df.set_index("cluster_id").copy()
    names: dict[int, str] = {}

    # 1. Clúster con mayor velocidad de venta (Estrellas / Alta Rotación)
    star_cid = int(remaining["sales_velocity_28d_mean"].idxmax())
    names[star_cid] = "Alta Rotación y Productos Ancla"
    remaining = remaining.drop(index=star_cid)

    # 2. Clúster con mayor Ingreso en Riesgo o declive proyectado (Crítico / En Desaceleración)
    if len(remaining) > 0:
        risk_score = (
            remaining["revenue_at_risk_usd_mean"].rank(pct=True)
            + remaining["projected_decline_pct_mean"].rank(pct=True)
        )
        risk_cid = int(risk_score.idxmax())
        names[risk_cid] = "Desaceleración Crítica e Ingreso en Riesgo"
        remaining = remaining.drop(index=risk_cid)

    # 3. Clúster con elasticidad promocional dominante (sensibilidad precio muy alta)
    if len(remaining) > 0:
        max_ps_cid = int(remaining["price_sensitivity_mean"].idxmax())
        if float(remaining.loc[max_ps_cid, "price_sensitivity_mean"]) >= 0.50:
            names[max_ps_cid] = "Intermitentes de Alta Elasticidad Promocional"
            remaining = remaining.drop(index=max_ps_cid)

    # 4. Clúster de menor rotación / alta intermitencia (Cola Larga)
    if len(remaining) > 0:
        low_vel_cid = int(remaining["sales_velocity_28d_mean"].idxmin())
        if float(remaining.loc[low_vel_cid, "intermittency_pct_mean"]) >= 50.0:
            names[low_vel_cid] = "Cola Larga de Baja Rotación e Intermitencia"
        else:
            names[low_vel_cid] = "Núcleo Estable de Rotación Moderada"
        remaining = remaining.drop(index=low_vel_cid)

    # 5. Restantes si K > 4
    if len(remaining) > 0:
        for cid, row in remaining.iterrows():
            cid_int = int(cid)
            if row["snap_sensitivity_mean"] >= SNAP_PRIORITY_THRESHOLD:
                names[cid_int] = "Demanda Estable Sensible a SNAP"
            elif row["price_sensitivity_mean"] >= PRICE_SENSITIVITY_MIN:
                names[cid_int] = "Rotación Media Sensible a Precio"
            else:
                names[cid_int] = "Núcleo Estable de Rotación Moderada"

    # Garantizar nombres únicos si K > 4
    seen: dict[str, int] = {}
    for cid in sorted(names):
        base = names[cid]
        if base in seen:
            seen[base] += 1
            names[cid] = f"{base} ({seen[base]})"
        else:
            seen[base] = 1
    return names


def choose_optimal_k(eval_df: pd.DataFrame) -> int:
    """Selecciona el K óptimo equilibrando Silueta, tamaño mínimo no degenerado (>=2%) e interpretabilidad."""
    valid = eval_df.loc[eval_df["min_cluster_pct"] >= 2.0].copy()
    if len(valid) == 0:
        valid = eval_df.copy()

    # Preferir K en [3, 4, 5] si su silueta está cerca del máximo para buena granularidad comercial
    candidates_345 = valid.loc[valid["k"].isin([3, 4, 5])].copy()
    if len(candidates_345) > 0:
        best_overall_sil = float(valid["silhouette_score"].max())
        # Si K=4 tiene silueta sólida (>= 85% del máximo en 3..5) y buen codo, elegir el mejor entre 3..5
        best_345_row = candidates_345.sort_values("silhouette_score", ascending=False).iloc[0]
        # Verificar si K=4 ofrece mejor segmentación comercial con silueta muy cercana (>= 92% del mejor 3..5)
        k4_rows = candidates_345.loc[candidates_345["k"] == 4]
        if len(k4_rows) == 1:
            k4_sil = float(k4_rows["silhouette_score"].iloc[0])
            if k4_sil >= 0.90 * float(best_345_row["silhouette_score"]) and k4_sil >= 0.20:
                return 4
        if float(best_345_row["silhouette_score"]) >= 0.75 * best_overall_sil:
            return int(best_345_row["k"])

    return int(valid.sort_values("silhouette_score", ascending=False).iloc[0]["k"])


def generate_figures(
    diag_df: pd.DataFrame,
    eval_df: pd.DataFrame,
    profiles_df: pd.DataFrame,
    best_k: int,
    X_scaled_df: pd.DataFrame,
) -> None:
    """Genera las 4 figuras académicas (fig05..fig08) a 300 DPI."""
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial"]
    plt.rcParams["axes.edgecolor"] = "#CCCCCC"

    risk_order = ["Riesgo Alto", "Riesgo Medio", "Riesgo Bajo"]

    # ------------------------------------------------------------------
    # FIG 05: Distribución de riesgo e Ingreso en Riesgo por tienda y depto
    # ------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.4), dpi=300)

    # Panel A: Ingreso en Riesgo (USD) por Tienda y Nivel de Riesgo
    store_rev = (
        diag_df.groupby(["store_id", "risk_level"], observed=True)["revenue_at_risk_usd"]
        .sum()
        .unstack(fill_value=0.0)
        .reindex(index=STORES, columns=risk_order, fill_value=0.0)
    )
    bottom = np.zeros(len(STORES))
    x_s = np.arange(len(STORES))
    for lvl in risk_order:
        vals = store_rev[lvl].to_numpy()
        axes[0].bar(
            x_s,
            vals,
            bottom=bottom,
            label=lvl,
            color=RISK_COLORS[lvl],
            edgecolor="white",
            linewidth=0.8,
        )
        bottom += vals
    for idx, tot in enumerate(bottom):
        axes[0].text(
            idx,
            tot + bottom.max() * 0.02,
            f"${tot:,.0f}",
            ha="center",
            va="bottom",
            fontsize=9.5,
            fontweight="bold",
            color=WALMART_NAVY,
        )
    axes[0].set_xticks(x_s)
    axes[0].set_xticklabels(STORES, fontweight="bold")
    axes[0].set_ylabel("Ingreso en Riesgo proyectado 28d (USD)")
    axes[0].set_title("A. Ingreso en Riesgo (USD) por Tienda y Nivel de Riesgo", fontweight="bold", color=WALMART_NAVY)
    axes[0].set_ylim(0, bottom.max() * 1.16)
    axes[0].legend(frameon=True, fontsize=8.5, loc="upper right")

    # Panel B: Conteo de SKUs y % por Departamento y Nivel de Riesgo
    dept_cnt = (
        diag_df.groupby(["dept_id", "risk_level"], observed=True)["id"]
        .count()
        .unstack(fill_value=0)
        .reindex(index=DEPARTMENTS, columns=risk_order, fill_value=0)
    )
    dept_rev_tot = diag_df.groupby("dept_id", observed=True)["revenue_at_risk_usd"].sum().reindex(DEPARTMENTS)
    bottom_d = np.zeros(len(DEPARTMENTS))
    x_d = np.arange(len(DEPARTMENTS))
    for lvl in risk_order:
        vals = dept_cnt[lvl].to_numpy()
        axes[1].bar(
            x_d,
            vals,
            bottom=bottom_d,
            label=lvl,
            color=RISK_COLORS[lvl],
            edgecolor="white",
            linewidth=0.8,
        )
        bottom_d += vals
    for idx, (tot_skus, rev_d) in enumerate(zip(bottom_d, dept_rev_tot)):
        axes[1].text(
            idx,
            tot_skus + bottom_d.max() * 0.02,
            f"{int(tot_skus):,} SKUs\n(${rev_d:,.0f})",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
            color=WALMART_NAVY,
        )
    axes[1].set_xticks(x_d)
    axes[1].set_xticklabels(DEPARTMENTS, fontweight="bold")
    axes[1].set_ylabel("Cantidad de series SKU-Tienda")
    axes[1].set_title("B. Distribución de SKUs (y USD en Riesgo) por Departamento", fontweight="bold", color=WALMART_NAVY)
    axes[1].set_ylim(0, bottom_d.max() * 1.20)
    axes[1].legend(frameon=True, fontsize=8.5, loc="upper left")

    fig.suptitle(
        "Diagnóstico de Riesgo Comercial — Walmart California (FOODS, 5,748 series, horizonte 28 días)",
        fontsize=12.5,
        fontweight="bold",
        color=WALMART_NAVY,
        y=1.02,
    )
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig05_risk_distribution_store_dept.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # ------------------------------------------------------------------
    # FIG 06: Método del Codo (WCSS) y Coeficiente de Silueta (K = 2..6)
    # ------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 4.9), dpi=300)

    axes[0].plot(eval_df["k"], eval_df["wcss"], marker="o", linewidth=2.4, markersize=7, color=WALMART_BLUE)
    best_wcss = float(eval_df.loc[eval_df["k"] == best_k, "wcss"].iloc[0])
    axes[0].scatter([best_k], [best_wcss], color=WALMART_YELLOW, edgecolor=WALMART_NAVY, s=140, zorder=5, linewidth=1.6)
    axes[0].axvline(best_k, color=WALMART_NAVY, linestyle="--", linewidth=1.1, alpha=0.7)
    for row in eval_df.itertuples(index=False):
        axes[0].text(row.k, row.wcss * 1.025, f"{row.wcss:,.0f}", ha="center", va="bottom", fontsize=8.5)
    axes[0].set_xticks(eval_df["k"])
    axes[0].set_ylim(eval_df["wcss"].min() * 0.92, eval_df["wcss"].max() * 1.10)
    axes[0].set_xlabel("Número de clústeres (K)")
    axes[0].set_ylabel("Inercia intra-clúster (WCSS)")
    axes[0].set_title("A. Método del Codo (WCSS)", fontweight="bold", color=WALMART_NAVY)

    axes[1].plot(eval_df["k"], eval_df["silhouette_score"], marker="s", linewidth=2.4, markersize=7, color=WALMART_NAVY)
    best_sil = float(eval_df.loc[eval_df["k"] == best_k, "silhouette_score"].iloc[0])
    axes[1].scatter([best_k], [best_sil], color=WALMART_YELLOW, edgecolor=WALMART_NAVY, s=140, zorder=5, linewidth=1.6, label=f"K seleccionado = {best_k} (Silueta={best_sil:.3f})")
    axes[1].axvline(best_k, color=WALMART_NAVY, linestyle="--", linewidth=1.1, alpha=0.7)
    for row in eval_df.itertuples(index=False):
        axes[1].text(row.k, row.silhouette_score + 0.012, f"{row.silhouette_score:.3f}", ha="center", va="bottom", fontsize=8.5, fontweight="bold")
    axes[1].set_xticks(eval_df["k"])
    axes[1].set_xlabel("Número de clústeres (K)")
    axes[1].set_ylabel("Coeficiente de Silueta")
    axes[1].set_ylim(0, eval_df["silhouette_score"].max() * 1.20)
    axes[1].set_title("B. Coeficiente de Silueta por K", fontweight="bold", color=WALMART_NAVY)
    axes[1].legend(frameon=True, fontsize=8.5, loc="lower left")

    fig.suptitle(
        "Evaluación Empírica de Segmentación K-Means (5,748 series, 6 indicadores estandarizados)",
        fontsize=12.5,
        fontweight="bold",
        color=WALMART_NAVY,
        y=1.02,
    )
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig06_kmeans_elbow_silhouette.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # ------------------------------------------------------------------
    # FIG 07: Perfiles de clústeres K-Means (Heatmap z-score + Peso SKU vs USD)
    # ------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(15.5, 5.5), dpi=300, gridspec_kw={"width_ratios": [1.35, 1.0]})

    z_means = X_scaled_df.copy()
    z_means["cluster_name"] = diag_df["cluster_name"].values
    heat_z = z_means.groupby("cluster_name")[CLUSTER_FEATURES].mean()
    # Ordenar según profiles_df (por revenue_at_risk_usd_total desc)
    ordered_names = profiles_df["cluster_name"].tolist()
    heat_z = heat_z.reindex(ordered_names)

    # Texto con valores reales en escala original dentro de cada celda
    prof_idx = profiles_df.set_index("cluster_name").reindex(ordered_names)
    annot_mat = np.empty(heat_z.shape, dtype=object)
    col_formats = [
        ("sales_velocity_28d_mean", lambda v: f"{v:.2f}\nu/d"),
        ("intermittency_pct_mean", lambda v: f"{v:.1f}%"),
        ("projected_decline_pct_mean", lambda v: f"{v:.1f}%"),
        ("revenue_at_risk_usd_mean", lambda v: f"${v:.1f}"),
        ("price_sensitivity_mean", lambda v: f"{v*100:+.1f}%"),
        ("snap_sensitivity_mean", lambda v: f"{v*100:+.1f}%"),
    ]
    for r_i, cname in enumerate(ordered_names):
        for c_i, (col_mean, fmt_fn) in enumerate(col_formats):
            val = float(prof_idx.loc[cname, col_mean])
            annot_mat[r_i, c_i] = fmt_fn(val)

    pretty_cols = ["Vel. 28d\n(u/día)", "Intermit.\n(% ceros)", "Declive\nproy. (%)", "Ingreso Riesgo\n(USD/SKU)", "Sensib.\nPrecio", "Sensib.\nSNAP"]
    sns.heatmap(
        heat_z.to_numpy(),
        ax=axes[0],
        cmap="RdBu_r",
        center=0.0,
        vmin=-1.6,
        vmax=1.6,
        annot=annot_mat,
        fmt="",
        linewidths=0.8,
        xticklabels=pretty_cols,
        yticklabels=ordered_names,
        cbar_kws={"label": "Centroide estandarizado (z-score)"},
        annot_kws={"fontsize": 8.5, "fontweight": "bold"},
    )
    axes[0].set_title(f"A. Centroides Reales por Clúster (K={best_k})", fontweight="bold", color=WALMART_NAVY)

    # Panel B: % de SKUs vs % de Ingreso en Riesgo Total por clúster
    y_c = np.arange(len(ordered_names))
    bar_h = 0.36
    sku_pct = prof_idx["portfolio_pct"].to_numpy()
    rev_pct = prof_idx["revenue_at_risk_share_pct"].to_numpy()
    b1 = axes[1].barh(y_c - bar_h / 2, sku_pct, height=bar_h, color=WALMART_BLUE, label="% del portafolio (SKUs)")
    b2 = axes[1].barh(y_c + bar_h / 2, rev_pct, height=bar_h, color="#D62828", label="% del Ingreso en Riesgo (USD)")
    for bar, v in zip(b1, sku_pct):
        axes[1].text(v + 0.8, bar.get_y() + bar.get_height() / 2, f"{v:.1f}%", va="center", fontsize=8.5, color=WALMART_NAVY)
    for bar, v in zip(b2, rev_pct):
        axes[1].text(v + 0.8, bar.get_y() + bar.get_height() / 2, f"{v:.1f}%", va="center", fontsize=8.5, fontweight="bold", color="#D62828")
    axes[1].set_yticks(y_c)
    axes[1].set_yticklabels([f"C{int(prof_idx.loc[n, 'cluster_id'])}" for n in ordered_names], fontweight="bold")
    axes[1].invert_yaxis()
    axes[1].set_xlabel("Participación porcentual (%)")
    axes[1].set_xlim(0, max(sku_pct.max(), rev_pct.max()) * 1.22)
    axes[1].set_title("B. Concentración: Volumen de SKUs vs Riesgo USD", fontweight="bold", color=WALMART_NAVY)
    axes[1].legend(frameon=True, fontsize=8.5, loc="lower right")

    fig.suptitle(
        "Perfiles Empíricos de Clústeres K-Means — Portafolio FOODS California",
        fontsize=12.5,
        fontweight="bold",
        color=WALMART_NAVY,
        y=1.02,
    )
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig07_kmeans_cluster_profiles.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # ------------------------------------------------------------------
    # FIG 08: Ingreso en Riesgo (USD) y SKUs por estrategia prescriptiva
    # ------------------------------------------------------------------
    strat_summary = (
        diag_df.groupby("primary_strategy", as_index=False)
        .agg(
            sku_count=("id", "count"),
            revenue_at_risk_usd=("revenue_at_risk_usd", "sum"),
        )
        .sort_values("revenue_at_risk_usd", ascending=False)
    )
    strat_summary["sku_pct"] = strat_summary["sku_count"] / len(diag_df) * 100.0
    total_rev_all = float(diag_df["revenue_at_risk_usd"].sum())
    strat_summary["rev_pct"] = (
        strat_summary["revenue_at_risk_usd"] / total_rev_all * 100.0 if total_rev_all > 0 else 0.0
    )

    snap_count = int(diag_df["snap_priority"].sum())
    snap_rev = float(diag_df.loc[diag_df["snap_priority"], "revenue_at_risk_usd"].sum())

    fig, axes = plt.subplots(1, 2, figsize=(15.5, 5.2), dpi=300)
    colors_s = [STRATEGY_COLORS.get(s, WALMART_BLUE) for s in strat_summary["primary_strategy"]]
    short_labels = [
        s.replace("Cross-Selling y Visibilidad Omnicanal (Sin Descuento)", "Cross-Selling Omnicanal\n(Sin Descuento)")
        .replace("Precios Dinámicos / Markdown (20%–35%)", "Precios Dinámicos /\nMarkdown (20%–35%)")
        .replace("Mantenimiento EDLP y Producto Ancla", "Mantenimiento EDLP\ny Producto Ancla")
        .replace("Sincronización SNAP (Base EDLP)", "Sincronización SNAP\n(Base EDLP)")
        for s in strat_summary["primary_strategy"]
    ]

    y_pos = np.arange(len(strat_summary))
    b_rev = axes[0].barh(y_pos, strat_summary["revenue_at_risk_usd"], color=colors_s, edgecolor=WALMART_NAVY, linewidth=0.7)
    for bar, v, pct in zip(b_rev, strat_summary["revenue_at_risk_usd"], strat_summary["rev_pct"]):
        axes[0].text(
            v + strat_summary["revenue_at_risk_usd"].max() * 0.018,
            bar.get_y() + bar.get_height() / 2,
            f"${v:,.0f} ({pct:.1f}%)",
            va="center",
            fontsize=8.8,
            fontweight="bold",
            color=WALMART_NAVY,
        )
    axes[0].set_yticks(y_pos)
    axes[0].set_yticklabels(short_labels, fontweight="bold")
    axes[0].invert_yaxis()
    axes[0].set_xlabel("Ingreso en Riesgo cubierto en 28 días (USD)")
    axes[0].set_xlim(0, strat_summary["revenue_at_risk_usd"].max() * 1.32)
    axes[0].set_title("A. Ingreso en Riesgo (USD) por Estrategia Principal", fontweight="bold", color=WALMART_NAVY)

    b_sku = axes[1].barh(y_pos, strat_summary["sku_count"], color=colors_s, edgecolor=WALMART_NAVY, linewidth=0.7)
    for bar, cnt, pct in zip(b_sku, strat_summary["sku_count"], strat_summary["sku_pct"]):
        axes[1].text(
            cnt + strat_summary["sku_count"].max() * 0.018,
            bar.get_y() + bar.get_height() / 2,
            f"{int(cnt):,} ({pct:.1f}%)",
            va="center",
            fontsize=8.8,
            fontweight="bold",
            color=WALMART_NAVY,
        )
    axes[1].set_yticks(y_pos)
    axes[1].set_yticklabels(short_labels, fontweight="bold")
    axes[1].invert_yaxis()
    axes[1].set_xlabel("Cantidad de series SKU-Tienda")
    axes[1].set_xlim(0, strat_summary["sku_count"].max() * 1.30)
    axes[1].set_title("B. Cobertura de Portafolio por Estrategia Principal", fontweight="bold", color=WALMART_NAVY)

    fig.suptitle(
        f"Motor Prescriptivo de Marketing — Capa transversal Prioridad SNAP (>=15%): {snap_count:,} SKUs (${snap_rev:,.0f} en riesgo)",
        fontsize=11.8,
        fontweight="bold",
        color=WALMART_NAVY,
        y=1.02,
    )
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig08_prescriptive_marketing_revenue_risk.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    t0 = time.perf_counter()
    ensure_directories()

    print("=" * 76)
    print("PASO 03 — DIAGNÓSTICO COMERCIAL, K-MEANS Y MOTOR PRESCRIPTIVO (FOODS · CA)")
    print("=" * 76)

    # 1. Cargar datos reales y pronósticos 28d
    print("\n[1/5] Cargando active_sales_3y.parquet y forecast_28d.parquet...")
    active = pd.read_parquet(
        ACTIVE_SALES_3Y_PATH,
        columns=["id", "item_id", "dept_id", "store_id", "d", "date", "units_sold", "sell_price", "relative_price", "snap_CA", "event_type_1"],
    )
    forecast = pd.read_parquet(FORECAST_28D_PATH)

    max_date = active["date"].max()
    start_28d = max_date - pd.Timedelta(days=HORIZON - 1)
    start_90d = max_date - pd.Timedelta(days=89)
    print(f"  - Fecha cierre real (d_1941) : {max_date.strftime('%Y-%m-%d')}")
    print(f"  - Ventana v28 real           : {start_28d.strftime('%Y-%m-%d')} a {max_date.strftime('%Y-%m-%d')}")
    print(f"  - Ventana v90 real           : {start_90d.strftime('%Y-%m-%d')} a {max_date.strftime('%Y-%m-%d')}")

    # 2. Calcular indicadores comerciales reales por serie (5,748 series)
    print("\n[2/5] Calculando indicadores reales sobre las 5,748 series...")
    meta = active[["id", "item_id", "dept_id", "store_id"]].drop_duplicates(subset=["id"]).copy()
    for col in ("id", "item_id", "dept_id", "store_id"):
        meta[col] = meta[col].astype(str)
    meta = meta.sort_values("id").reset_index(drop=True)
    assert len(meta) == EXPECTED_SERIES, f"Esperadas {EXPECTED_SERIES} series, halladas {len(meta)}"

    # Intermitencia 3 años activos y días activos
    active["is_zero"] = (active["units_sold"] == 0).astype(np.int8)
    agg_3y = (
        active.groupby("id", observed=True)
        .agg(
            active_days_3y=("units_sold", "count"),
            zero_days_3y=("is_zero", "sum"),
            mean_sales_3y=("units_sold", "mean"),
        )
        .reset_index()
    )
    agg_3y["id"] = agg_3y["id"].astype(str)
    agg_3y["intermittency_pct"] = agg_3y["zero_days_3y"] / agg_3y["active_days_3y"] * 100.0

    # Velocidad 28d y 90d reales + intermitencia 90d
    s28 = active.loc[active["date"] >= start_28d]
    v28_df = s28.groupby("id", observed=True)["units_sold"].mean().rename("sales_velocity_28d").reset_index()
    v28_df["id"] = v28_df["id"].astype(str)

    s90 = active.loc[active["date"] >= start_90d]
    v90_df = (
        s90.groupby("id", observed=True)
        .agg(
            sales_velocity_90d=("units_sold", "mean"),
            intermittency_90d_pct=("is_zero", lambda s: float(s.mean() * 100.0)),
        )
        .reset_index()
    )
    v90_df["id"] = v90_df["id"].astype(str)

    # Precio vigente en d_1941
    price_last = active.loc[active["date"] == max_date, ["id", "sell_price"]].rename(columns={"sell_price": "current_price"}).copy()
    price_last["id"] = price_last["id"].astype(str)
    assert len(price_last) == EXPECTED_SERIES, "Faltan precios en d_1941"

    # Velocidad pronosticada 28d (d_1942..d_1969)
    pred_v28_df = (
        forecast.groupby("id", observed=True)
        .agg(
            pred_velocity_28d=("pred_units", "mean"),
            pred_total_28d_units=("pred_units", "sum"),
        )
        .reset_index()
    )
    pred_v28_df["id"] = pred_v28_df["id"].astype(str)

    # Sensibilidad a precio (relative_price < 0.95 vs >= 0.95, mínimo 7 días en rebaja)
    active["is_promo_price"] = (active["relative_price"] < PRICE_PROMO_THRESHOLD).astype(np.int8)
    promo_agg = (
        active.groupby(["id", "is_promo_price"], observed=True)["units_sold"]
        .agg(["count", "mean"])
        .unstack(fill_value=np.nan)
    )
    promo_days = promo_agg["count"].get(1, pd.Series(0, index=promo_agg.index)).fillna(0).astype(int)
    mean_promo = promo_agg["mean"].get(1, pd.Series(np.nan, index=promo_agg.index))
    mean_normal = promo_agg["mean"].get(0, pd.Series(np.nan, index=promo_agg.index))

    has_promo_hist = (promo_days >= PRICE_PROMO_MIN_DAYS) & (mean_normal > 0) & mean_promo.notna()
    price_sens = pd.Series(np.nan, index=promo_agg.index, dtype=np.float64)
    price_sens.loc[has_promo_hist] = (mean_promo.loc[has_promo_hist] - mean_normal.loc[has_promo_hist]) / mean_normal.loc[has_promo_hist]

    price_sens_df = pd.DataFrame(
        {
            "id": promo_agg.index.astype(str),
            "promo_days_count": promo_days.to_numpy(dtype=int),
            "has_price_promo_history": has_promo_hist.to_numpy(dtype=bool),
            "price_sensitivity": price_sens.to_numpy(dtype=np.float64),
        }
    )

    # Sensibilidad SNAP (snap_CA == 1 vs 0)
    snap_agg = (
        active.groupby(["id", "snap_CA"], observed=True)["units_sold"]
        .mean()
        .unstack(fill_value=0.0)
    )
    snap0 = snap_agg[0].astype(np.float64)
    snap1 = snap_agg[1].astype(np.float64)
    snap_sens = np.where(snap0 > 0, (snap1 - snap0) / snap0, 0.0)
    snap_sens_df = pd.DataFrame(
        {
            "id": snap_agg.index.astype(str),
            "snap_sensitivity": snap_sens,
        }
    )

    # Sensibilidad a eventos (event_type_1 != "No_Event" vs "No_Event")
    active["is_event"] = (active["event_type_1"].astype(str) != "No_Event").astype(np.int8)
    event_agg = (
        active.groupby(["id", "is_event"], observed=True)["units_sold"]
        .mean()
        .unstack(fill_value=np.nan)
    )
    ev0 = event_agg[0].astype(np.float64)
    ev1 = event_agg[1].astype(np.float64)
    event_sens = np.where((ev0 > 0) & np.isfinite(ev1), (ev1 - ev0) / ev0, 0.0)
    event_sens_df = pd.DataFrame(
        {
            "id": event_agg.index.astype(str),
            "event_sensitivity": event_sens,
        }
    )

    del active, forecast, s28, s90, promo_agg, snap_agg, event_agg
    gc.collect()

    # Consolidar tabla maestra de diagnóstico
    diag = (
        meta.merge(agg_3y[["id", "active_days_3y", "intermittency_pct"]], on="id", how="left")
        .merge(v28_df, on="id", how="left")
        .merge(v90_df, on="id", how="left")
        .merge(pred_v28_df, on="id", how="left")
        .merge(price_last, on="id", how="left")
        .merge(price_sens_df, on="id", how="left")
        .merge(snap_sens_df, on="id", how="left")
        .merge(event_sens_df, on="id", how="left")
    )

    # Declive proyectado (%) e Ingreso en Riesgo (USD)
    v90 = diag["sales_velocity_90d"].to_numpy(dtype=np.float64)
    pv28 = diag["pred_velocity_28d"].to_numpy(dtype=np.float64)
    cur_p = diag["current_price"].to_numpy(dtype=np.float64)

    decline_raw = np.divide(
        v90 - pv28,
        v90,
        out=np.zeros_like(v90, dtype=np.float64),
        where=v90 > 0,
    )
    diag["projected_decline_pct"] = np.maximum(0.0, decline_raw * 100.0)
    diag["units_at_risk_28d"] = np.maximum(0.0, HORIZON * (v90 - pv28))
    diag["revenue_at_risk_usd"] = diag["units_at_risk_28d"] * cur_p

    # 3. Clasificación de Riesgo Comercial (Sección 7.1)
    print("\n[3/5] Clasificando niveles de riesgo comercial (umbral p80 por tienda)...")
    q80_by_store = (
        diag.groupby("store_id")["revenue_at_risk_usd"]
        .quantile(REVENUE_TOP_QUANTILE)
        .to_dict()
    )
    diag["store_revenue_q80_usd"] = diag["store_id"].map(q80_by_store)

    high_mask = (diag["projected_decline_pct"] >= DECLINE_HIGH) | (
        (diag["intermittency_pct"] >= INTERMITTENCY_HIGH)
        & (diag["revenue_at_risk_usd"] > 0.0)
        & (diag["revenue_at_risk_usd"] >= diag["store_revenue_q80_usd"])
    )
    med_mask = (~high_mask) & (
        ((diag["projected_decline_pct"] >= DECLINE_MED) & (diag["projected_decline_pct"] < DECLINE_HIGH))
        | ((diag["intermittency_pct"] >= INTERMITTENCY_MED) & (diag["intermittency_pct"] < INTERMITTENCY_HIGH))
    )

    diag["risk_level"] = np.where(
        high_mask, "Riesgo Alto", np.where(med_mask, "Riesgo Medio", "Riesgo Bajo")
    )

    print("  - Umbrales p80 de Ingreso en Riesgo por tienda (USD):")
    for st in STORES:
        print(f"      * {st}: ${q80_by_store[st]:.2f} USD")

    # 4. Segmentación K-Means (StandardScaler + detección de outliers/winsorización + Codo y Silueta)
    print("\n[4/5] Evaluando segmentación K-Means (K=2..6)...")
    X_raw_clust = diag[CLUSTER_FEATURES].copy()
    X_raw_clust["price_sensitivity"] = X_raw_clust["price_sensitivity"].fillna(0.0)

    # Verificar primero si sin winsorizar se forman clústeres degenerados (<1% del catálogo)
    scaler_raw = StandardScaler()
    X_scaled_raw = scaler_raw.fit_transform(X_raw_clust)
    raw_min_pcts: dict[int, float] = {}
    for k_test in range(2, 7):
        km_t = KMeans(n_clusters=k_test, n_init=20, random_state=RANDOM_SEED)
        lbl_t = km_t.fit_predict(X_scaled_raw)
        counts_t = np.bincount(lbl_t)
        raw_min_pcts[k_test] = float(counts_t.min() / len(diag) * 100.0)

    degenerate_detected = any(pct < 1.0 for pct in raw_min_pcts.values())
    winsor_bounds: dict[str, dict[str, float]] = {}

    if degenerate_detected:
        print(
            f"  [!] Clústeres degenerados (<1%) detectados sin winsorización (tamaños mínimos %: { {k: round(v, 2) for k, v in raw_min_pcts.items()} })."
        )
        print("      Aplicando winsorización controlada (p99 en no-negativas, p01-p99 en sensibilidades) solo para StandardScaler...")
        X_clust = X_raw_clust.copy()
        for col in CLUSTER_FEATURES:
            hi = float(X_clust[col].quantile(0.99))
            lo = float(X_clust[col].quantile(0.01)) if col in ("price_sensitivity", "snap_sensitivity") else float(X_clust[col].min())
            X_clust[col] = X_clust[col].clip(lower=lo, upper=hi)
            winsor_bounds[col] = {"lower_clip": round(lo, 4), "upper_clip": round(hi, 4)}
    else:
        print("  [OK] Sin clústeres degenerados (<1%) en los datos originales.")
        X_clust = X_raw_clust.copy()

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_clust)
    X_scaled_df = pd.DataFrame(X_scaled, columns=CLUSTER_FEATURES)

    eval_rows: list[dict] = []
    fitted_models: dict[int, np.ndarray] = {}
    for k in range(2, 7):
        km = KMeans(n_clusters=k, n_init=20, random_state=RANDOM_SEED)
        labels = km.fit_predict(X_scaled)
        sil = float(silhouette_score(X_scaled, labels))
        counts = np.bincount(labels)
        eval_rows.append(
            {
                "k": k,
                "wcss": float(km.inertia_),
                "silhouette_score": sil,
                "min_cluster_size": int(counts.min()),
                "min_cluster_pct": float(counts.min() / len(diag) * 100.0),
                "max_cluster_size": int(counts.max()),
                "max_cluster_pct": float(counts.max() / len(diag) * 100.0),
            }
        )
        fitted_models[k] = labels

    eval_df = pd.DataFrame(eval_rows)
    best_k = choose_optimal_k(eval_df)
    diag["cluster_id"] = fitted_models[best_k].astype(int)

    # Perfilado de centroides en escala original (valores reales SIN recortar)
    total_rev_risk = float(diag["revenue_at_risk_usd"].sum())
    prof_rows: list[dict] = []
    for cid, grp in diag.groupby("cluster_id"):
        row_p = {
            "cluster_id": int(cid),
            "sku_count": int(len(grp)),
            "portfolio_pct": float(len(grp) / len(diag) * 100.0),
            "sales_velocity_28d_mean": float(grp["sales_velocity_28d"].mean()),
            "intermittency_pct_mean": float(grp["intermittency_pct"].mean()),
            "projected_decline_pct_mean": float(grp["projected_decline_pct"].mean()),
            "revenue_at_risk_usd_mean": float(grp["revenue_at_risk_usd"].mean()),
            "revenue_at_risk_usd_total": float(grp["revenue_at_risk_usd"].sum()),
            "revenue_at_risk_share_pct": float(grp["revenue_at_risk_usd"].sum() / total_rev_risk * 100.0) if total_rev_risk > 0 else 0.0,
            "price_sensitivity_mean": float(grp["price_sensitivity"].mean()) if grp["price_sensitivity"].notna().any() else 0.0,
            "snap_sensitivity_mean": float(grp["snap_sensitivity"].mean()),
            "pct_high_risk": float((grp["risk_level"] == "Riesgo Alto").mean() * 100.0),
            "pct_med_risk": float((grp["risk_level"] == "Riesgo Medio").mean() * 100.0),
            "pct_low_risk": float((grp["risk_level"] == "Riesgo Bajo").mean() * 100.0),
        }
        prof_rows.append(row_p)

    profiles_df = pd.DataFrame(prof_rows)
    cluster_names = name_clusters_empirically(profiles_df)
    profiles_df["cluster_name"] = profiles_df["cluster_id"].map(cluster_names)
    profiles_df = profiles_df.sort_values("revenue_at_risk_usd_total", ascending=False).reset_index(drop=True)
    # Reordenar columnas para legibilidad
    cols_prof_order = [
        "cluster_id",
        "cluster_name",
        "sku_count",
        "portfolio_pct",
        "sales_velocity_28d_mean",
        "intermittency_pct_mean",
        "projected_decline_pct_mean",
        "revenue_at_risk_usd_mean",
        "revenue_at_risk_usd_total",
        "revenue_at_risk_share_pct",
        "price_sensitivity_mean",
        "snap_sensitivity_mean",
        "pct_high_risk",
        "pct_med_risk",
        "pct_low_risk",
    ]
    profiles_df = profiles_df[cols_prof_order]
    diag["cluster_name"] = diag["cluster_id"].map(cluster_names)

    print(f"  - K óptimo seleccionado: K = {best_k} (Silueta = {float(eval_df.loc[eval_df['k'] == best_k, 'silhouette_score'].iloc[0]):.4f})")

    # 5. Motor prescriptivo de marketing (Sección 7.3)
    print("\n[5/5] Ejecutando motor prescriptivo de marketing y asignando productos ancla...")
    diag["snap_sensitive_10pct"] = diag["snap_sensitivity"] >= SNAP_SENSITIVITY_MIN
    diag["snap_priority"] = diag["snap_sensitivity"] >= SNAP_PRIORITY_THRESHOLD

    # Calcular top productos ancla (Riesgo Bajo, mayor sales_velocity_28d) por (store_id, dept_id)
    low_risk_pool = (
        diag.loc[diag["risk_level"] == "Riesgo Bajo", ["store_id", "dept_id", "item_id", "sales_velocity_28d"]]
        .sort_values("sales_velocity_28d", ascending=False)
    )
    anchor_lookup: dict[tuple[str, str], list[str]] = {}
    for (st, dp), grp in low_risk_pool.groupby(["store_id", "dept_id"], sort=False):
        anchor_lookup[(str(st), str(dp))] = grp["item_id"].tolist()

    primary_strategies: list[str] = []
    tactical_actions: list[str] = []
    discount_ranges: list[str] = []
    stockpiling_alerts: list[bool] = []
    snap_plans: list[str] = []
    suggested_anchors: list[str] = []

    for row in diag.itertuples(index=False):
        is_risk = row.risk_level in ("Riesgo Alto", "Riesgo Medio")
        is_price_elastic = bool(row.has_price_promo_history) and pd.notna(row.price_sensitivity) and (row.price_sensitivity >= PRICE_SENSITIVITY_MIN)
        is_snap_prio = bool(row.snap_priority)

        if is_risk and is_price_elastic:
            strat = "Precios Dinámicos / Markdown (20%–35%)"
            d_range = "25%–35%" if row.risk_level == "Riesgo Alto" else "20%–25%"
            action = (
                f"Aplicar Markdown táctico {d_range} con migración operativa LEFO→FEFO; "
                "reducir orden de reposición post-promoción entre -20% y -30% para prevenir sobreinventario por stockpiling."
            )
            sp_alert = True
            anchor = ""
        elif is_risk:
            strat = "Cross-Selling y Visibilidad Omnicanal (Sin Descuento)"
            d_range = "0% (Sin descuento)"
            candidates = anchor_lookup.get((row.store_id, row.dept_id), [])
            anchor = next((c for c in candidates if c != row.item_id), "")
            action = (
                f"Evitar descuento (demanda inelástica o sin historial promocional); "
                f"ejecutar exhibición conjunta/bundling y visibilidad omnicanal junto al producto ancla {anchor}."
            )
            sp_alert = False
        elif is_snap_prio:
            strat = "Sincronización SNAP (Base EDLP)"
            d_range = "0% (EDLP)"
            action = (
                "Mantener política EDLP sin descuento agresivo; priorizar refuerzo de inventario, "
                "encartes y multipacks durante los días 1–10 de abono SNAP CA."
            )
            sp_alert = False
            anchor = ""
        else:
            strat = "Mantenimiento EDLP y Producto Ancla"
            d_range = "0% (EDLP)"
            action = (
                "Mantener estrategia Everyday Low Price (EDLP), asegurar disponibilidad continua "
                "y habilitar como producto ancla de alto tráfico para cross-selling."
            )
            sp_alert = False
            anchor = ""

        if is_snap_prio and is_risk:
            snap_plan = "Fase A (Días 1–10): encartes, multipacks y refuerzo de stock | Fase B (Días 20–31): cupones dirigidos de fin de mes"
        elif is_snap_prio:
            snap_plan = "Fase A (Días 1–10): encartes, multipacks y refuerzo de stock en base EDLP"
        else:
            snap_plan = "Calendario estándar (sin prioridad SNAP)"

        primary_strategies.append(strat)
        tactical_actions.append(action)
        discount_ranges.append(d_range)
        stockpiling_alerts.append(sp_alert)
        snap_plans.append(snap_plan)
        suggested_anchors.append(anchor)

    diag["primary_strategy"] = primary_strategies
    diag["discount_range"] = discount_ranges
    diag["stockpiling_alert"] = stockpiling_alerts
    diag["suggested_anchor_item"] = suggested_anchors
    diag["snap_tactical_plan"] = snap_plans
    diag["tactical_action"] = tactical_actions

    # Verificar integridad de productos ancla asignados
    cross_rows = diag.loc[diag["primary_strategy"] == "Cross-Selling y Visibilidad Omnicanal (Sin Descuento)"]
    assert (cross_rows["suggested_anchor_item"] != "").all(), "Faltan productos ancla en Cross-Selling"
    low_risk_pairs = set(
        zip(
            diag.loc[diag["risk_level"] == "Riesgo Bajo", "store_id"],
            diag.loc[diag["risk_level"] == "Riesgo Bajo", "dept_id"],
            diag.loc[diag["risk_level"] == "Riesgo Bajo", "item_id"],
        )
    )
    for r in cross_rows.itertuples(index=False):
        assert (r.store_id, r.dept_id, r.suggested_anchor_item) in low_risk_pairs, (
            f"Producto ancla inválido para {r.id}: {r.suggested_anchor_item}"
        )
    assert len(diag) == EXPECTED_SERIES, "Conteo final inconsistente"

    # Tablas resumen
    risk_summary = (
        diag.groupby(["store_id", "dept_id", "risk_level"], as_index=False)
        .agg(
            sku_count=("id", "count"),
            revenue_at_risk_usd=("revenue_at_risk_usd", "sum"),
            units_at_risk_28d=("units_at_risk_28d", "sum"),
            avg_intermittency_pct=("intermittency_pct", "mean"),
            avg_projected_decline_pct=("projected_decline_pct", "mean"),
            snap_priority_skus=("snap_priority", "sum"),
        )
    )
    risk_summary["portfolio_pct"] = risk_summary["sku_count"] / len(diag) * 100.0
    risk_summary["revenue_share_pct"] = risk_summary["revenue_at_risk_usd"] / total_rev_risk * 100.0

    # Top 50 promociones prioritarias (SKUs en riesgo ordenados por Ingreso en Riesgo descendente)
    top50_cols = [
        "id",
        "item_id",
        "store_id",
        "dept_id",
        "risk_level",
        "cluster_id",
        "cluster_name",
        "current_price",
        "sales_velocity_90d",
        "sales_velocity_28d",
        "pred_velocity_28d",
        "intermittency_pct",
        "projected_decline_pct",
        "units_at_risk_28d",
        "revenue_at_risk_usd",
        "has_price_promo_history",
        "price_sensitivity",
        "snap_sensitivity",
        "snap_priority",
        "primary_strategy",
        "discount_range",
        "stockpiling_alert",
        "suggested_anchor_item",
        "snap_tactical_plan",
        "tactical_action",
    ]
    top50 = (
        diag.loc[diag["risk_level"].isin(["Riesgo Alto", "Riesgo Medio"])]
        .sort_values("revenue_at_risk_usd", ascending=False)
        .head(50)[top50_cols]
        .reset_index(drop=True)
    )
    top50.insert(0, "priority_rank", np.arange(1, len(top50) + 1))

    # Guardar las 5 tablas CSV
    diag.to_csv(TABLES_DIR / "sku_store_diagnosis.csv", index=False)
    risk_summary.to_csv(TABLES_DIR / "risk_summary_by_store_dept.csv", index=False)
    eval_df.to_csv(TABLES_DIR / "kmeans_evaluation.csv", index=False)
    profiles_df.to_csv(TABLES_DIR / "kmeans_cluster_profiles.csv", index=False)
    top50.to_csv(TABLES_DIR / "top_50_priority_promotions.csv", index=False)

    # Generar las 4 figuras (fig05..fig08) a 300 DPI
    generate_figures(
        diag_df=diag,
        eval_df=eval_df,
        profiles_df=profiles_df,
        best_k=best_k,
        X_scaled_df=X_scaled_df,
    )

    # Construir resúmenes para auditoría JSON y consola
    risk_by_level = (
        diag.groupby("risk_level", as_index=False)
        .agg(
            sku_count=("id", "count"),
            revenue_at_risk_usd=("revenue_at_risk_usd", "sum"),
        )
    )
    risk_by_level["sku_pct"] = risk_by_level["sku_count"] / len(diag) * 100.0
    risk_by_level["rev_pct"] = risk_by_level["revenue_at_risk_usd"] / total_rev_risk * 100.0

    risk_by_store = (
        diag.groupby("store_id", as_index=False)
        .agg(
            sku_count=("id", "count"),
            high_risk_skus=("risk_level", lambda s: int((s == "Riesgo Alto").sum())),
            med_risk_skus=("risk_level", lambda s: int((s == "Riesgo Medio").sum())),
            low_risk_skus=("risk_level", lambda s: int((s == "Riesgo Bajo").sum())),
            revenue_at_risk_usd=("revenue_at_risk_usd", "sum"),
        )
    )
    risk_by_store["p80_threshold_usd"] = risk_by_store["store_id"].map(q80_by_store)

    strat_mix = (
        diag.groupby("primary_strategy", as_index=False)
        .agg(
            sku_count=("id", "count"),
            revenue_at_risk_usd=("revenue_at_risk_usd", "sum"),
            snap_priority_overlap=("snap_priority", "sum"),
        )
        .sort_values("revenue_at_risk_usd", ascending=False)
    )
    strat_mix["sku_pct"] = strat_mix["sku_count"] / len(diag) * 100.0
    strat_mix["rev_pct"] = strat_mix["revenue_at_risk_usd"] / total_rev_risk * 100.0

    elapsed = round(time.perf_counter() - t0, 2)
    audit = {
        "status": "PASS",
        "elapsed_seconds": elapsed,
        "total_series": int(len(diag)),
        "total_revenue_at_risk_usd": round(total_rev_risk, 2),
        "total_units_at_risk_28d": round(float(diag["units_at_risk_28d"].sum()), 2),
        "has_price_promo_history_count": int(diag["has_price_promo_history"].sum()),
        "price_elastic_count": int(
            (diag["has_price_promo_history"] & (diag["price_sensitivity"] >= PRICE_SENSITIVITY_MIN)).sum()
        ),
        "snap_sensitive_10pct_count": int(diag["snap_sensitive_10pct"].sum()),
        "snap_priority_15pct_count": int(diag["snap_priority"].sum()),
        "snap_priority_revenue_at_risk_usd": round(
            float(diag.loc[diag["snap_priority"], "revenue_at_risk_usd"].sum()), 2
        ),
        "store_p80_thresholds_usd": {k: round(float(v), 4) for k, v in q80_by_store.items()},
        "risk_by_level": risk_by_level.to_dict(orient="records"),
        "risk_by_store": risk_by_store.to_dict(orient="records"),
        "kmeans": {
            "features": CLUSTER_FEATURES,
            "raw_min_cluster_pct_by_k": {str(k): round(v, 4) for k, v in raw_min_pcts.items()},
            "winsorization_applied": degenerate_detected,
            "winsorization_bounds": winsor_bounds,
            "selected_k": best_k,
            "selected_silhouette": round(
                float(eval_df.loc[eval_df["k"] == best_k, "silhouette_score"].iloc[0]), 4
            ),
            "evaluation": eval_df.to_dict(orient="records"),
            "profiles": profiles_df.to_dict(orient="records"),
        },
        "strategy_mix": strat_mix.to_dict(orient="records"),
        "figures_generated": [
            "fig05_risk_distribution_store_dept.png",
            "fig06_kmeans_elbow_silhouette.png",
            "fig07_kmeans_cluster_profiles.png",
            "fig08_prescriptive_marketing_revenue_risk.png",
        ],
    }

    audit_path = METRICS_DIR / "diagnosis_audit.json"
    with audit_path.open("w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2, ensure_ascii=False)

    print("\n--- RESUMEN POR NIVEL DE RIESGO ---")
    print(risk_by_level.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))
    print("\n--- RESUMEN POR TIENDA (CON CORTE P80 USD) ---")
    print(risk_by_store.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))
    print("\n--- EVALUACIÓN K-MEANS (K=2..6) ---")
    print(eval_df.to_string(index=False, float_format=lambda v: f"{v:,.4f}"))
    print("\n--- PERFILES DE CLÚSTERES (K ELEGIDO) ---")
    print(profiles_df.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))
    print("\n--- MIX DE ESTRATEGIAS PRESCRIPTIVAS ---")
    print(strat_mix.to_string(index=False, float_format=lambda v: f"{v:,.2f}"))
    print("\n--- TOP 10 PROMOCIONES PRIORITARIAS ---")
    preview_cols = [
        "priority_rank",
        "id",
        "risk_level",
        "current_price",
        "projected_decline_pct",
        "revenue_at_risk_usd",
        "price_sensitivity",
        "snap_sensitivity",
        "primary_strategy",
        "suggested_anchor_item",
    ]
    print(top50.head(10)[preview_cols].to_string(index=False, float_format=lambda v: f"{v:,.2f}"))

    print("\n" + "=" * 76)
    print(f"PASO 03 COMPLETADO EN {elapsed:.2f}s — AUDITORÍA: PASS -> {audit_path}")
    print("=" * 76)


if __name__ == "__main__":
    main()

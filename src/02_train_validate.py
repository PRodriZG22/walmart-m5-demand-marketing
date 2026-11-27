"""Paso 02: Validación temporal rodante (4x28d), baselines sin fuga y Random Forest (FOODS · CA)."""

from __future__ import annotations

import argparse
import ctypes
import gc
import json
import sys
import time
from ctypes import wintypes
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.ensemble import RandomForestRegressor

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (  # noqa: E402
    ACTIVE_SALES_3Y_PATH,
    DEPARTMENTS,
    EXPECTED_SERIES,
    FEATURE_COLS,
    FEATURES_3Y_PATH,
    FIGURES_DIR,
    FORECAST_28D_PATH,
    FUTURE_28D_FEATURES_PATH,
    HORIZON,
    METRICS_DIR,
    NUM_ROLLING_WINDOWS,
    RANDOM_SEED,
    RF_PARAMS,
    STORES,
    TABLES_DIR,
    VAL_WINDOW4_PRED_PATH,
    ensure_directories,
)

# Paleta corporativa Walmart
WALMART_BLUE = "#0071CE"
WALMART_YELLOW = "#FFC220"
WALMART_NAVY = "#041E42"
COLOR_TEAL = "#2A9D8F"
COLOR_ORANGE = "#F77F00"
COLOR_RED = "#D62828"
COLOR_GRAY = "#6C757D"

SES_ALPHA_GRID = (0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50)

MODEL_ORDER = ["Random Forest", "SES (NumPy)", "MA28", "Seasonal Naïve (lag_28)"]


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def get_memory_mb() -> tuple[float, float]:
    """Devuelve (RSS actual MB, Peak Working Set MB) del proceso actual en Windows."""
    try:
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        kernel32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        handle = kernel32.GetCurrentProcess()
        ok = psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
        if ok:
            rss_mb = counters.WorkingSetSize / (1024 * 1024)
            peak_mb = counters.PeakWorkingSetSize / (1024 * 1024)
            return round(rss_mb, 1), round(peak_mb, 1)
    except Exception:
        pass
    return -1.0, -1.0


def build_sales_matrix(
    active_df: pd.DataFrame,
    series_ids: list[str],
    all_dates: pd.DatetimeIndex,
) -> np.ndarray:
    """Construye matriz densa (N_series, T_dates) en float32 con NaN antes del lanzamiento."""
    n_series = len(series_ids)
    n_dates = len(all_dates)
    id_to_row = {sid: i for i, sid in enumerate(series_ids)}
    date_to_col = {dt: j for j, dt in enumerate(all_dates)}

    row_idx = active_df["id"].astype(str).map(id_to_row).to_numpy(dtype=np.int32)
    col_idx = active_df["date"].map(date_to_col).to_numpy(dtype=np.int32)
    vals = active_df["units_sold"].to_numpy(dtype=np.float32)

    mat = np.full((n_series, n_dates), np.nan, dtype=np.float32)
    mat[row_idx, col_idx] = vals
    return mat


def compute_rmsse_scales(y_train_mat: np.ndarray) -> np.ndarray:
    """Calcula el denominador oficial M5 por serie usando historial activo estrictamente <= t_cut."""
    n_series = y_train_mat.shape[0]
    scales = np.zeros(n_series, dtype=np.float64)
    for i in range(n_series):
        row = y_train_mat[i]
        active = row[~np.isnan(row)]
        if active.size < 2:
            continue
        nz = np.flatnonzero(active > 0)
        if nz.size == 0:
            continue
        eff = active[nz[0] :].astype(np.float64)
        if eff.size < 2:
            continue
        diffs = np.diff(eff)
        scales[i] = float(np.mean(diffs * diffs))
    return scales


def fit_predict_ses_vectorized(
    y_train_mat: np.ndarray,
    alpha_grid: tuple[float, ...] = SES_ALPHA_GRID,
) -> tuple[np.ndarray, np.ndarray]:
    """SES vectorizado en NumPy con optimización de alpha estrictamente en entrenamiento <= t_cut."""
    n_series, n_steps = y_train_mat.shape
    best_sse = np.full(n_series, np.inf, dtype=np.float64)
    best_level = np.zeros(n_series, dtype=np.float64)
    best_alpha = np.full(n_series, alpha_grid[0], dtype=np.float64)

    for alpha in alpha_grid:
        level = np.full(n_series, np.nan, dtype=np.float64)
        sse = np.zeros(n_series, dtype=np.float64)
        cnt = np.zeros(n_series, dtype=np.int32)
        one_minus = 1.0 - alpha

        for t in range(n_steps):
            y_t = y_train_mat[:, t].astype(np.float64)
            valid = ~np.isnan(y_t)
            if not np.any(valid):
                continue
            has_lvl = ~np.isnan(level)
            upd = valid & has_lvl
            if np.any(upd):
                err = y_t[upd] - level[upd]
                sse[upd] += err * err
                cnt[upd] += 1
                level[upd] = alpha * y_t[upd] + one_minus * level[upd]
            init = valid & (~has_lvl)
            if np.any(init):
                level[init] = y_t[init]

        mse = np.where(cnt > 0, sse / np.maximum(cnt, 1), np.inf)
        level_clean = np.where(np.isnan(level), 0.0, level)
        improved = mse < best_sse
        best_sse = np.where(improved, mse, best_sse)
        best_level = np.where(improved, level_clean, best_level)
        best_alpha = np.where(improved, alpha, best_alpha)

    return np.clip(best_level, 0.0, None).astype(np.float32), best_alpha


def compute_ma28_origin(y_train_mat: np.ndarray) -> np.ndarray:
    """MA28 con origen fijo en t_cut: media de los últimos 28 días reales <= t_cut."""
    tail28 = y_train_mat[:, -HORIZON:]
    with np.errstate(all="ignore"):
        ma28 = np.nanmean(tail28, axis=1)
    ma28 = np.where(np.isnan(ma28), 0.0, ma28)
    return np.clip(ma28, 0.0, None).astype(np.float32)


def compute_metrics_for_predictions(
    df_eval: pd.DataFrame,
    pred_col: str,
    scale_map: dict[str, float],
) -> dict[str, float | int]:
    """Calcula MAE, RMSE y RMSSE oficial M5 (excluyendo series con scale == 0)."""
    y_true = df_eval["units_sold"].to_numpy(dtype=np.float64)
    y_pred = df_eval[pred_col].to_numpy(dtype=np.float64)
    diff = y_true - y_pred
    mae = float(np.mean(np.abs(diff)))
    rmse = float(np.sqrt(np.mean(diff * diff)))

    # RMSSE por serie
    sq_err_series = (
        pd.DataFrame({"id": df_eval["id"].astype(str), "sq_err": diff * diff})
        .groupby("id", sort=False)["sq_err"]
        .mean()
    )
    scales = sq_err_series.index.map(scale_map).to_numpy(dtype=np.float64)
    valid_mask = scales > 0.0
    excluded = int(np.sum(~valid_mask))
    rmsse_vals = np.sqrt(sq_err_series.to_numpy(dtype=np.float64)[valid_mask] / scales[valid_mask])
    rmsse = float(np.mean(rmsse_vals)) if rmsse_vals.size > 0 else float("nan")

    return {
        "mae": mae,
        "rmse": rmse,
        "rmsse": rmsse,
        "evaluated_series": int(np.sum(valid_mask)),
        "excluded_zero_scale_series": excluded,
    }


def compute_breakdown(
    df_eval: pd.DataFrame,
    pred_col: str,
    scale_map: dict[str, float],
    window_num: int,
) -> list[dict]:
    """Calcula desglose de MAE, RMSE y RMSSE por tienda, departamento y snap_CA."""
    rows: list[dict] = []
    # Por tienda
    for store in STORES:
        sub = df_eval.loc[df_eval["store_id"] == store]
        m = compute_metrics_for_predictions(sub, pred_col, scale_map)
        rows.append({"window": window_num, "dimension": "store_id", "segment": store, **m})
    # Por departamento
    for dept in DEPARTMENTS:
        sub = df_eval.loc[df_eval["dept_id"] == dept]
        m = compute_metrics_for_predictions(sub, pred_col, scale_map)
        rows.append({"window": window_num, "dimension": "dept_id", "segment": dept, **m})
    # Por snap_CA (1 vs 0)
    for snap_val in (0, 1):
        sub = df_eval.loc[df_eval["snap_CA"] == snap_val]
        m = compute_metrics_for_predictions(sub, pred_col, scale_map)
        label = f"snap_CA={snap_val}"
        rows.append({"window": window_num, "dimension": "snap_CA", "segment": label, **m})
    return rows


def generate_figures(
    summary_df: pd.DataFrame,
    by_window_df: pd.DataFrame,
    breakdown_avg_df: pd.DataFrame,
    fi_df: pd.DataFrame,
    active_df: pd.DataFrame,
    val_w4_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
) -> None:
    """Genera las 4 figuras académicas (fig01..fig04) a 300 DPI."""
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial"]
    plt.rcParams["axes.edgecolor"] = "#CCCCCC"

    # ------------------------------------------------------------------
    # FIG 01: Comparación de modelos (MAE, RMSE, RMSSE y evolución por ventana)
    # ------------------------------------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.4), dpi=300)
    models = [m for m in MODEL_ORDER if m in summary_df["model"].values]
    palette = [WALMART_BLUE, COLOR_TEAL, COLOR_ORANGE, COLOR_GRAY]

    # Panel A: Métricas promedio
    plot_m = summary_df.set_index("model").loc[models]
    metrics = ["mae", "rmse", "rmsse"]
    metric_labels = ["MAE", "RMSE", "RMSSE (M5)"]
    x = np.arange(len(metrics))
    width = 0.19

    for idx, model in enumerate(models):
        vals = [plot_m.loc[model, m] for m in metrics]
        bars = axes[0].bar(
            x + (idx - 1.5) * width,
            vals,
            width=width,
            label=model,
            color=palette[idx],
            edgecolor="white",
            linewidth=0.8,
        )
        for bar, v in zip(bars, vals):
            axes[0].text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.03,
                f"{v:.3f}",
                ha="center",
                va="bottom",
                fontsize=7.5,
                rotation=0,
            )
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(metric_labels, fontweight="bold")
    axes[0].set_ylabel("Error promedio (4 ventanas rodantes)")
    axes[0].set_title("A. Desempeño global: Random Forest vs Baselines", fontweight="bold", color=WALMART_NAVY)
    axes[0].legend(frameon=True, fontsize=8.5, loc="upper left")
    axes[0].set_ylim(0, plot_m[metrics].to_numpy().max() * 1.18)

    # Panel B: RMSSE por ventana temporal
    for idx, model in enumerate(models):
        sub = by_window_df.loc[by_window_df["model"] == model].sort_values("window")
        axes[1].plot(
            sub["window"],
            sub["rmsse"],
            marker="o",
            linewidth=2.3 if model == "Random Forest" else 1.7,
            markersize=6,
            color=palette[idx],
            label=model,
        )
    axes[1].set_xticks([1, 2, 3, 4])
    axes[1].set_xticklabels(["Ventana 1\n(Feb 2016)", "Ventana 2\n(Mar 2016)", "Ventana 3\n(Abr 2016)", "Ventana 4\n(May 2016)"])
    axes[1].set_ylabel("RMSSE oficial M5 (menor es mejor)")
    axes[1].set_title("B. Estabilidad temporal del RMSSE (4 ventanas × 28 días)", fontweight="bold", color=WALMART_NAVY)
    axes[1].legend(frameon=True, fontsize=8.5)

    fig.suptitle(
        "Validación Temporal por Origen Rodante — Walmart California (FOODS, 5,748 series)",
        fontsize=12.5,
        fontweight="bold",
        color=WALMART_NAVY,
        y=1.02,
    )
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig01_validation_metrics_comparison.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # ------------------------------------------------------------------
    # FIG 02: Desglose de RMSSE de Random Forest por tienda, depto y SNAP
    # ------------------------------------------------------------------
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), dpi=300)
    rf_overall_rmsse = float(summary_df.loc[summary_df["model"] == "Random Forest", "rmsse"].iloc[0])

    panel_specs = [
        ("store_id", "A. RMSSE por Tienda (CA)", [WALMART_BLUE] * 4),
        ("dept_id", "B. RMSSE por Departamento", [WALMART_NAVY, WALMART_BLUE, COLOR_TEAL]),
        ("snap_CA", "C. RMSSE: Días SNAP vs No-SNAP", [COLOR_GRAY, WALMART_YELLOW]),
    ]
    for ax, (dim, title, colors) in zip(axes, panel_specs):
        sub = breakdown_avg_df.loc[breakdown_avg_df["dimension"] == dim].copy()
        bars = ax.bar(sub["segment"], sub["rmsse"], color=colors[: len(sub)], edgecolor=WALMART_NAVY, linewidth=0.7)
        ax.axhline(rf_overall_rmsse, color=COLOR_RED, linestyle="--", linewidth=1.2, label=f"Promedio global ({rf_overall_rmsse:.3f})")
        for bar, v in zip(bars, sub["rmsse"]):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.015,
                f"{v:.3f}",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
            )
        ax.set_title(title, fontweight="bold", color=WALMART_NAVY)
        ax.set_ylabel("RMSSE promedio (4 ventanas)")
        ax.set_ylim(0, max(sub["rmsse"].max(), rf_overall_rmsse) * 1.22)
        ax.legend(fontsize=8, loc="lower right")

    fig.suptitle(
        "Desglose de Precisión de Random Forest (RMSSE) — Tienda, Departamento y Efecto SNAP",
        fontsize=12.5,
        fontweight="bold",
        color=WALMART_NAVY,
        y=1.02,
    )
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig02_rmsse_store_snap_breakdown.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # ------------------------------------------------------------------
    # FIG 03: Importancia de variables del Random Forest final
    # ------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 6.2), dpi=300)
    fi_plot = fi_df.sort_values("importance_pct", ascending=True)
    bar_colors = []
    for feat in fi_plot["feature"]:
        if feat.startswith(("lag_", "rolling_")):
            bar_colors.append(WALMART_BLUE)
        elif "price" in feat:
            bar_colors.append(WALMART_YELLOW)
        elif feat in ("snap_CA", "wday", "month", "year", "event_type_1_code"):
            bar_colors.append(COLOR_TEAL)
        else:
            bar_colors.append(COLOR_GRAY)

    bars = ax.barh(fi_plot["feature"], fi_plot["importance_pct"], color=bar_colors, edgecolor="white")
    for bar, v in zip(bars, fi_plot["importance_pct"]):
        ax.text(
            v + 0.4,
            bar.get_y() + bar.get_height() / 2,
            f"{v:.2f}%",
            va="center",
            ha="left",
            fontsize=8.5,
            fontweight="bold",
            color=WALMART_NAVY,
        )
    ax.set_xlabel("Importancia relativa (%)")
    ax.set_title(
        "Importancia de Variables del Modelo Random Forest Final (FOODS · California)",
        fontweight="bold",
        color=WALMART_NAVY,
        pad=12,
    )
    ax.set_xlim(0, fi_plot["importance_pct"].max() * 1.16)

    from matplotlib.patches import Patch

    legend_handles = [
        Patch(facecolor=WALMART_BLUE, label="Historial de demanda (rezagos / medias móviles >= t-28)"),
        Patch(facecolor=WALMART_YELLOW, label="Dinámica de precios"),
        Patch(facecolor=COLOR_TEAL, label="Calendario, eventos y SNAP CA"),
        Patch(facecolor=COLOR_GRAY, label="Identificadores (SKU, depto, tienda)"),
    ]
    ax.legend(handles=legend_handles, loc="lower right", frameon=True, fontsize=8.5)
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig03_feature_importance_rf.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # ------------------------------------------------------------------
    # FIG 04: Ejemplos reales vs predichos (Ventana 4 + Pronóstico 28 días)
    # ------------------------------------------------------------------
    # Seleccionar 3 casos representativos 100% desde los datos reales
    last_90_cutoff = active_df["date"].max() - pd.Timedelta(days=89)
    recent_90 = active_df.loc[active_df["date"] >= last_90_cutoff]
    stats = (
        recent_90.groupby("id", observed=True)
        .agg(
            mean_sales=("units_sold", "mean"),
            zero_pct=("units_sold", lambda s: float((s == 0).mean() * 100.0)),
        )
        .reset_index()
    )
    snap_means = (
        active_df.groupby(["id", "snap_CA"], observed=True)["units_sold"]
        .mean()
        .unstack(fill_value=0.0)
    )
    snap_lift = ((snap_means[1] - snap_means[0]) / snap_means[0].replace(0, np.nan)).rename("snap_lift")
    stats = stats.merge(snap_lift, on="id", how="left")
    stats["id_str"] = stats["id"].astype(str)

    # 1) Alta rotación (mayor venta media con baja intermitencia)
    c1_df = stats.loc[stats["zero_pct"] < 15].sort_values("mean_sales", ascending=False)
    case_high_rot = str(c1_df.iloc[0]["id_str"]) if len(c1_df) > 0 else str(stats.sort_values("mean_sales", ascending=False).iloc[0]["id_str"])

    # 2) Demanda intermitente (entre 55% y 70% de ceros y con ventas en ventana 4)
    c2_df = stats.loc[
        (stats["zero_pct"].between(55, 70))
        & (stats["mean_sales"] >= 0.4)
        & (stats["id_str"] != case_high_rot)
    ].sort_values("mean_sales", ascending=False)
    case_interm = str(c2_df.iloc[0]["id_str"]) if len(c2_df) > 0 else str(stats.iloc[1]["id_str"])

    # 3) Alta sensibilidad SNAP (alto volumen + fuerte lift SNAP)
    c3_df = stats.loc[
        (stats["mean_sales"] >= 3.0)
        & (stats["snap_lift"] > 0.25)
        & (~stats["id_str"].isin([case_high_rot, case_interm]))
    ].sort_values("snap_lift", ascending=False)
    case_snap = str(c3_df.iloc[0]["id_str"]) if len(c3_df) > 0 else str(stats.sort_values("snap_lift", ascending=False).iloc[0]["id_str"])

    selected_cases = [
        (case_high_rot, "Caso 1 — Alta Rotación"),
        (case_interm, "Caso 2 — Demanda Intermitente"),
        (case_snap, "Caso 3 — Alta Sensibilidad SNAP"),
    ]

    fig, axes = plt.subplots(3, 1, figsize=(13.5, 10.5), dpi=300, sharex=True)
    hist_start_plot = active_df["date"].max() - pd.Timedelta(days=69)
    cutoff_dt = active_df["date"].max()
    selected_ids = {sid for sid, _ in selected_cases}
    hist_plot_df = active_df.loc[
        (active_df["date"] >= hist_start_plot) & (active_df["id"].astype(str).isin(selected_ids))
    ].copy()
    hist_plot_df["id_str"] = hist_plot_df["id"].astype(str)
    w4_plot_df = val_w4_df.loc[val_w4_df["id"].astype(str).isin(selected_ids)].copy()
    w4_plot_df["id_str"] = w4_plot_df["id"].astype(str)
    f_plot_df = forecast_df.loc[forecast_df["id"].astype(str).isin(selected_ids)].copy()
    f_plot_df["id_str"] = f_plot_df["id"].astype(str)

    for ax, (sid, label_prefix) in zip(axes, selected_cases):
        h_sub = hist_plot_df.loc[hist_plot_df["id_str"] == sid].sort_values("date")
        w4_sub = w4_plot_df.loc[w4_plot_df["id_str"] == sid].sort_values("date")
        f_sub = f_plot_df.loc[f_plot_df["id_str"] == sid].sort_values("date")

        # Sombreado días SNAP CA == 1 (histórico + futuro)
        snap_dates = pd.concat(
            [h_sub[["date", "snap_CA"]], f_sub[["date", "snap_CA"]]], ignore_index=True
        ).drop_duplicates(subset=["date"])
        snap_on = snap_dates.loc[snap_dates["snap_CA"] == 1, "date"]
        for idx_s, dt in enumerate(snap_on):
            ax.axvspan(
                dt - pd.Timedelta(hours=12),
                dt + pd.Timedelta(hours=12),
                color=WALMART_YELLOW,
                alpha=0.18,
                label="Días SNAP CA" if idx_s == 0 else None,
            )

        ax.plot(h_sub["date"], h_sub["units_sold"], color=WALMART_NAVY, linewidth=1.6, label="Ventas reales")
        ax.plot(w4_sub["date"], w4_sub["pred_rf"], color=WALMART_BLUE, linestyle="--", linewidth=2.0, label="Validación Ventana 4 (RF)")
        ax.plot(f_sub["date"], f_sub["pred_units"], color=COLOR_RED, linewidth=2.2, label="Pronóstico 28 días (RF)")
        ax.axvline(cutoff_dt, color="#333333", linestyle=":", linewidth=1.4)

        row_stat = stats.loc[stats["id_str"] == sid].iloc[0]
        ax.set_title(
            f"{label_prefix}: {sid} | Media 90d={row_stat['mean_sales']:.2f} u/día | "
            f"Ceros 90d={row_stat['zero_pct']:.1f}% | Lift SNAP={row_stat['snap_lift']*100:+.1f}%",
            fontweight="bold",
            fontsize=10,
            color=WALMART_NAVY,
            loc="left",
        )
        ax.set_ylabel("Unidades / día")
        ax.legend(loc="upper right", ncol=4, fontsize=8, frameon=True)

    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    axes[-1].xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    plt.xticks(rotation=25)
    fig.suptitle(
        "Ventas Reales vs Validación Ventana 4 y Pronóstico Futuro 28 Días (Random Forest)",
        fontsize=12.5,
        fontweight="bold",
        color=WALMART_NAVY,
        y=1.01,
    )
    plt.tight_layout()
    fig.savefig(FIGURES_DIR / "fig04_actual_vs_forecast_examples.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Paso 02: Validación temporal rodante y Random Forest (M5 CA).")
    parser.add_argument(
        "--fast-dev",
        action="store_true",
        help="Ejecuta prueba rápida sobre muestra estratificada de 300 series (75 por tienda).",
    )
    parser.add_argument(
        "--max-features",
        type=str,
        default=None,
        help="Sobrescribe temporalmente RF_PARAMS['max_features'] (ej. 'sqrt' o '0.6').",
    )
    return parser.parse_args()


def resolve_max_features(override: str | None) -> str | float:
    if override is None:
        return RF_PARAMS["max_features"]
    if override in ("sqrt", "log2"):
        return override
    return float(override)


def main() -> None:
    args = parse_args()
    t_start = time.perf_counter()
    ensure_directories()

    rf_params = dict(RF_PARAMS)
    rf_params["max_features"] = resolve_max_features(args.max_features)
    mode_label = "FAST-DEV (300 series)" if args.fast_dev else "COMPLETO (5,748 series)"

    print("=" * 76)
    print(f"PASO 02 — VALIDACIÓN RODANTE 4x28d Y RANDOM FOREST [{mode_label}]")
    print("=" * 76)
    print(f"RF_PARAMS activos: {rf_params}")
    rss0, peak0 = get_memory_mb()
    print(f"RAM inicial proceso: RSS={rss0:.1f} MB | Peak={peak0:.1f} MB")

    # 1. Cargar datos procesados
    print("\n[1/5] Cargando parquets del Paso 01...")
    active_df = pd.read_parquet(
        ACTIVE_SALES_3Y_PATH,
        columns=["id", "item_id", "dept_id", "store_id", "d", "date", "units_sold", "sell_price", "snap_CA"],
    )
    features_df = pd.read_parquet(FEATURES_3Y_PATH)
    future_df = pd.read_parquet(FUTURE_28D_FEATURES_PATH)

    if args.fast_dev:
        rng = np.random.default_rng(RANDOM_SEED)
        meta_unique = active_df[["id", "store_id"]].drop_duplicates()
        sampled_ids: list[str] = []
        for store in STORES:
            s_ids = sorted(meta_unique.loc[meta_unique["store_id"] == store, "id"].astype(str).tolist())
            chosen = rng.choice(s_ids, size=75, replace=False).tolist()
            sampled_ids.extend(chosen)
        sampled_set = set(sampled_ids)
        active_df = active_df.loc[active_df["id"].astype(str).isin(sampled_set)].copy()
        features_df = features_df.loc[features_df["id"].astype(str).isin(sampled_set)].copy()
        future_df = future_df.loc[future_df["id"].astype(str).isin(sampled_set)].copy()
        print(f"  - Muestra estratificada cargada: {len(sampled_set)} series (75 por tienda)")
    else:
        assert active_df["id"].nunique() == EXPECTED_SERIES, "Conteo de series inconsistente"
        print(f"  - Portafolio completo cargado: {active_df['id'].nunique():,} series")

    # 2. Definir las 4 ventanas rodantes exactas sobre los últimos 112 días
    all_dates = pd.DatetimeIndex(sorted(active_df["date"].unique()))
    val_total_days = NUM_ROLLING_WINDOWS * HORIZON
    val_dates = all_dates[-val_total_days:]
    windows: list[dict] = []
    for w_idx in range(NUM_ROLLING_WINDOWS):
        w_dates = val_dates[w_idx * HORIZON : (w_idx + 1) * HORIZON]
        w_start = w_dates[0]
        w_end = w_dates[-1]
        t_cut = w_start - pd.Timedelta(days=1)
        windows.append(
            {
                "window": w_idx + 1,
                "start_date": w_start,
                "end_date": w_end,
                "t_cut": t_cut,
            }
        )

    series_ids = sorted(active_df["id"].astype(str).unique().tolist())
    sales_mat = build_sales_matrix(active_df, series_ids, all_dates)
    date_to_idx = {dt: i for i, dt in enumerate(all_dates)}
    print(f"  - Matriz ventas activas construida: {sales_mat.shape} ({sales_mat.nbytes / (1024**2):.1f} MB)")

    # 3. Validación temporal por origen rodante (4 ventanas)
    print("\n[2/5] Ejecutando validación temporal por origen rodante (4 ventanas de 28 días)...")
    window_metric_rows: list[dict] = []
    breakdown_rows: list[dict] = []
    window_timings: list[dict] = []
    ses_alpha_stats: list[dict] = []
    val_w4_predictions: pd.DataFrame | None = None

    for w in windows:
        w_num = w["window"]
        w_start = w["start_date"]
        w_end = w["end_date"]
        t_cut = w["t_cut"]
        t_w0 = time.perf_counter()

        # Historial estricto <= t_cut para baselines y escalas RMSSE
        cut_col = date_to_idx[t_cut] + 1
        y_hist_mat = sales_mat[:, :cut_col]

        scales = compute_rmsse_scales(y_hist_mat)
        scale_map = dict(zip(series_ids, scales))

        ma28_vals = compute_ma28_origin(y_hist_mat)
        ma28_map = dict(zip(series_ids, ma28_vals))

        ses_vals, ses_alphas = fit_predict_ses_vectorized(y_hist_mat)
        ses_map = dict(zip(series_ids, ses_vals))
        ses_alpha_stats.append(
            {
                "window": w_num,
                "mean_alpha": round(float(np.mean(ses_alphas)), 4),
                "median_alpha": round(float(np.median(ses_alphas)), 4),
            }
        )

        # Partición 100% temporal para Random Forest
        train_mask = features_df["date"] <= t_cut
        val_mask = (features_df["date"] >= w_start) & (features_df["date"] <= w_end)

        X_train = np.asfortranarray(
            features_df.loc[train_mask, FEATURE_COLS].to_numpy(dtype=np.float32),
            dtype=np.float32,
        )
        y_train = np.ascontiguousarray(
            features_df.loc[train_mask, "units_sold"].to_numpy(dtype=np.float32),
            dtype=np.float32,
        )
        X_val = np.ascontiguousarray(
            features_df.loc[val_mask, FEATURE_COLS].to_numpy(dtype=np.float32),
            dtype=np.float32,
        )

        rf = RandomForestRegressor(**rf_params)
        rf.fit(X_train, y_train)
        pred_rf = np.clip(rf.predict(X_val), 0.0, None).astype(np.float32)

        eval_df = features_df.loc[
            val_mask, ["id", "item_id", "dept_id", "store_id", "d", "date", "snap_CA", "sell_price", "units_sold", "lag_28"]
        ].copy()
        id_str = eval_df["id"].astype(str)
        eval_df["pred_rf"] = pred_rf
        eval_df["pred_ma28"] = id_str.map(ma28_map).to_numpy(dtype=np.float32)
        eval_df["pred_snaive"] = np.clip(eval_df["lag_28"].to_numpy(dtype=np.float32), 0.0, None)
        eval_df["pred_ses"] = id_str.map(ses_map).to_numpy(dtype=np.float32)

        # Evaluar los 4 modelos
        pred_cols = {
            "Random Forest": "pred_rf",
            "SES (NumPy)": "pred_ses",
            "MA28": "pred_ma28",
            "Seasonal Naïve (lag_28)": "pred_snaive",
        }
        w_log_parts = []
        for model_name, pcol in pred_cols.items():
            m = compute_metrics_for_predictions(eval_df, pcol, scale_map)
            window_metric_rows.append(
                {
                    "window": w_num,
                    "start_date": w_start.strftime("%Y-%m-%d"),
                    "end_date": w_end.strftime("%Y-%m-%d"),
                    "train_rows": int(X_train.shape[0]),
                    "val_rows": int(X_val.shape[0]),
                    "model": model_name,
                    **m,
                }
            )
            w_log_parts.append(f"{model_name}: RMSSE={m['rmsse']:.4f} | RMSE={m['rmse']:.4f} | MAE={m['mae']:.4f}")

        # Desglose de Random Forest por tienda, departamento y snap_CA
        breakdown_rows.extend(compute_breakdown(eval_df, "pred_rf", scale_map, w_num))

        if w_num == NUM_ROLLING_WINDOWS:
            val_w4_predictions = eval_df.drop(columns=["lag_28"]).copy()

        w_elapsed = round(time.perf_counter() - t_w0, 2)
        rss_w, peak_w = get_memory_mb()
        excluded_w = window_metric_rows[-4]["excluded_zero_scale_series"]
        window_timings.append(
            {
                "window": w_num,
                "start_date": w_start.strftime("%Y-%m-%d"),
                "end_date": w_end.strftime("%Y-%m-%d"),
                "elapsed_seconds": w_elapsed,
                "rss_mb": rss_w,
                "peak_ram_mb": peak_w,
                "excluded_zero_scale_series": excluded_w,
            }
        )
        print(
            f"  [Ventana {w_num}: {w_start.strftime('%Y-%m-%d')}..{w_end.strftime('%Y-%m-%d')}] "
            f"{w_elapsed:.1f}s | RSS={rss_w:.0f}MB Peak={peak_w:.0f}MB | excl(scale=0)={excluded_w}"
        )
        for part in w_log_parts:
            print(f"      - {part}")

        # Liberar RAM explícitamente entre ventanas
        del X_train, y_train, X_val, rf, pred_rf, eval_df, y_hist_mat, scales
        gc.collect()

    del sales_mat
    gc.collect()

    # 4. Consolidar tablas de validación
    by_window_df = pd.DataFrame(window_metric_rows)
    summary_df = (
        by_window_df.groupby("model", as_index=False)[["mae", "rmse", "rmsse"]]
        .mean()
        .sort_values("rmsse", ascending=True)
        .reset_index(drop=True)
    )
    rf_row = summary_df.loc[summary_df["model"] == "Random Forest"].iloc[0]
    for metric in ("mae", "rmse", "rmsse"):
        # Mejora % de Random Forest frente a cada modelo: (baseline - RF) / baseline * 100
        summary_df[f"rf_improvement_vs_model_{metric}_pct"] = (
            (summary_df[metric] - float(rf_row[metric])) / summary_df[metric] * 100.0
        )

    breakdown_df = pd.DataFrame(breakdown_rows)
    breakdown_avg_df = (
        breakdown_df.groupby(["dimension", "segment"], as_index=False)[["mae", "rmse", "rmsse"]]
        .mean()
    )
    breakdown_w4_df = (
        breakdown_df.loc[breakdown_df["window"] == NUM_ROLLING_WINDOWS, ["dimension", "segment", "mae", "rmse", "rmsse"]]
        .rename(columns={"mae": "mae_w4", "rmse": "rmse_w4", "rmsse": "rmsse_w4"})
    )
    breakdown_avg_df = breakdown_avg_df.merge(breakdown_w4_df, on=["dimension", "segment"], how="left")
    # Orden lógico para presentación
    dim_order = {"store_id": 0, "dept_id": 1, "snap_CA": 2}
    breakdown_avg_df["dim_ord"] = breakdown_avg_df["dimension"].map(dim_order)
    breakdown_avg_df = (
        breakdown_avg_df.sort_values(["dim_ord", "segment"])
        .drop(columns=["dim_ord"])
        .reset_index(drop=True)
    )

    print("\n[3/5] Resumen comparativo (promedio de 4 ventanas rodantes):")
    print(summary_df.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    if args.fast_dev:
        elapsed_total = round(time.perf_counter() - t_start, 2)
        rss_end, peak_end = get_memory_mb()
        print("\n" + "=" * 76)
        print(
            f"FAST-DEV FINALIZADO en {elapsed_total:.2f}s | RSS={rss_end:.1f} MB | Peak={peak_end:.1f} MB"
        )
        print("(No se sobrescribieron artefactos de producción en modo --fast-dev)")
        print("=" * 76)
        return

    # 5. Entrenar modelo final con TODO el historial hasta d_1941 y predecir 28 días futuros
    print("\n[4/5] Entrenando Random Forest operativo final (hasta d_1941) y pronosticando d_1942..d_1969...")
    t_final0 = time.perf_counter()
    X_full = np.asfortranarray(
        features_df[FEATURE_COLS].to_numpy(dtype=np.float32),
        dtype=np.float32,
    )
    y_full = np.ascontiguousarray(
        features_df["units_sold"].to_numpy(dtype=np.float32),
        dtype=np.float32,
    )
    del features_df
    gc.collect()

    rf_final = RandomForestRegressor(**rf_params)
    rf_final.fit(X_full, y_full)

    X_future = np.ascontiguousarray(
        future_df[FEATURE_COLS].to_numpy(dtype=np.float32),
        dtype=np.float32,
    )
    pred_future = np.clip(rf_final.predict(X_future), 0.0, None).astype(np.float32)

    forecast_df = future_df[["id", "item_id", "dept_id", "store_id", "d", "date", "sell_price", "snap_CA"]].copy()
    forecast_df["pred_units"] = pred_future

    fi_df = pd.DataFrame(
        {
            "feature": FEATURE_COLS,
            "importance": rf_final.feature_importances_.astype(np.float64),
        }
    ).sort_values("importance", ascending=False).reset_index(drop=True)
    fi_df["importance_pct"] = fi_df["importance"] * 100.0
    fi_df["rank"] = np.arange(1, len(fi_df) + 1)

    final_elapsed = round(time.perf_counter() - t_final0, 2)
    rss_final, peak_final = get_memory_mb()
    print(f"  - Modelo final entrenado y pronóstico generado en {final_elapsed:.2f}s | RSS={rss_final:.0f}MB Peak={peak_final:.0f}MB")
    print(f"  - Filas forecast_28d: {len(forecast_df):,} | Suma unidades proyectadas: {forecast_df['pred_units'].sum():,.1f}")

    del X_full, y_full, X_future, rf_final, future_df
    gc.collect()

    # Guardar tablas y parquets
    assert val_w4_predictions is not None
    val_w4_predictions.to_parquet(VAL_WINDOW4_PRED_PATH, engine="pyarrow", index=False)
    forecast_df.to_parquet(FORECAST_28D_PATH, engine="pyarrow", index=False)
    by_window_df.to_csv(TABLES_DIR / "validation_metrics_by_window.csv", index=False)
    summary_df.to_csv(TABLES_DIR / "validation_metrics_summary.csv", index=False)
    breakdown_avg_df.to_csv(TABLES_DIR / "validation_breakdown_store_snap.csv", index=False)
    fi_df.to_csv(TABLES_DIR / "feature_importance.csv", index=False)

    # 6. Generar las 4 figuras académicas (300 DPI)
    print("\n[5/5] Generando figuras académicas fig01..fig04 (300 DPI)...")
    generate_figures(
        summary_df=summary_df,
        by_window_df=by_window_df,
        breakdown_avg_df=breakdown_avg_df,
        fi_df=fi_df,
        active_df=active_df,
        val_w4_df=val_w4_predictions,
        forecast_df=forecast_df,
    )

    elapsed_total = round(time.perf_counter() - t_start, 2)
    rss_end, peak_end = get_memory_mb()

    audit = {
        "status": "PASS",
        "elapsed_total_seconds": elapsed_total,
        "final_model_fit_predict_seconds": final_elapsed,
        "peak_ram_mb": peak_end,
        "end_rss_mb": rss_end,
        "rf_params": rf_params,
        "ses_alpha_grid": list(SES_ALPHA_GRID),
        "ses_alpha_by_window": ses_alpha_stats,
        "window_timings": window_timings,
        "summary_metrics": summary_df.to_dict(orient="records"),
        "breakdown_avg": breakdown_avg_df.to_dict(orient="records"),
        "top_10_features": fi_df.head(10).to_dict(orient="records"),
        "forecast_28d": {
            "rows": int(len(forecast_df)),
            "unique_series": int(forecast_df["id"].nunique()),
            "total_predicted_units": round(float(forecast_df["pred_units"].sum()), 2),
            "mean_daily_predicted_units_per_series": round(float(forecast_df["pred_units"].mean()), 4),
        },
        "figures_generated": [
            "fig01_validation_metrics_comparison.png",
            "fig02_rmsse_store_snap_breakdown.png",
            "fig03_feature_importance_rf.png",
            "fig04_actual_vs_forecast_examples.png",
        ],
    }

    audit_path = METRICS_DIR / "validation_audit.json"
    with audit_path.open("w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 76)
    print(f"PASO 02 COMPLETO FINALIZADO EN {elapsed_total:.2f}s | Peak RAM={peak_end:.1f} MB")
    print(f"Auditoría guardada en: {audit_path}")
    print("=" * 76)


if __name__ == "__main__":
    main()

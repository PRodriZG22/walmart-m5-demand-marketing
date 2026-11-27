"""Paso 01: ETL eficiente en RAM e ingeniería de características sin data leakage (FOODS · CA)."""

from __future__ import annotations

import gc
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (  # noqa: E402
    ACTIVE_SALES_3Y_PATH,
    BUFFER_START_DATE,
    CALENDAR_RAW_PATH,
    ENCODERS_PATH,
    EXPECTED_ITEMS,
    EXPECTED_SERIES,
    FEATURE_COLS,
    FEATURES_3Y_PATH,
    FUTURE_28D_FEATURES_PATH,
    HISTORY_START_DATE,
    HORIZON,
    LAST_FORECAST_DATE,
    LAST_TRAIN_DATE,
    METRICS_DIR,
    PRICES_RAW_PATH,
    RANDOM_SEED,
    SALES_RAW_PATH,
    STORES,
    TARGET_CATEGORY,
    TARGET_STATE,
    ensure_directories,
)


def df_ram_mb(df: pd.DataFrame) -> float:
    """Devuelve el consumo real de RAM en MB de un DataFrame."""
    return float(df.memory_usage(deep=True).sum() / (1024 * 1024))


def main() -> None:
    t0 = time.perf_counter()
    ensure_directories()

    print("=" * 74)
    print("PASO 01 — ETL EFICIENTE EN RAM E INGENIERÍA DE CARACTERÍSTICAS (M5 CA)")
    print("=" * 74)

    # ------------------------------------------------------------------
    # 1. Cargar y recortar calendar.csv
    # ------------------------------------------------------------------
    print("\n[1/7] Cargando calendar.csv y definiendo rangos temporales...")
    cal_cols = ["date", "wm_yr_wk", "wday", "month", "year", "d", "event_type_1", "snap_CA"]
    cal = pd.read_csv(CALENDAR_RAW_PATH, usecols=cal_cols)
    # Imputar event_type_1 nulo ANTES de convertir a category (pandas 3.1.1 CoW safe)
    cal["event_type_1"] = cal["event_type_1"].fillna("No_Event").astype(str)
    cal["date"] = pd.to_datetime(cal["date"])

    buf_start_dt = pd.Timestamp(BUFFER_START_DATE)
    hist_start_dt = pd.Timestamp(HISTORY_START_DATE)
    last_train_dt = pd.Timestamp(LAST_TRAIN_DATE)
    last_forecast_dt = pd.Timestamp(LAST_FORECAST_DATE)

    cal_scope = cal.loc[
        (cal["date"] >= buf_start_dt) & (cal["date"] <= last_forecast_dt)
    ].copy()
    cal_hist = cal_scope.loc[cal_scope["date"] <= last_train_dt].copy()
    cal_future = cal_scope.loc[cal_scope["date"] > last_train_dt].copy()

    hist_day_cols = cal_hist["d"].tolist()
    future_day_cols = cal_future["d"].tolist()
    scope_weeks = set(cal_scope["wm_yr_wk"].unique().tolist())

    assert len(cal_future) == HORIZON, f"Se esperaban {HORIZON} días futuros, hallados {len(cal_future)}"
    print(
        f"  - Histórico + buffer : {hist_day_cols[0]}..{hist_day_cols[-1]} ({len(hist_day_cols)} días)"
    )
    print(
        f"  - Horizonte futuro   : {future_day_cols[0]}..{future_day_cols[-1]} ({len(future_day_cols)} días)"
    )

    del cal, cal_hist
    gc.collect()

    # ------------------------------------------------------------------
    # 2. Cargar sales_train_evaluation.csv (solo columnas necesarias) y filtrar
    # ------------------------------------------------------------------
    print("\n[2/7] Cargando sales_train_evaluation.csv y filtrando FOODS + CA...")
    meta_cols = ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]
    sales_wide = pd.read_csv(SALES_RAW_PATH, usecols=meta_cols + hist_day_cols)
    sales_wide = sales_wide.loc[
        (sales_wide["cat_id"] == TARGET_CATEGORY)
        & (sales_wide["state_id"] == TARGET_STATE)
    ].copy()

    assert len(sales_wide) == EXPECTED_SERIES, f"Esperadas {EXPECTED_SERIES} series, obtenidas {len(sales_wide)}"
    assert sales_wide["item_id"].nunique() == EXPECTED_ITEMS, "Conteo de productos inconsistente"

    sales_wide = sales_wide.drop(columns=["cat_id", "state_id"])
    series_meta = sales_wide[["id", "item_id", "dept_id", "store_id"]].copy()
    scope_items = set(series_meta["item_id"].unique().tolist())

    # ------------------------------------------------------------------
    # 3. Filtrar sell_prices.csv antes del merge
    # ------------------------------------------------------------------
    print("\n[3/7] Cargando y filtrando sell_prices.csv antes del merge...")
    prices = pd.read_csv(PRICES_RAW_PATH)
    prices = prices.loc[
        prices["store_id"].isin(STORES)
        & prices["item_id"].isin(scope_items)
        & prices["wm_yr_wk"].isin(scope_weeks)
    ].copy()
    print(f"  - Filas de precios en alcance temporal FOODS + CA: {len(prices):,}")

    # ------------------------------------------------------------------
    # 4. Wide -> Long + grilla futura 28d + merges + limpieza pre-lanzamiento
    # ------------------------------------------------------------------
    print("\n[4/7] Transformando wide -> long, uniendo calendario/precios y limpiando pre-lanzamientos...")
    long_hist = pd.melt(
        sales_wide,
        id_vars=["id", "item_id", "dept_id", "store_id"],
        value_vars=hist_day_cols,
        var_name="d",
        value_name="units_sold",
    )
    long_hist["is_future"] = False
    long_hist["units_sold"] = long_hist["units_sold"].astype(np.float64)

    del sales_wide
    gc.collect()

    # Grilla futura (5,748 series x 28 días)
    future_grid = series_meta.merge(
        pd.DataFrame({"d": future_day_cols}),
        how="cross",
    )
    future_grid["units_sold"] = np.nan
    future_grid["is_future"] = True

    df = pd.concat([long_hist, future_grid], ignore_index=True)
    raw_long_rows = int(len(df))
    del long_hist, future_grid, cal_future
    gc.collect()

    # Merge con calendario y precios
    df = df.merge(cal_scope, on="d", how="left")
    df = df.merge(prices, on=["store_id", "item_id", "wm_yr_wk"], how="left")

    del cal_scope, prices
    gc.collect()

    # Identificar primera fecha histórica con sell_price.notna() por id y eliminar pre-lanzamiento
    first_price_date = (
        df.loc[df["sell_price"].notna()]
        .groupby("id", sort=False)["date"]
        .min()
    )
    assert len(first_price_date) == EXPECTED_SERIES, (
        f"Solo {len(first_price_date)}/{EXPECTED_SERIES} series tienen precio en el rango"
    )
    first_price_mapped = df["id"].map(first_price_date)
    prelaunch_mask = df["date"] < first_price_mapped
    prelaunch_rows_removed = int(prelaunch_mask.sum())

    df = df.loc[~prelaunch_mask].copy()
    del first_price_date, first_price_mapped, prelaunch_mask
    gc.collect()

    # Ordenar estrictamente por (id, date) antes de ffill de precios y features
    df = df.sort_values(["id", "date"], kind="mergesort").reset_index(drop=True)

    # Verificar huecos de precio post-lanzamiento y rellenar estrictamente hacia adelante por id
    post_launch_null_prices = int(df["sell_price"].isna().sum())
    if post_launch_null_prices > 0:
        df["sell_price"] = df.groupby("id", sort=False)["sell_price"].ffill()

    # Medir RAM real ANTES del downcasting (sobre el panel limpio completo)
    ram_before_mb = df_ram_mb(df)

    # Downcasting inmediato
    # Codificadores determinísticos ordenados alfabéticamente
    item_categories = sorted(df["item_id"].unique().tolist())
    dept_categories = sorted(df["dept_id"].unique().tolist())
    store_categories = sorted(df["store_id"].unique().tolist())
    event_categories = sorted(df["event_type_1"].unique().tolist())
    id_categories = sorted(df["id"].unique().tolist())

    item_to_code = {v: i for i, v in enumerate(item_categories)}
    dept_to_code = {v: i for i, v in enumerate(dept_categories)}
    store_to_code = {v: i for i, v in enumerate(store_categories)}
    event_to_code = {v: i for i, v in enumerate(event_categories)}
    id_to_code = {v: i for i, v in enumerate(id_categories)}

    df["id"] = pd.Categorical(df["id"], categories=id_categories)
    df["item_id"] = pd.Categorical(df["item_id"], categories=item_categories)
    df["dept_id"] = pd.Categorical(df["dept_id"], categories=dept_categories)
    df["store_id"] = pd.Categorical(df["store_id"], categories=store_categories)
    df["d"] = df["d"].astype("category")
    df["event_type_1"] = pd.Categorical(df["event_type_1"], categories=event_categories)

    df["units_sold"] = df["units_sold"].astype(np.float32)
    df["sell_price"] = df["sell_price"].astype(np.float32)
    df["wm_yr_wk"] = df["wm_yr_wk"].astype(np.int16)
    df["wday"] = df["wday"].astype(np.int8)
    df["month"] = df["month"].astype(np.int8)
    df["year"] = df["year"].astype(np.int16)
    df["snap_CA"] = df["snap_CA"].astype(np.int8)

    ram_after_mb = df_ram_mb(df)
    ram_reduction_pct = (1.0 - ram_after_mb / ram_before_mb) * 100.0
    print(f"  - Filas brutas (wide->long + 28d)  : {raw_long_rows:,}")
    print(f"  - Filas pre-lanzamiento eliminadas : {prelaunch_rows_removed:,}")
    print(f"  - Filas activas totales (buf+3y+28): {len(df):,}")
    print(f"  - Precios nulos post-lanz. (ffill) : {post_launch_null_prices:,}")
    print(
        f"  - Memoria RAM panel limpio         : {ram_before_mb:.1f} MB -> {ram_after_mb:.1f} MB "
        f"(reducción {ram_reduction_pct:.2f}%)"
    )

    # ------------------------------------------------------------------
    # 5. Controles de integridad obligatorios + continuidad de calendario
    # ------------------------------------------------------------------
    print("\n[5/7] Ejecutando controles de integridad (duplicados, precios, ventas, continuidad)...")
    n_dups = int(df.duplicated(subset=["id", "date"]).sum())
    n_bad_price = int((df["sell_price"].isna() | (df["sell_price"] <= 0)).sum())
    hist_mask = ~df["is_future"]
    n_neg_sales = int((df.loc[hist_mask, "units_sold"] < 0).sum())
    n_null_hist_sales = int(df.loc[hist_mask, "units_sold"].isna().sum())

    assert n_dups == 0, f"Se hallaron {n_dups} duplicados por (id, date)"
    assert n_bad_price == 0, f"Se hallaron {n_bad_price} registros con sell_price nulo o <= 0"
    assert n_neg_sales == 0, f"Se hallaron {n_neg_sales} registros históricos con units_sold < 0"
    assert n_null_hist_sales == 0, f"Se hallaron {n_null_hist_sales} registros históricos con units_sold nulo"

    # Verificar que tras el lanzamiento no existan huecos de días calendario por serie
    series_idx = df["id"].cat.codes.to_numpy(dtype=np.int16)
    date_diff_days = df["date"].diff().dt.days.to_numpy()
    same_series = np.empty(len(df), dtype=bool)
    same_series[0] = False
    same_series[1:] = series_idx[1:] == series_idx[:-1]
    calendar_gaps = int(np.sum(same_series & (date_diff_days != 1)))
    assert calendar_gaps == 0, f"Se detectaron {calendar_gaps} huecos calendario dentro de las series"
    del date_diff_days, same_series
    gc.collect()

    print("  [OK] 0 duplicados (id, date), 0 sell_price <= 0, 0 units_sold < 0, 0 huecos calendario.")

    # ------------------------------------------------------------------
    # 6. Ingeniería de características (estrictamente sin data leakage)
    # ------------------------------------------------------------------
    print("\n[6/7] Calculando características temporales y de precio sin data leakage...")
    df["series_idx"] = series_idx
    df["item_code"] = df["item_id"].cat.codes.astype(np.int16)
    df["dept_code"] = df["dept_id"].cat.codes.astype(np.int8)
    df["store_code"] = df["store_id"].cat.codes.astype(np.int8)
    df["event_type_1_code"] = df["event_type_1"].cat.codes.astype(np.int8)

    # Rezagos estrictamente >= 28 días
    grp_sales = df.groupby("series_idx", sort=False)["units_sold"]
    df["lag_28"] = grp_sales.shift(28).astype(np.float32)
    df["lag_35"] = grp_sales.shift(35).astype(np.float32)
    df["lag_56"] = grp_sales.shift(56).astype(np.float32)

    # Medias móviles estrictamente desde t-28 hacia atrás (t-34..t-28 y t-55..t-28)
    rm7 = (
        df.groupby("series_idx", sort=False)["lag_28"]
        .rolling(window=7, min_periods=7)
        .mean()
    )
    assert np.array_equal(rm7.index.get_level_values(1).to_numpy(), df.index.to_numpy())
    df["rolling_mean_7"] = rm7.to_numpy(dtype=np.float32)
    del rm7

    rm28 = (
        df.groupby("series_idx", sort=False)["lag_28"]
        .rolling(window=28, min_periods=28)
        .mean()
    )
    assert np.array_equal(rm28.index.get_level_values(1).to_numpy(), df.index.to_numpy())
    df["rolling_mean_28"] = rm28.to_numpy(dtype=np.float32)
    del rm28
    gc.collect()

    # Variación porcentual semanal del precio (vs t-7)
    prev_price_7 = df.groupby("series_idx", sort=False)["sell_price"].shift(7)
    df["price_change"] = (
        ((df["sell_price"] - prev_price_7) / prev_price_7)
        .fillna(0.0)
        .astype(np.float32)
    )
    del prev_price_7

    # Precio relativo vs media expansiva histórica acumulada (estrictamente <= t)
    price_f64 = df["sell_price"].astype(np.float64)
    cum_price = price_f64.groupby(df["series_idx"], sort=False).cumsum()
    cum_count = df.groupby("series_idx", sort=False).cumcount() + 1
    expanding_mean_price = (cum_price / cum_count).astype(np.float64)
    df["relative_price"] = (price_f64 / expanding_mean_price).astype(np.float32)
    del price_f64, cum_price, cum_count, expanding_mean_price
    gc.collect()

    # ------------------------------------------------------------------
    # 7. Separación de tablas, prueba anti-leakage automatizada y guardado
    # ------------------------------------------------------------------
    print("\n[7/7] Ejecutando prueba automatizada anti-leakage y guardando parquets...")

    # a) active_sales_3y.parquet (ventana exacta de 3 años: 2013-05-23 a 2016-05-22)
    mask_3y = (~df["is_future"]) & (df["date"] >= hist_start_dt) & (df["date"] <= last_train_dt)
    active_cols = [
        "id",
        "item_id",
        "dept_id",
        "store_id",
        "d",
        "date",
        "units_sold",
        "sell_price",
        "relative_price",
        "snap_CA",
        "wday",
        "month",
        "year",
        "event_type_1",
    ]
    active_sales_3y = df.loc[mask_3y, active_cols].copy()
    active_sales_3y["units_sold"] = active_sales_3y["units_sold"].astype(np.int16)

    total_active_3y_rows = int(len(active_sales_3y))
    zero_sales_3y_rows = int((active_sales_3y["units_sold"] == 0).sum())
    global_intermittency_pct = (zero_sales_3y_rows / total_active_3y_rows) * 100.0
    active_series_3y = int(active_sales_3y["id"].nunique())

    # b) features_3y.parquet (ventana 3 años con todas las features sin NaN)
    feature_table_cols = ["id", "item_id", "dept_id", "store_id", "d", "date", "units_sold"] + FEATURE_COLS
    features_3y_all = df.loc[mask_3y, feature_table_cols].copy()
    valid_lag_mask = features_3y_all[FEATURE_COLS].notna().all(axis=1)
    cold_start_rows_dropped = int((~valid_lag_mask).sum())
    features_3y = features_3y_all.loc[valid_lag_mask].copy()
    features_3y["units_sold"] = features_3y["units_sold"].astype(np.int16)
    del features_3y_all, valid_lag_mask
    gc.collect()

    assert int(features_3y[FEATURE_COLS].isna().sum().sum()) == 0, "NaNs residuales en features_3y"

    # c) future_28d_features.parquet (d_1942..d_1969: exactamente 5,748 x 28 = 160,944 filas)
    future_cols = ["id", "item_id", "dept_id", "store_id", "d", "date"] + FEATURE_COLS
    future_28d = df.loc[df["is_future"], future_cols].copy()
    expected_future_rows = EXPECTED_SERIES * HORIZON
    assert len(future_28d) == expected_future_rows, (
        f"future_28d tiene {len(future_28d):,} filas, se esperaban {expected_future_rows:,}"
    )

    future_nans_before_impute = int(future_28d[FEATURE_COLS].isna().sum().sum())
    if future_nans_before_impute > 0:
        for col in ["lag_28", "lag_35", "lag_56", "rolling_mean_7", "rolling_mean_28", "price_change"]:
            if future_28d[col].isna().any():
                future_28d[col] = future_28d[col].fillna(0.0).astype(np.float32)
    assert int(future_28d[FEATURE_COLS].isna().sum().sum()) == 0, "NaNs residuales en future_28d_features"

    # Prueba automatizada anti-leakage sobre 200 muestras aleatorias reproducibles
    rng = np.random.default_rng(RANDOM_SEED)
    sample_positions = rng.choice(len(features_3y), size=200, replace=False)
    sample_rows = features_3y.iloc[sample_positions]
    sample_ids = set(sample_rows["id"].astype(str).unique().tolist())

    # Subconjunto compacto solo de los IDs muestreados (bajo uso de RAM)
    sub_lookup = df.loc[
        df["id"].astype(str).isin(sample_ids), ["id", "date", "units_sold", "sell_price"]
    ].copy()
    sub_lookup["id"] = sub_lookup["id"].astype(str)
    grouped_lookup = {
        sid: grp.set_index("date")[["units_sold", "sell_price"]]
        for sid, grp in sub_lookup.groupby("id", sort=False)
    }

    for row in sample_rows.itertuples(index=False):
        sid = str(row.id)
        t_date = row.date
        s_df = grouped_lookup[sid]
        # 1) lag_28 exacto == units_sold en t - 28 días
        expected_lag28 = float(s_df.at[t_date - pd.Timedelta(days=28), "units_sold"])
        assert np.isclose(float(row.lag_28), expected_lag28, atol=1e-5), (
            f"Fuga/desalineación en lag_28 para {sid} en {t_date}: {row.lag_28} != {expected_lag28}"
        )
        # 2) rolling_mean_7 exacto == promedio de [t-34 .. t-28]
        win7_slice = s_df.loc[t_date - pd.Timedelta(days=34) : t_date - pd.Timedelta(days=28), "units_sold"]
        assert len(win7_slice) == 7, f"Ventana de 7 días incompleta para {sid} en {t_date}"
        expected_rm7 = float(win7_slice.mean())
        assert np.isclose(float(row.rolling_mean_7), expected_rm7, rtol=1e-4, atol=1e-4), (
            f"Desalineación en rolling_mean_7 para {sid} en {t_date}: {row.rolling_mean_7} != {expected_rm7}"
        )
        # 3) relative_price exacto == sell_price[t] / mean(sell_price[<= t])
        past_mean = float(s_df.loc[:t_date, "sell_price"].mean())
        expected_rel_price = float(row.sell_price) / past_mean
        assert np.isclose(float(row.relative_price), expected_rel_price, rtol=1e-4, atol=1e-4), (
            f"Fuga en relative_price para {sid} en {t_date}: {row.relative_price} != {expected_rel_price}"
        )

    del sub_lookup, grouped_lookup, df
    gc.collect()
    print("  [OK] Prueba anti-leakage sobre 200 muestras (lag_28, rolling_mean_7, relative_price): PASS")

    # Guardar parquets y encoders
    active_sales_3y.to_parquet(ACTIVE_SALES_3Y_PATH, engine="pyarrow", index=False)
    features_3y.to_parquet(FEATURES_3Y_PATH, engine="pyarrow", index=False)
    future_28d.to_parquet(FUTURE_28D_FEATURES_PATH, engine="pyarrow", index=False)

    encoders = {
        "item_code": item_to_code,
        "dept_code": dept_to_code,
        "store_code": store_to_code,
        "event_type_1_code": event_to_code,
        "id_code": id_to_code,
    }
    with ENCODERS_PATH.open("w", encoding="utf-8") as f:
        json.dump(encoders, f, indent=2, ensure_ascii=False)

    active_mb = round(ACTIVE_SALES_3Y_PATH.stat().st_size / (1024 * 1024), 2)
    features_mb = round(FEATURES_3Y_PATH.stat().st_size / (1024 * 1024), 2)
    future_mb = round(FUTURE_28D_FEATURES_PATH.stat().st_size / (1024 * 1024), 2)
    elapsed_sec = round(time.perf_counter() - t0, 2)

    audit = {
        "status": "PASS",
        "elapsed_seconds": elapsed_sec,
        "row_counts": {
            "raw_long_including_buffer_and_future": raw_long_rows,
            "prelaunch_rows_removed": prelaunch_rows_removed,
            "post_launch_null_prices_ffilled": post_launch_null_prices,
            "active_sales_3y_rows": total_active_3y_rows,
            "cold_start_rows_dropped_from_features_3y": cold_start_rows_dropped,
            "features_3y_rows": int(len(features_3y)),
            "future_28d_features_rows": int(len(future_28d)),
            "future_nans_imputed_with_zero": future_nans_before_impute,
        },
        "series_coverage": {
            "active_sales_3y_unique_series": active_series_3y,
            "features_3y_unique_series": int(features_3y["id"].nunique()),
            "future_28d_unique_series": int(future_28d["id"].nunique()),
        },
        "intermittency_3y_active": {
            "zero_sales_days": zero_sales_3y_rows,
            "total_active_days": total_active_3y_rows,
            "global_intermittency_pct": round(global_intermittency_pct, 4),
        },
        "memory_optimization": {
            "ram_before_downcast_mb": round(ram_before_mb, 2),
            "ram_after_downcast_mb": round(ram_after_mb, 2),
            "ram_reduction_pct": round(ram_reduction_pct, 2),
        },
        "output_files_mb": {
            "active_sales_3y.parquet": active_mb,
            "features_3y.parquet": features_mb,
            "future_28d_features.parquet": future_mb,
        },
        "integrity_checks": {
            "duplicates_id_date": n_dups,
            "invalid_sell_price_le_zero_or_null": n_bad_price,
            "negative_units_sold": n_neg_sales,
            "calendar_gaps_post_launch": calendar_gaps,
            "future_feature_nans_after_check": int(future_28d[FEATURE_COLS].isna().sum().sum()),
            "anti_leakage_sample_test_n200": "PASS",
        },
        "feature_columns": FEATURE_COLS,
    }

    audit_path = METRICS_DIR / "etl_audit.json"
    with audit_path.open("w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 74)
    print(f"PASO 01 COMPLETADO EN {elapsed_sec:.2f}s — AUDITORÍA: PASS -> {audit_path}")
    print(f"  - active_sales_3y.parquet     : {total_active_3y_rows:,} filas ({active_mb:.2f} MB)")
    print(f"  - features_3y.parquet         : {len(features_3y):,} filas ({features_mb:.2f} MB)")
    print(f"  - future_28d_features.parquet : {len(future_28d):,} filas ({future_mb:.2f} MB)")
    print(f"  - Intermitencia global (3y)   : {global_intermittency_pct:.2f}% de días en cero")
    print("=" * 74)


if __name__ == "__main__":
    main()

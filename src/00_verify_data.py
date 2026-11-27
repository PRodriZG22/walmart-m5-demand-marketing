"""Paso 00: Verificación de integridad de datos crudos Kaggle M5 (FOODS · CA)."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import sys
from pathlib import Path

import pandas as pd

# Permite ejecutar como `python src/00_verify_data.py` desde la raíz
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import (  # noqa: E402
    BUFFER_START_DATE,
    CALENDAR_RAW_PATH,
    DEPARTMENTS,
    EXPECTED_ITEMS,
    EXPECTED_SERIES,
    HISTORY_START_DATE,
    HORIZON,
    LAST_FORECAST_DATE,
    LAST_FORECAST_DAY,
    LAST_TRAIN_DATE,
    LAST_TRAIN_DAY,
    METRICS_DIR,
    NUM_ROLLING_WINDOWS,
    PRICES_RAW_PATH,
    RF_PARAMS,
    SALES_RAW_PATH,
    STORES,
    TARGET_CATEGORY,
    TARGET_STATE,
    ensure_directories,
)

TRACKED_PACKAGES = [
    "pandas",
    "numpy",
    "scikit-learn",
    "pyarrow",
    "matplotlib",
    "seaborn",
    "plotly",
    "streamlit",
    "joblib",
]


def get_installed_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for pkg in TRACKED_PACKAGES:
        try:
            versions[pkg] = importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            versions[pkg] = "NOT_INSTALLED"
    return versions


def main() -> None:
    ensure_directories()

    print("=" * 72)
    print("PASO 00 — AUDITORÍA DE ENTORNO Y DATOS CRUDOS KAGGLE M5 (FOODS · CA)")
    print("=" * 72)

    py_ver = platform.python_version()
    pkg_versions = get_installed_versions()
    print(f"Python: {py_ver} ({platform.architecture()[0]})")
    print(f"RF_PARAMS activos: {RF_PARAMS}")
    print("\nLibrerías instaladas:")
    for pkg, ver in pkg_versions.items():
        print(f"  - {pkg:<14}: {ver}")

    # 1. Existencia y tamaño de archivos crudos
    raw_files = {
        "sales_train_evaluation.csv": SALES_RAW_PATH,
        "calendar.csv": CALENDAR_RAW_PATH,
        "sell_prices.csv": PRICES_RAW_PATH,
    }
    file_sizes_mb: dict[str, float] = {}
    print("\n1. Verificación de archivos en data/raw/:")
    for name, path in raw_files.items():
        assert path.exists(), f"Archivo requerido no encontrado: {path}"
        size_mb = round(path.stat().st_size / (1024 * 1024), 2)
        file_sizes_mb[name] = size_mb
        print(f"  [OK] {name:<28} ({size_mb:.2f} MB)")

    # 2. Auditoría de calendar.csv
    print("\n2. Auditoría de calendar.csv:")
    cal = pd.read_csv(CALENDAR_RAW_PATH)
    required_cal_cols = [
        "date",
        "wm_yr_wk",
        "wday",
        "month",
        "year",
        "d",
        "event_type_1",
        "snap_CA",
    ]
    missing_cal = [c for c in required_cal_cols if c not in cal.columns]
    assert not missing_cal, f"Faltan columnas en calendar.csv: {missing_cal}"

    cal["date_dt"] = pd.to_datetime(cal["date"])
    d_to_date = dict(zip(cal["d"], cal["date"]))

    assert "d_1" in d_to_date, "d_1 no existe en calendar.csv"
    assert LAST_TRAIN_DAY in d_to_date, f"{LAST_TRAIN_DAY} no existe en calendar.csv"
    assert LAST_FORECAST_DAY in d_to_date, f"{LAST_FORECAST_DAY} no existe en calendar.csv"
    assert d_to_date[LAST_TRAIN_DAY] == LAST_TRAIN_DATE, (
        f"Esperado {LAST_TRAIN_DAY}={LAST_TRAIN_DATE}, obtenido {d_to_date[LAST_TRAIN_DAY]}"
    )
    assert d_to_date[LAST_FORECAST_DAY] == LAST_FORECAST_DATE, (
        f"Esperado {LAST_FORECAST_DAY}={LAST_FORECAST_DATE}, obtenido {d_to_date[LAST_FORECAST_DAY]}"
    )

    buffer_cal = cal[(cal["date"] >= BUFFER_START_DATE) & (cal["date"] < HISTORY_START_DATE)]
    hist_cal = cal[(cal["date"] >= HISTORY_START_DATE) & (cal["date"] <= LAST_TRAIN_DATE)]
    future_cal = cal[(cal["date"] > LAST_TRAIN_DATE) & (cal["date"] <= LAST_FORECAST_DATE)]

    assert len(buffer_cal) == 60, f"Buffer esperado = 60 días, obtenido {len(buffer_cal)}"
    assert len(future_cal) == HORIZON, f"Horizonte futuro esperado = {HORIZON}, obtenido {len(future_cal)}"

    val_days_total = HORIZON * NUM_ROLLING_WINDOWS
    val_cal = hist_cal.tail(val_days_total)

    print(f"  - Total días calendario : {len(cal)} ({cal['d'].iloc[0]}={cal['date'].iloc[0]} -> {cal['d'].iloc[-1]}={cal['date'].iloc[-1]})")
    print(f"  - Cierre histórico real : {LAST_TRAIN_DAY} = {d_to_date[LAST_TRAIN_DAY]}")
    print(f"  - Cierre pronóstico 28d : {LAST_FORECAST_DAY} = {d_to_date[LAST_FORECAST_DAY]}")
    print(
        f"  - Buffer previo (60d)   : {buffer_cal['d'].iloc[0]}..{buffer_cal['d'].iloc[-1]} "
        f"({buffer_cal['date'].iloc[0]} a {buffer_cal['date'].iloc[-1]}, {len(buffer_cal)} días)"
    )
    print(
        f"  - Ventana 3 años        : {hist_cal['d'].iloc[0]}..{hist_cal['d'].iloc[-1]} "
        f"({hist_cal['date'].iloc[0]} a {hist_cal['date'].iloc[-1]}, {len(hist_cal)} días)"
    )
    print(
        f"  - Validación rodante    : {val_cal['d'].iloc[0]}..{val_cal['d'].iloc[-1]} "
        f"({val_cal['date'].iloc[0]} a {val_cal['date'].iloc[-1]}, {len(val_cal)} días = {NUM_ROLLING_WINDOWS}x{HORIZON})"
    )
    print(
        f"  - Horizonte futuro      : {future_cal['d'].iloc[0]}..{future_cal['d'].iloc[-1]} "
        f"({future_cal['date'].iloc[0]} a {future_cal['date'].iloc[-1]}, {len(future_cal)} días)"
    )

    # 3. Auditoría de sales_train_evaluation.csv (bajo consumo de RAM)
    print("\n3. Auditoría de sales_train_evaluation.csv:")
    sales_header = pd.read_csv(SALES_RAW_PATH, nrows=0).columns.tolist()
    meta_cols = ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]
    for col in meta_cols:
        assert col in sales_header, f"Falta columna {col} en sales_train_evaluation.csv"

    day_cols = [c for c in sales_header if c.startswith("d_")]
    assert day_cols[0] == "d_1" and day_cols[-1] == LAST_TRAIN_DAY, (
        f"Rango de días inesperado en sales_train_evaluation.csv: {day_cols[0]}..{day_cols[-1]}"
    )
    assert len(day_cols) == 1941, f"Se esperaban 1941 columnas de días, obtenidas {len(day_cols)}"

    sales_meta = pd.read_csv(SALES_RAW_PATH, usecols=meta_cols)
    total_series_all = len(sales_meta)

    sales_scope = sales_meta[
        (sales_meta["cat_id"] == TARGET_CATEGORY)
        & (sales_meta["state_id"] == TARGET_STATE)
    ].copy()

    n_items = int(sales_scope["item_id"].nunique())
    n_series = int(len(sales_scope))
    found_stores = sorted(sales_scope["store_id"].unique().tolist())
    found_depts = sorted(sales_scope["dept_id"].unique().tolist())

    assert n_items == EXPECTED_ITEMS, f"Esperados {EXPECTED_ITEMS} productos, encontrados {n_items}"
    assert n_series == EXPECTED_SERIES, f"Esperadas {EXPECTED_SERIES} series, encontradas {n_series}"
    assert found_stores == sorted(STORES), f"Tiendas inesperadas: {found_stores}"
    assert found_depts == sorted(DEPARTMENTS), f"Departamentos inesperados: {found_depts}"
    assert sales_scope["id"].nunique() == EXPECTED_SERIES, "Existen IDs duplicados en el alcance FOODS + CA"

    store_dept_counts = (
        sales_scope.groupby(["store_id", "dept_id"])["id"]
        .count()
        .unstack(fill_value=0)
    )
    dept_item_counts = sales_scope.groupby("dept_id")["item_id"].nunique().to_dict()

    print(f"  - Total series en archivo completo : {total_series_all:,}")
    print(f"  - Columnas de días observados      : {len(day_cols)} ({day_cols[0]}..{day_cols[-1]})")
    print(f"  - Alcance filtrado                 : cat_id={TARGET_CATEGORY}, state_id={TARGET_STATE}")
    print(f"  - Productos únicos (item_id)       : {n_items:,} [VERIFICADO = {EXPECTED_ITEMS:,}]")
    print(f"  - Tiendas verificadas              : {found_stores}")
    print(f"  - Series producto-tienda (id)      : {n_series:,} [VERIFICADO = {EXPECTED_SERIES:,}]")
    print("  - Desglose de series por tienda y departamento:")
    print(store_dept_counts.to_string())

    # 4. Auditoría de sell_prices.csv
    print("\n4. Auditoría de sell_prices.csv:")
    prices = pd.read_csv(
        PRICES_RAW_PATH,
        dtype={"store_id": "category", "item_id": "category", "wm_yr_wk": "int16", "sell_price": "float32"},
    )
    required_price_cols = ["store_id", "item_id", "wm_yr_wk", "sell_price"]
    missing_price = [c for c in required_price_cols if c not in prices.columns]
    assert not missing_price, f"Faltan columnas en sell_prices.csv: {missing_price}"

    scope_items_set = set(sales_scope["item_id"].unique())
    prices_scope = prices[
        prices["store_id"].isin(STORES) & prices["item_id"].isin(scope_items_set)
    ].copy()

    n_price_items = int(prices_scope["item_id"].nunique())
    n_price_stores = int(prices_scope["store_id"].nunique())
    n_null_prices = int(prices_scope["sell_price"].isna().sum())
    n_nonpos_prices = int((prices_scope["sell_price"] <= 0).sum())
    min_price = float(prices_scope["sell_price"].min())
    max_price = float(prices_scope["sell_price"].max())

    future_weeks = set(future_cal["wm_yr_wk"].unique())
    hist_weeks = set(hist_cal["wm_yr_wk"].unique())
    available_weeks = set(prices_scope["wm_yr_wk"].unique())
    missing_hist_weeks = sorted(hist_weeks - available_weeks)
    missing_future_weeks = sorted(future_weeks - available_weeks)

    # Verificar cobertura de series en las semanas futuras
    future_price_pairs = prices_scope[prices_scope["wm_yr_wk"].isin(future_weeks)][
        ["store_id", "item_id"]
    ].drop_duplicates()

    assert n_price_items == EXPECTED_ITEMS, f"Faltan ítems en sell_prices: {n_price_items}/{EXPECTED_ITEMS}"
    assert n_price_stores == len(STORES), f"Faltan tiendas en sell_prices: {n_price_stores}"
    assert n_null_prices == 0, f"Se encontraron {n_null_prices} precios nulos en alcance"
    assert n_nonpos_prices == 0, f"Se encontraron {n_nonpos_prices} precios <= 0 en alcance"
    assert not missing_hist_weeks, f"Faltan semanas históricas en sell_prices: {missing_hist_weeks}"
    assert not missing_future_weeks, f"Faltan semanas futuras en sell_prices: {missing_future_weeks}"

    print(f"  - Filas totales en sell_prices.csv : {len(prices):,}")
    print(f"  - Filas en alcance FOODS + CA      : {len(prices_scope):,}")
    print(f"  - Ítems cubiertos en alcance       : {n_price_items:,} / {EXPECTED_ITEMS:,}")
    print(f"  - Series con precio en d_1942..1969: {len(future_price_pairs):,} / {EXPECTED_SERIES:,}")
    print(f"  - Rango sell_price (USD)           : ${min_price:.2f} a ${max_price:.2f} (nulos={n_null_prices}, <=0={n_nonpos_prices})")
    print(f"  - Cobertura semanas 3y y futuro    : 100% ({len(hist_weeks)} sem. hist., {len(future_weeks)} sem. fut.)")

    # 5. Guardar auditoría JSON
    rolling_windows_info = []
    for w_idx in range(NUM_ROLLING_WINDOWS):
        start_i = w_idx * HORIZON
        end_i = start_i + HORIZON - 1
        w_slice = val_cal.iloc[start_i : end_i + 1]
        rolling_windows_info.append(
            {
                "window": w_idx + 1,
                "start_d": str(w_slice["d"].iloc[0]),
                "end_d": str(w_slice["d"].iloc[-1]),
                "start_date": str(w_slice["date"].iloc[0]),
                "end_date": str(w_slice["date"].iloc[-1]),
                "days": int(len(w_slice)),
            }
        )

    audit = {
        "status": "PASS",
        "python_version": py_ver,
        "packages": pkg_versions,
        "rf_params": RF_PARAMS,
        "raw_files_mb": file_sizes_mb,
        "calendar": {
            "total_days": int(len(cal)),
            "first_day": str(cal["d"].iloc[0]),
            "first_date": str(cal["date"].iloc[0]),
            "last_train_day": LAST_TRAIN_DAY,
            "last_train_date": str(d_to_date[LAST_TRAIN_DAY]),
            "last_forecast_day": LAST_FORECAST_DAY,
            "last_forecast_date": str(d_to_date[LAST_FORECAST_DAY]),
            "buffer_range": {
                "start_d": str(buffer_cal["d"].iloc[0]),
                "end_d": str(buffer_cal["d"].iloc[-1]),
                "start_date": str(buffer_cal["date"].iloc[0]),
                "end_date": str(buffer_cal["date"].iloc[-1]),
                "days": int(len(buffer_cal)),
            },
            "history_3y_range": {
                "start_d": str(hist_cal["d"].iloc[0]),
                "end_d": str(hist_cal["d"].iloc[-1]),
                "start_date": str(hist_cal["date"].iloc[0]),
                "end_date": str(hist_cal["date"].iloc[-1]),
                "days": int(len(hist_cal)),
            },
            "future_28d_range": {
                "start_d": str(future_cal["d"].iloc[0]),
                "end_d": str(future_cal["d"].iloc[-1]),
                "start_date": str(future_cal["date"].iloc[0]),
                "end_date": str(future_cal["date"].iloc[-1]),
                "days": int(len(future_cal)),
            },
            "rolling_windows": rolling_windows_info,
        },
        "sales_scope": {
            "total_rows_raw": int(total_series_all),
            "day_columns_count": int(len(day_cols)),
            "category": TARGET_CATEGORY,
            "state": TARGET_STATE,
            "stores": found_stores,
            "departments": found_depts,
            "unique_items": n_items,
            "total_series": n_series,
            "unique_items_by_dept": {str(k): int(v) for k, v in dept_item_counts.items()},
            "series_by_store_dept": {
                str(store): {str(dept): int(val) for dept, val in row.items()}
                for store, row in store_dept_counts.to_dict(orient="index").items()
            },
        },
        "prices_scope": {
            "total_rows_raw": int(len(prices)),
            "scope_rows": int(len(prices_scope)),
            "unique_items": n_price_items,
            "unique_stores": n_price_stores,
            "future_horizon_series_with_price": int(len(future_price_pairs)),
            "min_price_usd": round(min_price, 4),
            "max_price_usd": round(max_price, 4),
            "null_prices": n_null_prices,
            "non_positive_prices": n_nonpos_prices,
        },
    }

    output_path = METRICS_DIR / "data_verification.json"
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(audit, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 72)
    print(f"AUDITORÍA PASO 00 COMPLETADA: PASS -> {output_path}")
    print("=" * 72)


if __name__ == "__main__":
    main()

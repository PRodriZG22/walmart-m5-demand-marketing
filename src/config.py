"""Configuración centralizada del proyecto Walmart M5 Demand & Marketing (FOODS · CA)."""

from pathlib import Path

# ---------------------------------------------------------------------------
# Rutas del proyecto
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_RAW_DIR = DATA_DIR / "raw"
DATA_PROCESSED_DIR = DATA_DIR / "processed"
DOCS_DIR = PROJECT_ROOT / "docs"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
METRICS_DIR = OUTPUTS_DIR / "metrics"
TABLES_DIR = OUTPUTS_DIR / "tables"
FIGURES_DIR = OUTPUTS_DIR / "figures"

# Archivos crudos Kaggle M5
SALES_RAW_PATH = DATA_RAW_DIR / "sales_train_evaluation.csv"
CALENDAR_RAW_PATH = DATA_RAW_DIR / "calendar.csv"
PRICES_RAW_PATH = DATA_RAW_DIR / "sell_prices.csv"

# Archivos procesados principales
ACTIVE_SALES_3Y_PATH = DATA_PROCESSED_DIR / "active_sales_3y.parquet"
FEATURES_3Y_PATH = DATA_PROCESSED_DIR / "features_3y.parquet"
FUTURE_28D_FEATURES_PATH = DATA_PROCESSED_DIR / "future_28d_features.parquet"
ENCODERS_PATH = DATA_PROCESSED_DIR / "encoders.json"
VAL_WINDOW4_PRED_PATH = DATA_PROCESSED_DIR / "val_window4_predictions.parquet"
FORECAST_28D_PATH = DATA_PROCESSED_DIR / "forecast_28d.parquet"

# ---------------------------------------------------------------------------
# Alcance real del dataset y parámetros temporales
# ---------------------------------------------------------------------------
TARGET_CATEGORY = "FOODS"
TARGET_STATE = "CA"
STORES = ["CA_1", "CA_2", "CA_3", "CA_4"]
DEPARTMENTS = ["FOODS_1", "FOODS_2", "FOODS_3"]

EXPECTED_ITEMS = 1437
EXPECTED_SERIES = 5748

HORIZON = 28
NUM_ROLLING_WINDOWS = 4
YEARS_HISTORY = 3
LAG_BUFFER_DAYS = 60
RANDOM_SEED = 42

# Fechas y días clave oficiales de M5 (verificados en Paso 00)
LAST_TRAIN_DAY = "d_1941"
LAST_TRAIN_DATE = "2016-05-22"
LAST_FORECAST_DAY = "d_1969"
LAST_FORECAST_DATE = "2016-06-19"
HISTORY_START_DATE = "2013-05-23"
BUFFER_START_DATE = "2013-03-24"

# ---------------------------------------------------------------------------
# Umbrales de diagnóstico de riesgo y motor prescriptivo de marketing
# ---------------------------------------------------------------------------
DECLINE_HIGH = 30.0
DECLINE_MED = 10.0
INTERMITTENCY_HIGH = 70.0
INTERMITTENCY_MED = 40.0
REVENUE_TOP_QUANTILE = 0.80

PRICE_PROMO_THRESHOLD = 0.95
PRICE_SENSITIVITY_MIN = 0.10
PRICE_PROMO_MIN_DAYS = 7

SNAP_SENSITIVITY_MIN = 0.10
SNAP_PRIORITY_THRESHOLD = 0.15

# ---------------------------------------------------------------------------
# Hiperparámetros Random Forest calibrados (i7-1255U, 16 GB RAM / ~4.6 GB libres)
# ---------------------------------------------------------------------------
RF_PARAMS = {
    "n_estimators": 100,
    "max_depth": 16,
    "min_samples_leaf": 25,
    "max_samples": 0.30,
    "max_features": "sqrt",
    "random_state": RANDOM_SEED,
    "n_jobs": 6,
}

# Variables explicativas del modelo (cero data leakage)
FEATURE_COLS = [
    "lag_28",
    "lag_35",
    "lag_56",
    "rolling_mean_7",
    "rolling_mean_28",
    "sell_price",
    "price_change",
    "relative_price",
    "wday",
    "month",
    "year",
    "event_type_1_code",
    "snap_CA",
    "item_code",
    "dept_code",
    "store_code",
]


def ensure_directories() -> None:
    """Crea si no existen los directorios de salida y datos procesados."""
    for directory in (DATA_PROCESSED_DIR, METRICS_DIR, TABLES_DIR, FIGURES_DIR):
        directory.mkdir(parents=True, exist_ok=True)

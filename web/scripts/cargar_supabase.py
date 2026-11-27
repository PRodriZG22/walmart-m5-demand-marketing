"""Carga en Supabase los mismos datos que usa el dashboard de Streamlit.

Reutiliza las funciones de app/dashboard.py para que las columnas derivadas sean idénticas.
Las tablas son de solo lectura para el público: antes de ejecutar este script hay que crear una
política temporal de inserción que exija la cabecera x-load-token, y borrarla al terminar.

Variables de entorno: SUPABASE_URL, SUPABASE_KEY (publicable), LOAD_TOKEN.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))
import dashboard as d  # noqa: E402

URL = os.environ["SUPABASE_URL"].rstrip("/")
HEADERS = {
    "apikey": os.environ["SUPABASE_KEY"],
    "x-load-token": os.environ["LOAD_TOKEN"],
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}


def registros(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", double_precision=10, date_format="iso"))


def subir(tabla: str, filas: list[dict], lote: int) -> None:
    for i in range(0, len(filas), lote):
        r = requests.post(f"{URL}/rest/v1/{tabla}", headers=HEADERS, data=json.dumps(filas[i : i + lote]), timeout=120)
        if r.status_code >= 300:
            raise SystemExit(f"{tabla} lote {i}: {r.status_code} {r.text[:400]}")
    print(f"{tabla}: {len(filas):,} filas")


def columnas(grupo: pd.DataFrame, cols: list[str]) -> dict:
    salida = {}
    for c in cols:
        v = grupo[c]
        if c == "date":
            salida[c] = pd.to_datetime(v).dt.strftime("%Y-%m-%d").tolist()
        else:
            salida[c] = [None if pd.isna(x) else round(float(x), 4) for x in v]
    return salida


def main() -> None:
    diag = d.load_diagnosis()
    subir("diagnosis", registros(diag), 500)

    hist = d.load_history_90d()
    w4, forecast = d.load_predictions()
    partes = {
        "hist": (hist, ["date", "units_sold", "sell_price", "snap_CA"]),
        "w4": (w4, ["date", "units_sold", "pred_rf", "pred_ses", "pred_ma28", "pred_snaive"]),
        "forecast": (forecast, ["date", "sell_price", "snap_CA", "pred_units"]),
    }
    series: dict[str, dict] = {i: {"id": i} for i in diag["id"]}
    for nombre, (df, cols) in partes.items():
        for sid, g in df.sort_values(["id", "date"]).groupby("id", sort=False):
            series[sid][nombre] = columnas(g, cols)
    subir("series", list(series.values()), 200)

    tablas = {k: registros(v) for k, v in d.load_validation_and_kmeans().items()}
    tablas["audits"] = d.load_audits()
    senal = {str(u): registros(d.calcular_senal_caida(hist, w4, u / 100.0).replace({np.nan: None})) for u in (10, 20, 30)}
    tablas["senal_caida"] = senal
    subir("reports", [{"key": k, "data": v} for k, v in tablas.items()], 20)


if __name__ == "__main__":
    main()

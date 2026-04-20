"""
data_loader.py — загрузка данных из Excel и MOEX ISS API.
"""

import json
import os
from pathlib import Path

import pandas as pd
import requests

DATA_DIR  = Path(__file__).parent / "data"
CACHE_FILE = DATA_DIR / "benchmark_cache.json"
EXCEL_FILE = DATA_DIR / "Дивиденды_с_2019_MOEX.xlsx"

# Единый широкий диапазон для кэша — все запросы берут отсюда
_CACHE_START = 2001
_CACHE_END   = 2030

RISK_FREE_RATES = {
    2001: 0.250, 2002: 0.210, 2003: 0.160, 2004: 0.130, 2005: 0.130,
    2006: 0.110, 2007: 0.100, 2008: 0.130, 2009: 0.090, 2010: 0.080,
    2011: 0.080, 2012: 0.080, 2013: 0.080, 2014: 0.095, 2015: 0.150,
    2016: 0.105, 2017: 0.090, 2018: 0.075, 2019: 0.070, 2020: 0.045,
    2021: 0.060, 2022: 0.110, 2023: 0.160, 2024: 0.165, 2025: 0.210,
}


def load_index_data() -> pd.DataFrame:
    """
    Читает лист «Индекс с Дивидендами».
    Возвращает DataFrame: year, ticker, price, weight, dividend, div_yield
    """
    df = pd.read_excel(EXCEL_FILE, sheet_name="Индекс с Дивидендами")
    df = df.rename(columns={
        "Год":              "year",
        "Код инструмента":  "ticker",
        "Цена, RUB":        "price",
        "Вес, %":           "weight",
        "Dividend":         "dividend",
        "Див. Доходность":  "div_yield",
    })
    for col in ("div_yield", "dividend", "price", "weight"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["year"]   = df["year"].astype(int)
    df["ticker"] = df["ticker"].astype(str).str.strip()
    return df[["year", "ticker", "price", "weight", "dividend", "div_yield"]].copy()


# ──────────────────────────────────────────────────────────────
# MOEX ISS — годовые доходности индекса
# ──────────────────────────────────────────────────────────────

def _fetch_index_from_moex(ticker: str, start_year: int, end_year: int) -> dict[int, float]:
    """Загружает дневные свечи индекса с MOEX ISS и возвращает {year: return}."""
    url = (
        f"https://iss.moex.com/iss/history/engines/stock/"
        f"markets/index/securities/{ticker}.json"
    )
    all_rows: list[dict] = []
    start = 0

    while True:
        try:
            resp = requests.get(url, params={
                "from":     f"{start_year}-01-02",
                "till":     f"{end_year}-12-31",
                "interval": 1,
                "start":    start,
            }, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            cols = data["history"]["columns"]
            rows = data["history"]["data"]
        except Exception:
            break

        if not rows:
            break

        all_rows.extend([dict(zip(cols, r)) for r in rows])
        start += len(rows)
        # Если вернулось меньше страницы — больше данных нет
        if len(rows) < 100:
            break

    if not all_rows:
        return {}

    df = pd.DataFrame(all_rows)
    df["TRADEDATE"] = pd.to_datetime(df["TRADEDATE"])
    df["year"]  = df["TRADEDATE"].dt.year
    df["CLOSE"] = pd.to_numeric(df["CLOSE"], errors="coerce")

    annual: dict[int, float] = {}
    for year, grp in df.groupby("year"):
        grp = grp.sort_values("TRADEDATE").dropna(subset=["CLOSE"])
        if len(grp) < 5:
            continue
        p_open  = grp["CLOSE"].iloc[0]
        p_close = grp["CLOSE"].iloc[-1]
        if p_open > 0:
            annual[int(year)] = round(p_close / p_open - 1, 6)
    return annual


def get_benchmark_returns(start_year: int = 2001, end_year: int = 2025) -> pd.Series:
    """
    Годовые доходности IMOEX за запрошенный диапазон.

    Данные кэшируются одним широким запросом (2001–2030).
    Повторные вызовы с любым диапазоном не делают новых запросов к API.
    """
    cache: dict = {}
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            cache = json.load(f)

    # Единый ключ для всех запросов
    key = f"imoex_{_CACHE_START}_{_CACHE_END}"

    if key not in cache:
        returns = _fetch_index_from_moex("IMOEX", _CACHE_START, _CACHE_END)
        if returns:
            cache[key] = returns
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)

    raw = cache.get(key, {})
    full_series = pd.Series({int(k): v for k, v in raw.items()}).sort_index()

    # Фильтруем по запрошенному диапазону
    return full_series[
        (full_series.index >= start_year) &
        (full_series.index <= end_year)
    ]


def clear_benchmark_cache() -> None:
    """Удаляет кэш — использовать для принудительного обновления данных."""
    if CACHE_FILE.exists():
        os.remove(CACHE_FILE)


def get_risk_free_rates() -> dict:
    return RISK_FREE_RATES
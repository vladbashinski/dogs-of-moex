"""
conftest.py — общие фикстуры для тестов backtester.py
"""

import pandas as pd
import pytest


@pytest.fixture
def simple_index_data():
    """
    Простой набор данных: 3 акции × 3 года (2020, 2021, 2022).
    Известные значения для проверки логики.
    """
    rows = []
    # 2020 — год отбора для 2021
    rows += [
        {"year": 2020, "ticker": "AAA", "price": 100.0, "weight": 0.10,
         "dividend": 10.0, "div_yield": 0.10},
        {"year": 2020, "ticker": "BBB", "price": 200.0, "weight": 0.05,
         "dividend": 16.0, "div_yield": 0.08},
        {"year": 2020, "ticker": "CCC", "price": 50.0,  "weight": 0.02,
         "dividend": 1.0,  "div_yield": 0.02},
    ]
    # 2021 — год удержания / год отбора для 2022
    rows += [
        {"year": 2021, "ticker": "AAA", "price": 110.0, "weight": 0.10,
         "dividend": 11.0, "div_yield": 0.10},
        {"year": 2021, "ticker": "BBB", "price": 220.0, "weight": 0.05,
         "dividend": 17.6, "div_yield": 0.08},
        {"year": 2021, "ticker": "CCC", "price": 60.0,  "weight": 0.02,
         "dividend": 1.2,  "div_yield": 0.02},
    ]
    # 2022 — год удержания
    rows += [
        {"year": 2022, "ticker": "AAA", "price": 121.0, "weight": 0.10,
         "dividend": 12.1, "div_yield": 0.10},
        {"year": 2022, "ticker": "BBB", "price": 200.0, "weight": 0.05,
         "dividend": 16.0, "div_yield": 0.08},
        {"year": 2022, "ticker": "CCC", "price": 70.0,  "weight": 0.02,
         "dividend": 1.4,  "div_yield": 0.02},
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def filter_test_data():
    """
    Данные с разными уровнями дивдоходности для проверки фильтров.
    5 акций в 2020 (год отбора) и 2021 (год удержания).
    """
    rows = []
    # 2020
    rows += [
        {"year": 2020, "ticker": "T01", "price": 100, "weight": 0.05,
         "dividend": 30, "div_yield": 0.30},  # выше max_yield 0.25
        {"year": 2020, "ticker": "T02", "price": 100, "weight": 0.05,
         "dividend": 15, "div_yield": 0.15},
        {"year": 2020, "ticker": "T03", "price": 100, "weight": 0.05,
         "dividend": 8,  "div_yield": 0.08},
        {"year": 2020, "ticker": "T04", "price": 100, "weight": 0.05,
         "dividend": 4,  "div_yield": 0.04},  # ниже min_yield 0.05
        {"year": 2020, "ticker": "T05", "price": 100, "weight": 0.005,
         "dividend": 12, "div_yield": 0.12},  # ниже min_weight 0.01
    ]
    # 2021 — все остаются по той же цене
    rows += [
        {"year": 2021, "ticker": "T01", "price": 110, "weight": 0.05,
         "dividend": 30, "div_yield": 0.30},
        {"year": 2021, "ticker": "T02", "price": 110, "weight": 0.05,
         "dividend": 15, "div_yield": 0.15},
        {"year": 2021, "ticker": "T03", "price": 110, "weight": 0.05,
         "dividend": 8,  "div_yield": 0.08},
        {"year": 2021, "ticker": "T04", "price": 110, "weight": 0.05,
         "dividend": 4,  "div_yield": 0.04},
        {"year": 2021, "ticker": "T05", "price": 110, "weight": 0.005,
         "dividend": 12, "div_yield": 0.12},
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def no_commission():
    """Параметр-комиссия = 0 для проверки расчётов без округления."""
    return 0.0


@pytest.fixture
def rfr_zero():
    """Безрисковая ставка = 0 для проверки Sharpe/Sortino без MAR."""
    return {y: 0.0 for y in range(2018, 2030)}
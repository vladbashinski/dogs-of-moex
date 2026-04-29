"""
test_returns.py — тесты расчёта доходности портфеля и отдельных бумаг.
"""

import pandas as pd
import pytest
from backtester import run_backtest, StrategyParams


def test_price_return_calculation(simple_index_data, no_commission):
    """
    AAA: P_buy=100 (2020), P_sell=110 (2021) → price_ret = (110-100)/100 = 10%
    BBB: P_buy=200, P_sell=220 → price_ret = 10%
    """
    params = StrategyParams(
        start_year=2021, end_year=2021,
        n_dogs=2, commission=no_commission,
        min_div_yield=0.0, max_div_yield=0.99, min_index_weight=0.0,
    )
    result = run_backtest(simple_index_data, params)
    stocks = result.annual[0].stocks.set_index("ticker")

    assert stocks.loc["AAA", "price_ret"] == pytest.approx(0.10, abs=1e-6)
    assert stocks.loc["BBB", "price_ret"] == pytest.approx(0.10, abs=1e-6)


def test_dividend_return_uses_buy_price(simple_index_data, no_commission):
    """
    Дивидендная доходность считается к цене покупки (Y-1), не к цене продажи.
    AAA: dividend_2021=11, P_buy=100 → div_ret = 11/100 = 0.11
    """
    params = StrategyParams(
        start_year=2021, end_year=2021,
        n_dogs=2, commission=no_commission,
        min_div_yield=0.0, max_div_yield=0.99, min_index_weight=0.0,
    )
    result = run_backtest(simple_index_data, params)
    stocks = result.annual[0].stocks.set_index("ticker")

    assert stocks.loc["AAA", "div_ret"] == pytest.approx(0.11, abs=1e-6)


def test_total_return_includes_double_commission(simple_index_data):
    """
    total_return портфеля = mean(stock_total_ret) - 2*commission.
    AAA total_ret = 10% + 11% = 21%
    BBB total_ret = 10% + 8.8% = 18.8%
    Mean = 19.9%, минус 2*0.001 = 0.2% → 19.7%
    """
    commission = 0.001
    params = StrategyParams(
        start_year=2021, end_year=2021,
        n_dogs=2, commission=commission,
        min_div_yield=0.0, max_div_yield=0.99, min_index_weight=0.0,
    )
    result = run_backtest(simple_index_data, params)

    expected = ((0.21 + 0.188) / 2) - 2 * commission
    assert result.annual[0].portfolio_return == pytest.approx(expected, abs=1e-4)


def test_delisted_stock_excluded(no_commission):
    """
    Если у акции нет цены в году удержания (делистинг или выход из индекса),
    она должна быть исключена из портфеля, а не падать с ошибкой.
    """
    rows = [
        # 2020 — три акции, все попадают в топ
        {"year": 2020, "ticker": "OK1",   "price": 100, "weight": 0.05,
         "dividend": 10, "div_yield": 0.10},
        {"year": 2020, "ticker": "OK2",   "price": 100, "weight": 0.05,
         "dividend": 8,  "div_yield": 0.08},
        {"year": 2020, "ticker": "DELIST","price": 100, "weight": 0.05,
         "dividend": 12, "div_yield": 0.12},
        # 2021 — DELIST исчезла из индекса
        {"year": 2021, "ticker": "OK1", "price": 110, "weight": 0.05,
         "dividend": 11, "div_yield": 0.10},
        {"year": 2021, "ticker": "OK2", "price": 105, "weight": 0.05,
         "dividend": 8,  "div_yield": 0.08},
    ]
    df = pd.DataFrame(rows)

    params = StrategyParams(
        start_year=2021, end_year=2021,
        n_dogs=3, commission=no_commission,
        min_div_yield=0.0, max_div_yield=0.99, min_index_weight=0.0,
    )
    result = run_backtest(df, params)

    selected = set(result.annual[0].stocks["ticker"])
    assert "DELIST" not in selected, "Делистнутая акция не должна попасть в результат"
    assert selected == {"OK1", "OK2"}, f"Ожидали {{OK1, OK2}}, получили {selected}"
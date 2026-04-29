"""
test_metrics.py — тесты вычисления риск-скорректированных метрик.
"""

import pandas as pd
import numpy as np
import pytest
from backtester import run_backtest, StrategyParams


def _make_constant_return_data(returns_per_year: dict, ticker: str = "X"):
    """
    Конструктор данных где одна акция X даёт заданную доходность за каждый год.
    Реализуется через выбор P_buy и P_sell.
    """
    rows = []
    base_year = min(returns_per_year.keys()) - 1
    price = 100.0
    rows.append({
        "year": base_year, "ticker": ticker, "price": price, "weight": 0.10,
        "dividend": 0.0, "div_yield": 0.10,  # любой ненулевой yield для отбора
    })
    for year in sorted(returns_per_year.keys()):
        ret = returns_per_year[year]
        new_price = price * (1 + ret)
        rows.append({
            "year": year, "ticker": ticker, "price": new_price, "weight": 0.10,
            "dividend": 0.0, "div_yield": 0.10,
        })
        price = new_price
    return pd.DataFrame(rows)


def test_cagr_constant_growth(rfr_zero, no_commission):
    """
    Если каждый год доходность ровно +10%, CAGR должен быть 10%.
    """
    df = _make_constant_return_data({2021: 0.10, 2022: 0.10, 2023: 0.10})

    params = StrategyParams(
        start_year=2021, end_year=2023,
        n_dogs=1, commission=no_commission,
        min_div_yield=0.0, max_div_yield=0.99, min_index_weight=0.0,
    )
    result = run_backtest(df, params, risk_free_rates=rfr_zero)

    assert result.metrics["cagr"] == pytest.approx(0.10, abs=1e-3)


def test_max_drawdown_calculation(rfr_zero, no_commission):
    """
    Доходности: +20%, -50%, +10%, +10%
    Capital: 1.0 → 1.2 → 0.6 → 0.66 → 0.726
    Peak = 1.2, низшая точка после пика = 0.6
    Max DD = (0.6 - 1.2) / 1.2 = -50%
    """
    df = _make_constant_return_data({
        2021: 0.20, 2022: -0.50, 2023: 0.10, 2024: 0.10,
    })

    params = StrategyParams(
        start_year=2021, end_year=2024,
        n_dogs=1, commission=no_commission,
        min_div_yield=0.0, max_div_yield=0.99, min_index_weight=0.0,
    )
    result = run_backtest(df, params, risk_free_rates=rfr_zero)

    assert result.metrics["max_drawdown"] == pytest.approx(-0.50, abs=1e-3)


def test_win_rate_counts_positive_years(rfr_zero, no_commission):
    """
    Доходности: +10%, -5%, +20%, -2%, +8%
    Положительных: 3 из 5 → Win Rate = 60%
    """
    df = _make_constant_return_data({
        2021: 0.10, 2022: -0.05, 2023: 0.20, 2024: -0.02, 2025: 0.08,
    })

    params = StrategyParams(
        start_year=2021, end_year=2025,
        n_dogs=1, commission=no_commission,
        min_div_yield=0.0, max_div_yield=0.99, min_index_weight=0.0,
    )
    result = run_backtest(df, params, risk_free_rates=rfr_zero)

    assert result.metrics["win_rate"] == pytest.approx(0.60, abs=1e-3)


def test_sharpe_uses_excess_std(no_commission):
    """
    Sharpe = mean(excess) / std(excess), где excess = R - Rf.
    При Rf=0 для двух разных лет:
      returns = [+10%, +30%]
      mean = 20%, std = 14.142%
      Sharpe = 0.20 / 0.14142 ≈ 1.414
    """
    df = _make_constant_return_data({2021: 0.10, 2022: 0.30})
    rfr_zero = {y: 0.0 for y in range(2020, 2030)}

    params = StrategyParams(
        start_year=2021, end_year=2022,
        n_dogs=1, commission=no_commission,
        min_div_yield=0.0, max_div_yield=0.99, min_index_weight=0.0,
    )
    result = run_backtest(df, params, risk_free_rates=rfr_zero)

    expected = 0.20 / np.std([0.10, 0.30], ddof=1)
    assert result.metrics["sharpe"] == pytest.approx(expected, abs=1e-2)


def test_sortino_uses_only_negative_excess(no_commission):
    """
    Sortino использует std только отрицательных excess returns.
    returns = [+10%, +30%, -20%, -10%], Rf=0
    Negative excess: [-20%, -10%]
    std(downside) = std([-0.20, -0.10], ddof=1) = 0.0707
    mean(excess) = (10 + 30 - 20 - 10) / 4 = 2.5%
    Sortino = 0.025 / 0.0707 ≈ 0.354
    """
    df = _make_constant_return_data({
        2021: 0.10, 2022: 0.30, 2023: -0.20, 2024: -0.10,
    })
    rfr_zero = {y: 0.0 for y in range(2020, 2030)}

    params = StrategyParams(
        start_year=2021, end_year=2024,
        n_dogs=1, commission=no_commission,
        min_div_yield=0.0, max_div_yield=0.99, min_index_weight=0.0,
    )
    result = run_backtest(df, params, risk_free_rates=rfr_zero)

    expected_dn_std = np.std([-0.20, -0.10], ddof=1)
    expected_mean = (0.10 + 0.30 - 0.20 - 0.10) / 4
    expected_sortino = expected_mean / expected_dn_std

    assert result.metrics["sortino"] == pytest.approx(expected_sortino, abs=1e-2)
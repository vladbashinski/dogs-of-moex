"""
test_edge_cases.py — граничные случаи и устойчивость к плохим данным.
"""

import pandas as pd
from backtester import run_backtest, StrategyParams


def test_empty_data_returns_empty_result(no_commission):
    """Бэктестер не должен падать на пустом DataFrame."""
    df = pd.DataFrame(columns=["year", "ticker", "price", "weight",
                                "dividend", "div_yield"])

    params = StrategyParams(
        start_year=2021, end_year=2022,
        n_dogs=10, commission=no_commission,
        min_div_yield=0.0, max_div_yield=0.99, min_index_weight=0.0,
    )
    result = run_backtest(df, params)

    assert result.annual == []
    assert result.metrics == {}


def test_single_year_period_works(simple_index_data, no_commission, rfr_zero):
    """Один год бэктеста (start_year == end_year) должен работать без ошибок."""
    params = StrategyParams(
        start_year=2021, end_year=2021,
        n_dogs=2, commission=no_commission,
        min_div_yield=0.0, max_div_yield=0.99, min_index_weight=0.0,
    )
    result = run_backtest(simple_index_data, params, risk_free_rates=rfr_zero)

    assert len(result.annual) == 1
    assert result.metrics["n_years"] == 1
    assert "cagr" in result.metrics
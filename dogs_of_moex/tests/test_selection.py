"""
test_selection.py — тесты отбора акций в портфель.
"""

from backtester import run_backtest, StrategyParams


def test_selects_top_n_by_previous_year_yield(simple_index_data, no_commission):
    """
    Отбор должен идти по div_yield ПРЕДЫДУЩЕГО года (защита от look-ahead).
    В 2020: AAA=10%, BBB=8%, CCC=2%.
    В 2021 портфель должен быть {AAA, BBB} (топ-2).
    """
    params = StrategyParams(
        start_year=2021, end_year=2021,
        n_dogs=2, commission=no_commission,
        min_div_yield=0.0, max_div_yield=0.99, min_index_weight=0.0,
    )
    result = run_backtest(simple_index_data, params)

    assert len(result.annual) == 1
    portfolio = result.annual[0].stocks
    selected_tickers = set(portfolio["ticker"])
    assert selected_tickers == {"AAA", "BBB"}, \
        f"Ожидали отбор по 2020 году ({{AAA, BBB}}), получили {selected_tickers}"


def test_filters_apply_correctly(filter_test_data, no_commission):
    """
    После применения min_yield=5%, max_yield=25%, min_weight=1%
    должны остаться T02 и T03. T01 (yield 30%), T04 (yield 4%), T05 (weight 0.5%) — отсеяны.
    """
    params = StrategyParams(
        start_year=2021, end_year=2021,
        n_dogs=10, commission=no_commission,
        min_div_yield=0.05, max_div_yield=0.25, min_index_weight=0.01,
    )
    result = run_backtest(filter_test_data, params)

    assert len(result.annual) == 1
    selected = set(result.annual[0].stocks["ticker"])
    assert selected == {"T02", "T03"}, \
        f"Фильтры пропустили {selected}, ожидали {{T02, T03}}"


def test_low5_mode_picks_cheapest_from_top_n(no_commission):
    """
    В режиме Low-5: из топ-N по доходности берутся 5 самых дешёвых по цене.
    """
    import pandas as pd
    rows = []
    # 2020: 6 акций, все с одинаковой div_yield, но разные цены
    for i, (ticker, price) in enumerate([
        ("HIGH1", 1000), ("HIGH2", 800), ("MID1", 500),
        ("LOW1", 100), ("LOW2", 50), ("LOW3", 20),
    ]):
        rows.append({"year": 2020, "ticker": ticker, "price": price,
                     "weight": 0.05, "dividend": price * 0.10, "div_yield": 0.10})
    # 2021 — те же позиции
    for ticker, price in [
        ("HIGH1", 1100), ("HIGH2", 880), ("MID1", 550),
        ("LOW1", 110), ("LOW2", 55), ("LOW3", 22),
    ]:
        rows.append({"year": 2021, "ticker": ticker, "price": price,
                     "weight": 0.05, "dividend": price * 0.10, "div_yield": 0.10})
    df = pd.DataFrame(rows)

    params = StrategyParams(
        start_year=2021, end_year=2021,
        n_dogs=10, commission=no_commission,
        low5_mode=True, low5_n_first=6,
        min_div_yield=0.0, max_div_yield=0.99,
    )
    result = run_backtest(df, params)

    selected = set(result.annual[0].stocks["ticker"])
    # Из всех 6 берём 5 самых дешёвых по цене 2020
    assert selected == {"HIGH2", "MID1", "LOW1", "LOW2", "LOW3"}, \
        f"Low-5 выбрал {selected}"
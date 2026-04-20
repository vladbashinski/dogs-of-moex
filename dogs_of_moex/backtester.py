"""
backtester.py — реализация стратегии «Собаки Доу» на MOEX.

Методология (без look-ahead bias)
──────────────────────────────────
1. В начале года Y знаем только данные года Y-1.
2. Отбираем топ-N акций по дивидендной доходности года Y-1.
3. Покупаем по цене закрытия года Y-1 (= цена начала года Y).
4. Держим весь год Y.
5. Доходность каждой бумаги за год Y:
       price_ret  = P_Y / P_{Y-1} - 1
       div_ret    = Dividend_Y / P_{Y-1}
       total_ret  = price_ret + div_ret - 2 * commission
6. Ребалансировка в начале следующего года.

Фильтры (необязательные):
  - min_div_yield    : мин. дивдоходность года Y-1 для включения в отбор
  - max_div_yield    : макс. дивдоходность года Y-1 (отсекает аномалии)
  - min_index_weight : мин. вес в индексе на момент отбора (ликвидность)
  - low5_mode        : «Щенки» — из топ-N по доходности берём 5 самых дешёвых
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class StrategyParams:
    start_year:        int   = 2019
    end_year:          int   = 2024
    n_dogs:            int   = 10
    commission:        float = 0.001
    min_div_yield:     float = 0.001
    max_div_yield:     float = 0.99
    min_index_weight:  float = 0.0
    low5_mode:         bool  = False
    low5_n_first:      int   = 10


@dataclass
class YearResult:
    year:             int
    portfolio_return: float
    price_return:     float
    div_return:       float
    n_stocks:         int
    equity_value:     float
    stocks:           pd.DataFrame = field(repr=False)


@dataclass
class BacktestResult:
    params:           StrategyParams
    annual:           list[YearResult]
    equity_curve:     pd.Series
    benchmark_curve:  Optional[pd.Series]
    metrics:          dict[str, float]


def run_backtest(
    df_index:          pd.DataFrame,
    params:            StrategyParams,
    benchmark_returns: Optional[pd.Series] = None,
    risk_free_rates:   Optional[dict[int, float]] = None,
) -> BacktestResult:
    annual_results: list[YearResult] = []
    equity      = 1.0
    equity_dict: dict[int, float] = {params.start_year - 1: 1.0}

    bench_eq                 = 1.0
    bench_dict: dict[int, float] = {}
    bench_has_data           = False

    for year in range(params.start_year, params.end_year + 1):

        # 1. Отбор на основе данных ПРЕДЫДУЩЕГО года
        prev = df_index[
            (df_index["year"] == year - 1) &
            (df_index["div_yield"] >= params.min_div_yield) &
            (df_index["div_yield"] <= params.max_div_yield) &
            (df_index["weight"]    >= params.min_index_weight) &
            (df_index["price"]     >  0)
        ].copy()

        if prev.empty:
            continue

        # 2. Топ-N собак по дивдоходности Y-1
        if params.low5_mode:
            pool = prev.nlargest(params.low5_n_first, "div_yield")
            dogs = pool.nsmallest(5, "price").copy()
        else:
            dogs = prev.nlargest(params.n_dogs, "div_yield").copy()

        dogs = dogs.rename(columns={
            "price":     "price_buy",
            "div_yield": "prev_div_yield",
        })

        # 3. Цена продажи и дивиденды из ТЕКУЩЕГО года
        curr = df_index[df_index["year"] == year][
            ["ticker", "price", "dividend"]
        ].rename(columns={
            "price":    "price_sell",
            "dividend": "dividend_paid",
        })

        dogs = dogs.merge(curr, on="ticker", how="left")
        dogs = dogs.dropna(subset=["price_sell"])
        dogs = dogs[dogs["price_sell"] > 0]

        if dogs.empty:
            continue

        # 4. Доходности
        dogs["price_ret"] = dogs["price_sell"] / dogs["price_buy"] - 1
        dogs["div_ret"]   = dogs["dividend_paid"] / dogs["price_buy"]
        dogs["total_ret"] = dogs["price_ret"] + dogs["div_ret"]

        port_price_ret = float(dogs["price_ret"].mean())
        port_div_ret   = float(dogs["div_ret"].mean())
        port_total_ret = float(dogs["total_ret"].mean()) - 2 * params.commission

        # 5. Equity
        equity *= (1 + port_total_ret)
        equity_dict[year] = round(equity, 6)

        # 6. Бенчмарк
        if benchmark_returns is not None and year in benchmark_returns.index:
            if not bench_has_data:
                bench_dict[year - 1] = 1.0
                bench_has_data = True
            bench_eq *= (1 + float(benchmark_returns[year]))
            bench_dict[year] = round(bench_eq, 6)

        annual_results.append(YearResult(
            year             = year,
            portfolio_return = round(port_total_ret, 6),
            price_return     = round(port_price_ret, 6),
            div_return       = round(port_div_ret, 6),
            n_stocks         = len(dogs),
            equity_value     = equity,
            stocks           = dogs[[
                "ticker", "price_buy", "price_sell",
                "dividend_paid", "prev_div_yield",
                "price_ret", "div_ret", "total_ret",
            ]].copy(),
        ))

    equity_series = pd.Series(equity_dict).sort_index()
    bench_series  = pd.Series(bench_dict).sort_index() if bench_has_data else None

    return BacktestResult(
        params          = params,
        annual          = annual_results,
        equity_curve    = equity_series,
        benchmark_curve = bench_series,
        metrics         = _compute_metrics(annual_results, equity_series, bench_series, risk_free_rates),
    )


def _compute_metrics(
    annual:       list[YearResult],
    equity:       pd.Series,
    bench_equity: Optional[pd.Series],
    rfr:          Optional[dict[int, float]],
) -> dict[str, float]:
    if not annual:
        return {}

    returns = np.array([r.portfolio_return for r in annual])
    years   = [r.year for r in annual]
    n       = len(returns)

    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1)
    cagr         = float((1 + total_return) ** (1 / n) - 1)

    rf_arr  = np.array([rfr.get(y, 0.07) for y in years]) if rfr else np.full(n, 0.07)
    excess  = returns - rf_arr
    exc_std = float(excess.std(ddof=1)) if n > 1 else 0.0
    sharpe  = float(excess.mean() / exc_std) if exc_std > 0 else 0.0

    downside = excess[excess < 0]
    dn_std   = float(downside.std(ddof=1)) if len(downside) > 1 else 0.0
    sortino  = float(excess.mean() / dn_std) if dn_std > 0 else 0.0

    max_drawdown = float(((equity - equity.cummax()) / equity.cummax()).min())
    win_rate     = float((returns > 0).mean())
    avg_div      = float(np.mean([r.div_return for r in annual]))

    metrics: dict[str, float] = {
        "total_return":         round(total_return, 4),
        "cagr":                 round(cagr, 4),
        "sharpe":               round(sharpe, 3),
        "sortino":              round(sortino, 3),
        "max_drawdown":         round(max_drawdown, 4),
        "win_rate":             round(win_rate, 4),
        "avg_div_contribution": round(avg_div, 4),
        "n_years":              n,
        "best_year":            round(float(returns.max()), 4),
        "worst_year":           round(float(returns.min()), 4),
        "avg_annual_return":    round(float(returns.mean()), 4),
        "volatility":           round(float(returns.std(ddof=1)), 4),
    }

    if bench_equity is not None and len(bench_equity) >= 3:
        bench_rets = bench_equity.pct_change().dropna()
        common     = [y for y in years if y in bench_rets.index]
        if len(common) >= 3:
            strat_r = np.array([dict(zip(years, returns))[y] for y in common])
            bench_r = np.array([float(bench_rets[y]) for y in common])
            cov     = np.cov(strat_r, bench_r)
            beta    = float(cov[0, 1] / cov[1, 1]) if cov[1, 1] > 0 else 0.0
            alpha   = float(np.mean(strat_r)) - beta * float(np.mean(bench_r))
            metrics["beta"]  = round(beta, 3)
            metrics["alpha"] = round(alpha, 4)

    return metrics
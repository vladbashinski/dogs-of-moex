"""
backtester.py — реализация стратегии «Собаки Доу» на MOEX.

Методология
───────────
1. На начало года Y отбираются топ-N акций из индекса MOEX
   с наибольшей дивидендной доходностью года Y.
2. Портфель держится весь год (равновзвешенный).
3. Доходность каждой бумаги:
       R_i = (P_{Y+1} / P_Y - 1) + DivYield_Y
   где P_Y — цена на начало Y, DivYield_Y — дивидендная доходность года Y.
4. Портфельная доходность = среднее R_i по всем N бумагам (после комиссий).
5. Следующий год — ребалансировка по тем же правилам.

Фильтры (необязательные):
  - min_div_yield  : нижняя граница дивидендной доходности
  - max_div_yield  : верхняя граница (отсекает аномальные выплаты)
  - min_index_weight : минимальный вес в индексе (ликвидность)
  - low5_mode      : «Щенки» — из топ-N по доходности выбираются 5 самых дешёвых
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


# ──────────────────────────────────────────────────────────────
# Параметры стратегии
# ──────────────────────────────────────────────────────────────

@dataclass
class StrategyParams:
    start_year:        int   = 2019
    end_year:          int   = 2024      # последний год, для которого есть выход
    n_dogs:            int   = 10
    commission:        float = 0.001     # доля от объёма (одна сторона)
    min_div_yield:     float = 0.001     # исключаем нулевых дивидендщиков
    max_div_yield:     float = 0.99      # исключаем экстремальные значения
    min_index_weight:  float = 0.0       # мин. вес в индексе
    low5_mode:         bool  = False     # «Щенки Доу» — 5 самых дешёвых из топ-N
    low5_n_first:      int   = 10        # откуда берутся щенки (обычно топ-10)


# ──────────────────────────────────────────────────────────────
# Результаты
# ──────────────────────────────────────────────────────────────

@dataclass
class YearResult:
    year:             int
    portfolio_return: float
    price_return:     float
    div_return:       float
    n_stocks:         int
    equity_value:     float
    stocks:           pd.DataFrame = field(repr=False)   # детализация по бумагам


@dataclass
class BacktestResult:
    params:           StrategyParams
    annual:           list[YearResult]
    equity_curve:     pd.Series          # индекс = год, значение = стоимость портфеля
    benchmark_curve:  Optional[pd.Series]
    metrics:          dict[str, float]


# ──────────────────────────────────────────────────────────────
# Основной бэктестер
# ──────────────────────────────────────────────────────────────

def run_backtest(
    df_index: pd.DataFrame,
    params: StrategyParams,
    benchmark_returns: Optional[pd.Series] = None,
    risk_free_rates:   Optional[dict[int, float]] = None,
) -> BacktestResult:
    """
    Запускает бэктест Dogs of the Dow на переданных данных.

    df_index должен содержать: year, ticker, price, weight, div_yield
    """
    annual_results: list[YearResult] = []
    equity = 1.0
    equity_dict: dict[int, float] = {params.start_year - 1: 1.0}

    bench_eq   = 1.0
    bench_dict: dict[int, float] = {params.start_year - 1: 1.0}

    for year in range(params.start_year, params.end_year + 1):
        # ── 1. Данные года отбора ──────────────────────────────
        pool = df_index[
            (df_index["year"] == year) &
            (df_index["div_yield"] >= params.min_div_yield) &
            (df_index["div_yield"] <= params.max_div_yield) &
            (df_index["weight"]    >= params.min_index_weight) &
            (df_index["price"]     >  0)
        ].copy()

        if pool.empty:
            continue

        # ── 2. Отбор топ-N «собак» ────────────────────────────
        dogs = pool.nlargest(params.n_dogs, "div_yield").copy()

        # Фильтр «Щенки» (Low-5): из топ-N выбираем 5 дешёвых по цене
        if params.low5_mode:
            source = pool.nlargest(params.low5_n_first, "div_yield")
            dogs   = source.nsmallest(5, "price").copy()

        # ── 3. Цены следующего года для расчёта price return ──
        next_prices = (
            df_index[df_index["year"] == year + 1][["ticker", "price"]]
            .rename(columns={"price": "price_next"})
        )
        dogs = dogs.merge(next_prices, on="ticker", how="left")

        # Бумаги без цены следующего года исключаем (делистинг / выход из индекса)
        dogs = dogs.dropna(subset=["price_next"])
        dogs = dogs[dogs["price_next"] > 0]

        if dogs.empty:
            continue

        # ── 4. Доходности ─────────────────────────────────────
        dogs["price_ret"] = dogs["price_next"] / dogs["price"] - 1
        dogs["total_ret"] = dogs["price_ret"] + dogs["div_yield"]

        port_price_ret = dogs["price_ret"].mean()
        port_div_ret   = dogs["div_yield"].mean()
        port_total_ret = dogs["total_ret"].mean() - 2 * params.commission

        # ── 5. Обновляем equity ───────────────────────────────
        equity *= (1 + port_total_ret)
        equity_dict[year] = round(equity, 6)

        # ── 6. Бенчмарк ───────────────────────────────────────
        if benchmark_returns is not None and year in benchmark_returns.index:
            bench_eq *= (1 + float(benchmark_returns[year]))
            bench_dict[year] = round(bench_eq, 6)

        annual_results.append(YearResult(
            year             = year,
            portfolio_return = round(port_total_ret, 6),
            price_return     = round(port_price_ret, 6),
            div_return       = round(port_div_ret, 6),
            n_stocks         = len(dogs),
            equity_value     = equity,
            stocks           = dogs[["ticker", "price", "price_next",
                                     "div_yield", "price_ret", "total_ret"]].copy(),
        ))

    equity_series = pd.Series(equity_dict).sort_index()
    bench_series  = pd.Series(bench_dict).sort_index() if bench_dict else None

    metrics = _compute_metrics(annual_results, equity_series, bench_series, risk_free_rates)

    return BacktestResult(
        params          = params,
        annual          = annual_results,
        equity_curve    = equity_series,
        benchmark_curve = bench_series,
        metrics         = metrics,
    )


# ──────────────────────────────────────────────────────────────
# Метрики
# ──────────────────────────────────────────────────────────────

def _compute_metrics(
    annual:        list[YearResult],
    equity:        pd.Series,
    bench_equity:  Optional[pd.Series],
    rfr:           Optional[dict[int, float]],
) -> dict[str, float]:
    if not annual:
        return {}

    returns = np.array([r.portfolio_return for r in annual])
    years   = [r.year for r in annual]
    n       = len(returns)

    # CAGR
    total_return = equity.iloc[-1] / equity.iloc[0] - 1
    cagr = (1 + total_return) ** (1 / n) - 1

    # Средний excess return над безрисковой ставкой
    if rfr:
        rf_arr = np.array([rfr.get(y, 0.07) for y in years])
    else:
        rf_arr = np.full(n, 0.07)

    excess = returns - rf_arr
    sharpe = float(excess.mean() / returns.std(ddof=1)) if returns.std(ddof=1) > 0 else 0.0

    # Sortino (downside std только по отрицательным excess)
    downside = excess[excess < 0]
    sortino  = float(excess.mean() / downside.std(ddof=1)) if len(downside) > 1 else 0.0

    # Max drawdown
    peak = equity.cummax()
    dd   = (equity - peak) / peak
    max_drawdown = float(dd.min())

    # Win rate
    win_rate = float((returns > 0).mean())

    # Среднегодовой дивидендный вклад
    avg_div_contribution = float(np.mean([r.div_return for r in annual]))

    metrics = {
        "total_return":         round(total_return, 4),
        "cagr":                 round(cagr, 4),
        "sharpe":               round(sharpe, 3),
        "sortino":              round(sortino, 3),
        "max_drawdown":         round(max_drawdown, 4),
        "win_rate":             round(win_rate, 4),
        "avg_div_contribution": round(avg_div_contribution, 4),
        "n_years":              n,
        "best_year":            round(float(returns.max()), 4),
        "worst_year":           round(float(returns.min()), 4),
        "avg_annual_return":    round(float(returns.mean()), 4),
        "volatility":           round(float(returns.std(ddof=1)), 4),
    }

    # Альфа и бета vs бенчмарк
    if bench_equity is not None and len(bench_equity) >= 3:
        bench_rets = bench_equity.pct_change().dropna()
        common = [y for y in years if y in bench_rets.index]
        if len(common) >= 3:
            strat_r = np.array([dict(zip(years, returns))[y] for y in common])
            bench_r = np.array([bench_rets[y] for y in common])
            cov = np.cov(strat_r, bench_r)
            beta  = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else 0.0
            alpha = float(np.mean(strat_r)) - beta * float(np.mean(bench_r))
            metrics["beta"]  = round(beta, 3)
            metrics["alpha"] = round(alpha, 4)

    return metrics

"""
app.py — Streamlit-приложение «Собаки MOEX».
Бэктест стратегии Dogs of the Dow на Московской бирже (2001–2024).

Запуск:
    streamlit run app.py
"""

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from data_loader import (
    load_index_data,
    get_benchmark_returns,
    get_risk_free_rates,
    clear_benchmark_cache,
)
from backtester import StrategyParams, run_backtest, BacktestResult

# ──────────────────────────────────────────────────────────────
# Конфиг страницы
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Собаки MOEX",
    page_icon="🐕",
    layout="wide",
    initial_sidebar_state="expanded",
)

ACCENT = "#E8272A"     # MOEX red
BENCH  = "#2A7AE8"     # синий для бенчмарка
GREEN  = "#2ECC71"
RED    = "#E74C3C"

# ──────────────────────────────────────────────────────────────
# Кэш загрузки данных
# ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Загрузка данных...")
def _load_all():
    df   = load_index_data()
    rfr  = get_risk_free_rates()
    return df, rfr

@st.cache_data(show_spinner="Получение бенчмарка IMOEX...")
def _load_benchmark(start: int, end: int):
    return get_benchmark_returns(start, end)


# ──────────────────────────────────────────────────────────────
# Хелперы форматирования
# ──────────────────────────────────────────────────────────────
def pct(v: float, digits: int = 1) -> str:
    return f"{v * 100:+.{digits}f}%"

def pct_plain(v: float, digits: int = 1) -> str:
    return f"{v * 100:.{digits}f}%"

def delta_color(v: float) -> str:
    return GREEN if v >= 0 else RED

def metric_card(label: str, value: str, delta: str = "", positive_delta: bool = True) -> None:
    color = GREEN if positive_delta else RED
    st.markdown(
        f"""
        <div style="background:#1E1E2E;border-radius:8px;padding:14px 18px;margin:4px 0;">
            <div style="font-size:12px;color:#888;margin-bottom:4px;">{label}</div>
            <div style="font-size:22px;font-weight:700;color:#FFF;">{value}</div>
            {"<div style='font-size:13px;color:" + color + ";margin-top:2px;'>" + delta + "</div>" if delta else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────
# SIDEBAR — параметры
# ──────────────────────────────────────────────────────────────
def render_sidebar(available_years: list[int]) -> StrategyParams:
    st.sidebar.image(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0b/Moex-logo.svg/1200px-Moex-logo.svg.png",
        width=160,
    )
    st.sidebar.markdown("## ⚙️ Параметры стратегии")

    min_y, max_y = min(available_years), max(available_years) - 1
    col1, col2 = st.sidebar.columns(2)
    start_year = col1.number_input("С года", min_value=min_y, max_value=max_y - 1,
                                   value=max(2019, min_y), step=1)
    end_year   = col2.number_input("По год", min_value=start_year + 1,
                                   max_value=max_y, value=max_y, step=1)

    n_dogs = st.sidebar.slider("Кол-во «собак» (N)", min_value=3, max_value=15, value=10)
    commission = st.sidebar.slider("Комиссия (%, одна сторона)",
                                   min_value=0.0, max_value=1.0, value=0.1, step=0.05) / 100

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔬 Фильтры")

    min_yield = st.sidebar.slider("Мин. дивидендная доходность (%)",
                                  min_value=0.0, max_value=20.0, value=0.1, step=0.1) / 100
    max_yield = st.sidebar.slider("Макс. дивидендная доходность (%)",
                                  min_value=10.0, max_value=100.0, value=99.0, step=1.0) / 100
    min_weight = st.sidebar.slider("Мин. вес в индексе (%)",
                                   min_value=0.0, max_value=5.0, value=0.0, step=0.1) / 100

    low5_mode = st.sidebar.checkbox(
        '🐶 «Щенки Доу» (Low-5)',
        help="Из топ-N по доходности выбрать 5 бумаг с наименьшей ценой акции"
    )

    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Обновить бенчмарк (MOEX API)"):
        clear_benchmark_cache()
        st.cache_data.clear()
        st.rerun()

    return StrategyParams(
        start_year       = int(start_year),
        end_year         = int(end_year),
        n_dogs           = n_dogs,
        commission       = commission,
        min_div_yield    = min_yield,
        max_div_yield    = max_yield,
        min_index_weight = min_weight,
        low5_mode        = low5_mode,
    )


# ──────────────────────────────────────────────────────────────
# TAB 1 — Сводные результаты
# ──────────────────────────────────────────────────────────────
def tab_summary(res: BacktestResult) -> None:
    m = res.metrics
    if not m:
        st.warning("Нет данных за выбранный период.")
        return

    # ── KPI Cards ─────────────────────────────────────────────
    st.markdown("### 📊 Ключевые метрики")
    cols = st.columns(4)
    with cols[0]:
        metric_card("Совокупный доход", pct_plain(m["total_return"]),
                    f"CAGR {pct_plain(m['cagr'])}", m["total_return"] >= 0)
    with cols[1]:
        metric_card("Коэф. Шарпа", f"{m['sharpe']:.2f}",
                    f"Sortino {m['sortino']:.2f}", m["sharpe"] >= 1)
    with cols[2]:
        metric_card("Макс. просадка", pct(m["max_drawdown"]),
                    f"Win rate {pct_plain(m['win_rate'], 0)}", m["max_drawdown"] > -0.3)
    with cols[3]:
        metric_card("Ср. дивидендный вклад", pct_plain(m["avg_div_contribution"]),
                    f"σ {pct_plain(m['volatility'])}", True)

    if "alpha" in m and "beta" in m:
        cols2 = st.columns(4)
        with cols2[0]:
            metric_card("Альфа (vs IMOEX)", pct(m["alpha"]), "", m["alpha"] >= 0)
        with cols2[1]:
            metric_card("Бета (vs IMOEX)", f"{m['beta']:.2f}", "", True)
        with cols2[2]:
            metric_card("Лучший год", pct(m["best_year"]), "", True)
        with cols2[3]:
            metric_card("Худший год", pct(m["worst_year"]), "", m["worst_year"] >= 0)

    # ── Equity Curve ──────────────────────────────────────────
    st.markdown("### 📈 Equity Curve (нормировано к 1)")
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=res.equity_curve.index, y=res.equity_curve.values,
        mode="lines+markers", name="Dogs of MOEX",
        line=dict(color=ACCENT, width=2.5),
        marker=dict(size=6),
        hovertemplate="%{x}: %{y:.3f}<extra>Стратегия</extra>",
    ))

    if res.benchmark_curve is not None and len(res.benchmark_curve) > 1:
        fig.add_trace(go.Scatter(
            x=res.benchmark_curve.index, y=res.benchmark_curve.values,
            mode="lines+markers", name="IMOEX",
            line=dict(color=BENCH, width=2, dash="dot"),
            marker=dict(size=5),
            hovertemplate="%{x}: %{y:.3f}<extra>IMOEX</extra>",
        ))

    fig.update_layout(
        template="plotly_dark", height=420,
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(x=0.02, y=0.98),
        xaxis_title="Год", yaxis_title="Стоимость портфеля",
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Годовые доходности — бар-чарт ─────────────────────────
    st.markdown("### 📊 Годовые доходности")
    years   = [r.year for r in res.annual]
    strat_r = [r.portfolio_return for r in res.annual]

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=years, y=[v * 100 for v in strat_r],
        name="Dogs of MOEX",
        marker_color=[ACCENT if v >= 0 else RED for v in strat_r],
        text=[pct(v) for v in strat_r], textposition="outside",
        hovertemplate="%{x}: %{y:.1f}%<extra>Стратегия</extra>",
    ))

    if res.benchmark_curve is not None:
        bench_rets = res.benchmark_curve.pct_change().dropna()
        bench_common = [(y, bench_rets[y]) for y in years if y in bench_rets.index]
        if bench_common:
            bx, by = zip(*bench_common)
            fig2.add_trace(go.Scatter(
                x=list(bx), y=[v * 100 for v in by],
                mode="lines+markers", name="IMOEX",
                line=dict(color=BENCH, width=2),
                marker=dict(size=7, symbol="diamond"),
                hovertemplate="%{x}: %{y:.1f}%<extra>IMOEX</extra>",
            ))

    fig2.add_hline(y=0, line_dash="dash", line_color="gray", line_width=1)
    fig2.update_layout(
        template="plotly_dark", height=380,
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(x=0.02, y=0.98),
        xaxis_title="Год", yaxis_title="Доходность, %",
        hovermode="x unified", bargap=0.2,
    )
    st.plotly_chart(fig2, use_container_width=True)


# ──────────────────────────────────────────────────────────────
# TAB 2 — Портфели по годам
# ──────────────────────────────────────────────────────────────
def tab_portfolios(res: BacktestResult) -> None:
    st.markdown("### 📋 Состав портфеля по годам")

    years = [r.year for r in res.annual]
    sel_year = st.selectbox("Выберите год", years, index=len(years) - 1)

    yr = next((r for r in res.annual if r.year == sel_year), None)
    if yr is None:
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Доходность портфеля", pct(yr.portfolio_return))
    col2.metric("Прирост цен",         pct(yr.price_return))
    col3.metric("Дивидендный вклад",   pct(yr.div_return))
    col4.metric("Бумаг в портфеле",    str(yr.n_stocks))

    df = yr.stocks.copy()
    df.columns = ["Тикер", "Цена (вход)", "Цена (выход)",
                  "Дивидендная доходность", "Прирост цены", "Итого"]
    for col in ["Дивидендная доходность", "Прирост цены", "Итого"]:
        df[col] = df[col].apply(lambda v: f"{v * 100:.2f}%")
    df["Цена (вход)"]  = df["Цена (вход)"].apply(lambda v: f"{v:,.2f} ₽")
    df["Цена (выход)"] = df["Цена (выход)"].apply(lambda v: f"{v:,.2f} ₽")

    st.dataframe(df, use_container_width=True, hide_index=True)

    # Визуализация дивдоходности по бумагам
    fig = px.bar(
        yr.stocks, x="ticker", y="div_yield",
        color="total_ret",
        color_continuous_scale=["#E74C3C", "#F39C12", "#2ECC71"],
        labels={"ticker": "Тикер", "div_yield": "Дивидендная доходность",
                "total_ret": "Итоговая доходность"},
        title=f"Состав портфеля {sel_year} — дивидендная доходность",
        template="plotly_dark", height=360,
    )
    fig.update_traces(text=(yr.stocks["div_yield"] * 100).round(1).astype(str) + "%",
                      textposition="outside")
    fig.update_layout(margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig, use_container_width=True)

    # Таблица ВСЕХ портфелей
    with st.expander("📄 Все портфели — сводная таблица"):
        rows = []
        for r in res.annual:
            for _, s in r.stocks.iterrows():
                rows.append({
                    "Год":                  r.year,
                    "Тикер":               s["ticker"],
                    "Цена входа":          round(s["price"], 2),
                    "Цена выхода":         round(s["price_next"], 2),
                    "Дивдоходность, %":    round(s["div_yield"] * 100, 2),
                    "Прирост цены, %":     round(s["price_ret"] * 100, 2),
                    "Итого, %":            round(s["total_ret"] * 100, 2),
                })
        full_df = pd.DataFrame(rows)
        st.dataframe(full_df, use_container_width=True, hide_index=True)
        csv = full_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Скачать CSV", csv, "dogs_portfolios.csv", "text/csv")


# ──────────────────────────────────────────────────────────────
# TAB 3 — Аналитика
# ──────────────────────────────────────────────────────────────
def tab_analytics(res: BacktestResult) -> None:
    st.markdown("### 🔬 Анализ стратегии")

    if not res.annual:
        st.info("Нет данных.")
        return

    returns = [r.portfolio_return for r in res.annual]
    years   = [r.year for r in res.annual]

    col1, col2 = st.columns(2)

    # Декомпозиция: цена vs дивиденды
    with col1:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=years, y=[r.price_return * 100 for r in res.annual],
            name="Прирост цены", marker_color=BENCH,
        ))
        fig.add_trace(go.Bar(
            x=years, y=[r.div_return * 100 for r in res.annual],
            name="Дивиденды", marker_color=ACCENT,
        ))
        fig.update_layout(
            barmode="stack", template="plotly_dark", height=340,
            title="Декомпозиция доходности: цена + дивиденды",
            margin=dict(l=0, r=0, t=40, b=0),
            legend=dict(x=0.02, y=0.98),
            yaxis_title="Доходность, %",
        )
        st.plotly_chart(fig, use_container_width=True)

    # Распределение доходностей
    with col2:
        fig2 = px.histogram(
            x=[v * 100 for v in returns],
            nbins=10, template="plotly_dark",
            title="Распределение годовых доходностей",
            labels={"x": "Доходность, %", "count": "Частота"},
            color_discrete_sequence=[ACCENT], height=340,
        )
        fig2.add_vline(x=0, line_dash="dash", line_color="white")
        fig2.add_vline(x=pd.Series(returns).mean() * 100,
                       line_dash="dot", line_color=GREEN,
                       annotation_text=f"Среднее: {pct_plain(pd.Series(returns).mean())}",
                       annotation_position="top right")
        fig2.update_layout(margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig2, use_container_width=True)

    # Тепловая карта: топ бумаги по частоте попадания в портфель
    st.markdown("#### 🏆 Топ-20 акций по частоте в портфеле")
    freq: dict[str, int] = {}
    avg_yield: dict[str, list] = {}
    for r in res.annual:
        for _, s in r.stocks.iterrows():
            t = s["ticker"]
            freq[t] = freq.get(t, 0) + 1
            avg_yield.setdefault(t, []).append(s["total_ret"])

    freq_df = pd.DataFrame([{
        "Тикер":                t,
        "Попаданий в портфель": c,
        "Ср. доходность, %":    round(pd.Series(avg_yield[t]).mean() * 100, 2),
    } for t, c in freq.items()]).sort_values("Попаданий в портфель", ascending=False).head(20)

    fig3 = px.bar(
        freq_df, x="Тикер", y="Попаданий в портфель",
        color="Ср. доходность, %",
        color_continuous_scale=["#E74C3C", "#F39C12", "#2ECC71"],
        template="plotly_dark", height=340,
        title="Частота в портфеле (лет) и средняя доходность",
    )
    fig3.update_layout(margin=dict(l=0, r=0, t=40, b=0))
    st.plotly_chart(fig3, use_container_width=True)

    # Просадка
    st.markdown("#### 📉 Динамика просадки")
    eq = res.equity_curve
    peak = eq.cummax()
    dd   = (eq - peak) / peak * 100

    fig4 = go.Figure()
    fig4.add_trace(go.Scatter(
        x=dd.index, y=dd.values,
        fill="tozeroy", mode="lines",
        line=dict(color=RED, width=1.5),
        fillcolor="rgba(231, 76, 60, 0.25)",
        name="Просадка",
    ))
    fig4.update_layout(
        template="plotly_dark", height=280,
        margin=dict(l=0, r=0, t=10, b=0),
        yaxis_title="Просадка, %",
    )
    st.plotly_chart(fig4, use_container_width=True)


# ──────────────────────────────────────────────────────────────
# TAB 4 — Сырые данные
# ──────────────────────────────────────────────────────────────
def tab_data(df_index: pd.DataFrame, res: BacktestResult) -> None:
    st.markdown("### 🗃️ Исходные данные")

    year_filter = st.multiselect(
        "Фильтр по годам",
        options=sorted(df_index["year"].unique()),
        default=list(range(2019, 2026)),
    )
    display = df_index[df_index["year"].isin(year_filter)].copy()
    display["div_yield_pct"] = (display["div_yield"] * 100).round(2)
    display = display.rename(columns={
        "year": "Год", "ticker": "Тикер", "price": "Цена, ₽",
        "weight": "Вес, %", "dividend": "Дивиденд, ₽",
        "div_yield_pct": "Дивдоходность, %",
    }).drop(columns=["div_yield"])

    st.dataframe(display.sort_values(["Год", "Дивдоходность, %"], ascending=[True, False]),
                 use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("### 📋 Метрики бэктеста")
    if res.metrics:
        metrics_display = {
            "Совокупный доход":           pct_plain(res.metrics["total_return"]),
            "CAGR":                       pct_plain(res.metrics["cagr"]),
            "Коэф. Шарпа":               f"{res.metrics['sharpe']:.3f}",
            "Коэф. Сортино":             f"{res.metrics['sortino']:.3f}",
            "Макс. просадка":            pct(res.metrics["max_drawdown"]),
            "Win Rate":                  pct_plain(res.metrics["win_rate"], 0),
            "Ср. дивидендный вклад":     pct_plain(res.metrics["avg_div_contribution"]),
            "Волатильность (σ)":         pct_plain(res.metrics["volatility"]),
            "Лучший год":                pct(res.metrics["best_year"]),
            "Худший год":                pct(res.metrics["worst_year"]),
            "Альфа (vs IMOEX)":         pct(res.metrics.get("alpha", 0)),
            "Бета (vs IMOEX)":          f"{res.metrics.get('beta', 0):.3f}",
            "Кол-во лет в бэктесте":    str(res.metrics["n_years"]),
        }
        st.table(pd.DataFrame({"Метрика": metrics_display.keys(),
                                "Значение": metrics_display.values()}))


# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────
def main():
    st.markdown(
        """
        <h1 style='margin-bottom:0;'>🐕 Собаки MOEX</h1>
        <p style='color:#888;margin-top:4px;'>
        Бэктест стратегии Dogs of the Dow на Московской бирже
        </p>
        <hr style='margin: 8px 0 16px 0; border-color: #333;'>
        """,
        unsafe_allow_html=True,
    )

    # Загрузка данных
    df_index, rfr = _load_all()
    available_years = sorted(df_index["year"].unique().tolist())

    # Сайдбар
    params = render_sidebar(available_years)

    # Бенчмарк
    with st.spinner("Загрузка IMOEX..."):
        benchmark = _load_benchmark(params.start_year, params.end_year + 1)

    # Бэктест
    result = run_backtest(
        df_index          = df_index,
        params            = params,
        benchmark_returns = benchmark if len(benchmark) > 0 else None,
        risk_free_rates   = rfr,
    )

    if not result.annual:
        st.error("⚠️ Нет данных за выбранный период. Попробуйте изменить параметры.")
        return

    # Инфо-строка
    first_yr = result.annual[0].year
    last_yr  = result.annual[-1].year
    n_total  = sum(r.n_stocks for r in result.annual)
    st.info(
        f"📌 Стратегия: **{params.n_dogs} собак** · "
        f"Период: **{first_yr}–{last_yr}** ({result.metrics['n_years']} лет) · "
        f"Всего позиций открыто: **{n_total}** · "
        f"Комиссия: **{params.commission * 100:.2f}%**"
        + (" · Режим: **🐶 Щенки Доу**" if params.low5_mode else "")
    )

    # Табы
    t1, t2, t3, t4 = st.tabs([
        "📊 Результаты",
        "📋 Портфели по годам",
        "🔬 Аналитика",
        "🗃️ Данные",
    ])
    with t1: tab_summary(result)
    with t2: tab_portfolios(result)
    with t3: tab_analytics(result)
    with t4: tab_data(df_index, result)


if __name__ == "__main__":
    main()

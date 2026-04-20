"""
app.py — Streamlit-интерфейс бэктестера «Собаки Доу» на MOEX.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from data_loader import load_index_data, get_benchmark_returns, get_risk_free_rates
from backtester import run_backtest, StrategyParams

st.set_page_config(
    page_title="Собаки MOEX",
    page_icon="🐕",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.metric-card {
    background: #1e2130; border-radius: 12px;
    padding: 16px 20px; text-align: center;
}
.metric-label { color: #9ca3af; font-size: 13px; margin-bottom: 4px; }
.metric-value { font-size: 26px; font-weight: 700; }
.positive { color: #34d399; }
.negative { color: #f87171; }
.neutral  { color: #93c5fd; }
</style>
""", unsafe_allow_html=True)

# ─── Сайдбар ──────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Параметры")

    st.subheader("🐕 Стратегия")
    n_dogs = st.slider("Количество «собак»", 3, 15, 10,
                        help="Топ-N акций по дивдоходности предыдущего года")
    low5_mode = st.checkbox("Режим «Щенки» (Low-5)",
                             help="Из топ-N выбираем 5 самых дешёвых по цене")

    st.subheader("📅 Период")
    start_year = st.selectbox("Начало", [2019, 2020, 2021, 2022], index=0)
    end_year   = st.selectbox("Конец",  [2022, 2023, 2024],       index=2)
    if end_year <= start_year:
        st.error("Конец должен быть позже начала")
        st.stop()

    st.subheader("🔍 Фильтры")
    min_yield  = st.slider("Мин. дивдоходность, %", 0, 30, 1) / 100
    max_yield  = st.slider("Макс. дивдоходность, %", 10, 100, 99) / 100
    min_weight = st.slider("Мин. вес в индексе, %", 0.0, 5.0, 0.0, 0.1) / 100
    commission = st.slider("Комиссия (одна сторона), %", 0.0, 1.0, 0.1, 0.05) / 100

    st.subheader("💰 Капитал")
    initial_capital = st.number_input(
        "Начальный капитал, ₽",
        min_value=100_000, max_value=100_000_000,
        value=1_000_000, step=100_000, format="%d",
    )

# ─── Загрузка данных ──────────────────────────────────────────
@st.cache_data(show_spinner="Загружаем данные…")
def load_data():
    return load_index_data()

@st.cache_data(show_spinner="Загружаем бенчмарк IMOEX…")
def load_benchmark(sy, ey):
    returns = get_benchmark_returns(sy - 1, ey + 1)
    return None if returns.empty else returns

df_index = load_data()

# ─── Бэктест ──────────────────────────────────────────────────
@st.cache_data(show_spinner="Считаем бэктест…")
def cached_backtest(n_dogs, start_year, end_year, min_yield, max_yield,
                    min_weight, commission, low5_mode):
    params = StrategyParams(
        start_year       = start_year,
        end_year         = end_year,
        n_dogs           = n_dogs,
        commission       = commission,
        min_div_yield    = min_yield,
        max_div_yield    = max_yield,
        min_index_weight = min_weight,
        low5_mode        = low5_mode,
        low5_n_first     = n_dogs,
    )
    return run_backtest(
        df_index,
        params,
        benchmark_returns = load_benchmark(start_year, end_year),
        risk_free_rates   = get_risk_free_rates(),
    )

result = cached_backtest(n_dogs, start_year, end_year, min_yield, max_yield,
                         min_weight, commission, low5_mode)

if not result.annual:
    st.warning("Нет данных для выбранных параметров. Измените фильтры.")
    st.stop()

m = result.metrics

# ─── Заголовок ────────────────────────────────────────────────
st.title("🐕 Собаки Доу — MOEX")
st.caption(
    "Стратегия: каждый год покупаем N акций из индекса MOEX с наибольшей "
    "дивидендной доходностью, держим год, ребалансируемся. "
    "Бенчмарк — IMOEX (индекс Московской Биржи)."
)
st.divider()

# ─── Метрики ──────────────────────────────────────────────────
def card(label, value, suffix="", css="neutral"):
    st.markdown(f"""
    <div class="metric-card">
      <div class="metric-label">{label}</div>
      <div class="metric-value {css}">{value}{suffix}</div>
    </div>""", unsafe_allow_html=True)

def color(v): return "positive" if v >= 0 else "negative"

final_capital = initial_capital * result.equity_curve.iloc[-1]

c1, c2, c3, c4, c5, c6 = st.columns(6)
with c1: card("Итоговый капитал", f"₽{final_capital:,.0f}")
with c2: card("Полная доходность", f"{m['total_return']*100:.1f}", "%", color(m['total_return']))
with c3: card("CAGR", f"{m['cagr']*100:.1f}", "%", color(m['cagr']))
with c4: card("Sharpe", f"{m['sharpe']:.2f}", "", "positive" if m['sharpe'] > 0.5 else "neutral")
with c5: card("Макс. просадка", f"−{abs(m['max_drawdown'])*100:.1f}", "%", "negative")
with c6: card("Лучший год", f"{m['best_year']*100:.1f}", "%", "positive")

st.divider()

# ─── Графики ──────────────────────────────────────────────────
left, right = st.columns([2, 1])

with left:
    st.subheader("Кривая капитала")
    eq = result.equity_curve * initial_capital
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(eq.index), y=list(eq.values),
        name=f"Собаки ({n_dogs} акций)",
        line=dict(color="#34d399", width=2.5),
        fill="tozeroy", fillcolor="rgba(52,211,153,0.07)",
    ))
    if result.benchmark_curve is not None:
        bench_eq = result.benchmark_curve * initial_capital
        # Берём только годы которые есть в обоих кривых
        shared = sorted(set(eq.index) & set(bench_eq.index))
        if shared:
            fig.add_trace(go.Scatter(
                x=shared, y=[bench_eq[y] for y in shared],
                name="IMOEX",
                line=dict(color="#93c5fd", width=2, dash="dash"),
            ))
    fig.update_layout(
        template="plotly_dark", height=340,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=1.08),
        xaxis=dict(dtick=1),
        yaxis=dict(title="₽", tickformat=",.0f"),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Доходность по годам")
    years_list = [r.year for r in result.annual]
    rets = [r.portfolio_return * 100 for r in result.annual]
    fig2 = go.Figure(go.Bar(
        x=years_list, y=rets,
        marker_color=["#34d399" if r >= 0 else "#f87171" for r in rets],
        text=[f"{r:+.1f}%" for r in rets],
        textposition="outside",
    ))
    fig2.add_hline(y=0, line_dash="dot", line_color="gray")
    fig2.update_layout(
        template="plotly_dark", height=340,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(dtick=1), yaxis=dict(title="%"),
        showlegend=False,
    )
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ─── Состав портфелей ─────────────────────────────────────────
st.subheader("📋 Состав портфелей по годам")

for yr in result.annual:
    with st.expander(
        f"**{yr.year}** — "
        f"Итого: {yr.portfolio_return*100:+.1f}%  |  "
        f"Цена: {yr.price_return*100:+.1f}%  |  "
        f"Дивиденды: {yr.div_return*100:+.1f}%  |  "
        f"Акций: {yr.n_stocks}"
    ):
        df_show = yr.stocks.copy()
        df_show.columns = [
            "Тикер", "Цена покупки", "Цена продажи",
            "Дивиденд, ₽", "Дивдоходность (отбор)",
            "Рост цены", "Дивдоходность факт", "Итого",
        ]
        for col in ["Дивдоходность (отбор)", "Рост цены", "Дивдоходность факт", "Итого"]:
            df_show[col] = df_show[col] * 100
        st.dataframe(
            df_show.style.format({
                "Цена покупки":          "{:.2f} ₽",
                "Цена продажи":          "{:.2f} ₽",
                "Дивиденд, ₽":           "{:.2f} ₽",
                "Дивдоходность (отбор)": "{:.1f}%",
                "Рост цены":             "{:+.1f}%",
                "Дивдоходность факт":    "{:+.1f}%",
                "Итого":                 "{:+.1f}%",
            }).background_gradient(
                subset=["Итого"], cmap="RdYlGn", vmin=-50, vmax=100
            ),
            use_container_width=True, hide_index=True,
        )
st.divider()

# ─── Сводные метрики ──────────────────────────────────────────
st.subheader("📊 Сводные метрики")
st.dataframe(pd.DataFrame([
    {"Метрика": "Полная доходность",      "Значение": f"{m['total_return']*100:.1f}%"},
    {"Метрика": "CAGR",                   "Значение": f"{m['cagr']*100:.1f}%"},
    {"Метрика": "Волатильность (σ)",      "Значение": f"{m['volatility']*100:.1f}%"},
    {"Метрика": "Sharpe",                 "Значение": f"{m['sharpe']:.2f}"},
    {"Метрика": "Sortino",                "Значение": f"{m['sortino']:.2f}"},
    {"Метрика": "Max Drawdown",           "Значение": f"{m['max_drawdown']*100:.1f}%"},
    {"Метрика": "Win Rate",               "Значение": f"{m['win_rate']*100:.0f}%"},
    {"Метрика": "Лучший год",             "Значение": f"{m['best_year']*100:.1f}%"},
    {"Метрика": "Худший год",             "Значение": f"{m['worst_year']*100:.1f}%"},
    {"Метрика": "Ср. дивидендный вклад",  "Значение": f"{m['avg_div_contribution']*100:.1f}%"},
]), use_container_width=False, hide_index=True, width=400)

st.divider()
st.caption(
    "Данные: IMOEX (состав индекса) + дивиденды. "
    "Цены = закрытие на конец года. "
    "Результаты прошлого не гарантируют будущей доходности."
)
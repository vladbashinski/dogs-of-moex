"""
app.py — Streamlit-интерфейс бэктестера «Собаки Доу» на MOEX.
Два режима: Исследование (настройка параметров) и Сравнение (4 фикс. сценария).
Поддержка двух бенчмарков: IMOEX (ценовой) и MCFTR (полная доходность).
"""

import io
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from data_loader import (
    load_index_data, get_benchmark, get_risk_free_rates
)
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


# ════════════════════════════════════════════════════════════════
# ОБЩИЕ ФУНКЦИИ
# ════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner="Загружаем данные…")
def load_data():
    return load_index_data()


@st.cache_data(show_spinner="Загружаем бенчмарк…")
def load_benchmark(sy, ey, ticker):
    returns = get_benchmark(ticker, sy - 1, ey + 1)
    return None if returns.empty else returns


def card(label, value, suffix="", css="neutral"):
    st.markdown(f"""
    <div class="metric-card">
      <div class="metric-label">{label}</div>
      <div class="metric-value {css}">{value}{suffix}</div>
    </div>""", unsafe_allow_html=True)


def color(v): return "positive" if v >= 0 else "negative"


df_index = load_data()


# ════════════════════════════════════════════════════════════════
# САЙДБАР — общие параметры (режим + бенчмарк)
# ════════════════════════════════════════════════════════════════

with st.sidebar:
    st.title("⚙️ Режим")
    mode = st.radio(
        "Выберите режим работы",
        ["🔬 Исследование", "📊 Сравнение сценариев"],
        label_visibility="collapsed",
    )
    st.divider()

    st.subheader("📊 Бенчмарк")
    benchmark_ticker = st.radio(
        "Сравнивать с:",
        ["IMOEX", "MCFTR"],
        index=0,
        format_func=lambda x: "IMOEX (ценовой)" if x == "IMOEX"
                               else "MCFTR (полная доходность)",
        help=(
            "IMOEX — ценовой индекс, дивиденды не включает.\n"
            "MCFTR — индекс полной доходности с реинвестированием дивидендов. "
            "Методологически корректнее для сравнения с дивидендной стратегией."
        ),
    )
    st.divider()


# ════════════════════════════════════════════════════════════════
# РЕЖИМ 1: ИССЛЕДОВАНИЕ
# ════════════════════════════════════════════════════════════════

if mode == "🔬 Исследование":

    with st.sidebar:
        st.title("⚙️ Параметры")

        st.subheader("🐕 Стратегия")
        n_dogs = st.slider("Количество «собак»", 3, 15, 10,
                            help="Топ-N акций по дивдоходности предыдущего года")
        low5_mode = st.checkbox("Режим «Щенки» (Low-5)",
                                 help="Из топ-N выбираем 5 самых дешёвых по цене")

        st.subheader("📅 Период")
        start_year = st.selectbox("Начало", [2019, 2020, 2021, 2022], index=0)
        end_year   = st.selectbox("Конец",  [2022, 2023, 2024, 2025], index=3)
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

    @st.cache_data(show_spinner="Считаем бэктест…")
    def cached_backtest(n_dogs, start_year, end_year, min_yield, max_yield,
                        min_weight, commission, low5_mode, benchmark_ticker):
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
            benchmark_returns = load_benchmark(start_year, end_year, benchmark_ticker),
            risk_free_rates   = get_risk_free_rates(),
        )

    result = cached_backtest(n_dogs, start_year, end_year, min_yield, max_yield,
                             min_weight, commission, low5_mode, benchmark_ticker)

    if not result.annual:
        st.warning("Нет данных для выбранных параметров. Измените фильтры.")
        st.stop()

    m = result.metrics
    final_capital = initial_capital * result.equity_curve.iloc[-1]

    bench_label = "IMOEX" if benchmark_ticker == "IMOEX" else "MCFTR (полная доходность)"

    st.title("🐕 Собаки Доу — MOEX")
    st.caption(
        f"Стратегия: каждый год покупаем N акций из индекса MOEX с наибольшей "
        f"дивидендной доходностью, держим год, ребалансируемся. "
        f"Бенчмарк — {bench_label}."
    )
    st.divider()

    # ─── Карточки метрик ──────────────────────────────────────
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1: card("Итоговый капитал", f"₽{final_capital:,.0f}")
    with c2: card("Полная доходность", f"{m['total_return']*100:.1f}", "%", color(m['total_return']))
    with c3: card("CAGR", f"{m['cagr']*100:.1f}", "%", color(m['cagr']))
    with c4: card("Sharpe", f"{m['sharpe']:.2f}", "", "positive" if m['sharpe'] > 0.5 else "neutral")
    with c5: card("Макс. просадка", f"−{abs(m['max_drawdown'])*100:.1f}", "%", "negative")
    with c6: card("Лучший год", f"{m['best_year']*100:.1f}", "%", "positive")

    st.markdown("<div style='margin-top:12px'></div>", unsafe_allow_html=True)
    c7, c8, c9, c10, c11, c12 = st.columns(6)
    with c7:  card("Sortino", f"{m['sortino']:.2f}", "", "positive" if m['sortino'] > 0.5 else "neutral")
    with c8:  card("Calmar", f"{m['calmar']:.2f}", "", "positive" if m['calmar'] > 0.5 else "neutral")
    with c9:  card("Omega", f"{m['omega']:.2f}", "", "positive" if m['omega'] > 1 else "negative")
    with c10: card("Win Rate", f"{m['win_rate']*100:.0f}", "%", "positive" if m['win_rate'] >= 0.5 else "negative")
    with c11: card("Batting Avg", f"{m.get('batting_avg', 0)*100:.0f}", "%", "positive" if m.get('batting_avg', 0) >= 0.5 else "neutral")
    with c12: card("Ср. ставка ЦБ", f"{m.get('avg_rf_rate', 0)*100:.1f}", "%", "neutral")

    st.divider()

    # ─── Графики ──────────────────────────────────────────────
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
            shared = sorted(set(eq.index) & set(bench_eq.index))
            if shared:
                fig.add_trace(go.Scatter(
                    x=shared, y=[bench_eq[y] for y in shared],
                    name=benchmark_ticker,
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

        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            name="Dogs",
            x=years_list,
            y=rets,
            marker_color=["#34d399" if r >= 0 else "#f87171" for r in rets],
            text=[f"{r:+.1f}%" for r in rets],
            textposition="outside",
        ))
        if result.benchmark_curve is not None:
            bench_rets_by_year = result.benchmark_curve.pct_change().dropna()
            bench_vals = [
                round(float(bench_rets_by_year[y]) * 100, 1)
                if y in bench_rets_by_year.index else None
                for y in years_list
            ]
            fig2.add_trace(go.Bar(
                name=benchmark_ticker,
                x=years_list,
                y=bench_vals,
                marker_color="#93c5fd",
                text=[f"{v:+.1f}%" if v is not None else "" for v in bench_vals],
                textposition="outside",
            ))
        fig2.add_hline(y=0, line_dash="dot", line_color="gray")
        fig2.update_layout(
            template="plotly_dark", height=340,
            barmode="group",
            margin=dict(l=10, r=10, t=10, b=10),
            legend=dict(orientation="h", y=1.08),
            xaxis=dict(dtick=1), yaxis=dict(title="%"),
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ─── График ставки ЦБ ─────────────────────────────────────
    st.subheader("📈 Ключевая ставка ЦБ — Reality Check")
    rf = result.rf_curve
    fig_rf = go.Figure()
    if 2022 in rf.index:
        fig_rf.add_vrect(
            x0=2021.5, x1=2022.5,
            fillcolor="rgba(248,113,113,0.12)",
            layer="below", line_width=0,
            annotation_text="Кризис 2022",
            annotation_position="top left",
            annotation_font=dict(color="#f87171", size=11),
        )
    fig_rf.add_trace(go.Scatter(
        x=list(rf.index), y=[v * 100 for v in rf.values],
        name="Ключевая ставка ЦБ",
        line=dict(color="#fbbf24", width=2.5),
        mode="lines+markers", marker=dict(size=7),
        fill="tozeroy", fillcolor="rgba(251,191,36,0.08)",
    ))
    fig_rf.add_trace(go.Scatter(
        x=years_list, y=rets,
        name="Доходность Dogs",
        line=dict(color="#34d399", width=1.5, dash="dot"),
        mode="lines+markers", marker=dict(size=5),
    ))
    fig_rf.add_hline(
        y=float(m.get("avg_rf_rate", 0.07)) * 100,
        line_dash="dash", line_color="rgba(251,191,36,0.4)",
        annotation_text=f"Средняя ставка {m.get('avg_rf_rate', 0)*100:.1f}%",
        annotation_position="right",
    )
    fig_rf.update_layout(
        template="plotly_dark", height=260,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=1.08),
        xaxis=dict(dtick=1), yaxis=dict(title="%", ticksuffix="%"),
        hovermode="x unified",
    )
    st.plotly_chart(fig_rf, use_container_width=True)

    st.divider()

    # ─── Состав портфелей ─────────────────────────────────────
    st.subheader("📋 Состав портфелей по годам")
    for yr in result.annual:
        with st.expander(
            f"**{yr.year}** — "
            f"Итого: {yr.portfolio_return*100:+.1f}%  |  "
            f"Цена: {yr.price_return*100:+.1f}%  |  "
            f"Дивиденды: {yr.div_return*100:+.1f}%  |  "
            f"Ставка ЦБ: {yr.rf_rate*100:.1f}%  |  "
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

    # ─── Сводные метрики ──────────────────────────────────────
    st.subheader("📊 Сводные метрики")
    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("**Доходность и риск**")
        st.dataframe(pd.DataFrame([
            {"Метрика": "Полная доходность",     "Значение": f"{m['total_return']*100:.1f}%"},
            {"Метрика": "CAGR",                  "Значение": f"{m['cagr']*100:.1f}%"},
            {"Метрика": "Волатильность (σ)",     "Значение": f"{m['volatility']*100:.1f}%"},
            {"Метрика": "Max Drawdown",          "Значение": f"{m['max_drawdown']*100:.1f}%"},
            {"Метрика": "Лучший год",            "Значение": f"{m['best_year']*100:.1f}%"},
            {"Метрика": "Худший год",            "Значение": f"{m['worst_year']*100:.1f}%"},
            {"Метрика": "Ср. дивидендный вклад", "Значение": f"{m['avg_div_contribution']*100:.1f}%"},
            {"Метрика": "Ср. ставка ЦБ (MAR)",  "Значение": f"{m.get('avg_rf_rate', 0)*100:.1f}%"},
        ]), use_container_width=True, hide_index=True)
    with col_right:
        st.markdown("**Метрики качества**")
        rows = [
            {"Метрика": "Sharpe Ratio",  "Значение": f"{m['sharpe']:.3f}"},
            {"Метрика": "Sortino Ratio", "Значение": f"{m['sortino']:.3f}"},
            {"Метрика": "Calmar Ratio",  "Значение": f"{m['calmar']:.3f}"},
            {"Метрика": "Omega Ratio",   "Значение": f"{m['omega']:.3f}"},
            {"Метрика": "Win Rate",      "Значение": f"{m['win_rate']*100:.0f}%"},
        ]
        if "batting_avg" in m: rows.append({"Метрика": "Batting Average",   "Значение": f"{m['batting_avg']*100:.0f}%"})
        if "alpha"       in m: rows.append({"Метрика": "Alpha (годовая)",   "Значение": f"{m['alpha']*100:.1f}%"})
        if "beta"        in m: rows.append({"Метрика": "Beta",              "Значение": f"{m['beta']:.3f}"})
        if "info_ratio"  in m: rows.append({"Метрика": "Information Ratio", "Значение": f"{m['info_ratio']:.3f}"})
        if "up_capture"  in m: rows.append({"Метрика": "Upside Capture",    "Значение": f"{m['up_capture']*100:.0f}%"})
        if "down_capture"in m: rows.append({"Метрика": "Downside Capture",  "Значение": f"{m['down_capture']*100:.0f}%"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()
    st.caption(
        f"Данные: IMOEX (состав индекса) + дивиденды. Цены = закрытие на конец года. "
        f"Бенчмарк: {bench_label}. "
        f"Sharpe и Sortino — относительно ключевой ставки ЦБ РФ."
    )


# ════════════════════════════════════════════════════════════════
# РЕЖИМ 2: СРАВНЕНИЕ СЦЕНАРИЕВ
# ════════════════════════════════════════════════════════════════

else:
    bench_label = "IMOEX" if benchmark_ticker == "IMOEX" else "MCFTR (полная доходность)"

    st.title("📊 Сравнение стратегий — Dogs of MOEX")
    st.caption(
        f"Сравнение классической стратегии Dogs of the Dow с тремя модификациями "
        f"на периоде 2019–2025. Бенчмарк: {bench_label}."
    )

    SY, EY, CAP = 2019, 2025, 1_000_000

    SCENARIOS = [
        ("Классика",
         StrategyParams(start_year=SY, end_year=EY, n_dogs=10, commission=0.001,
                        min_div_yield=0.0, max_div_yield=0.99, min_index_weight=0.0,
                        low5_mode=False),
         "10 собак, без фильтров. Базовая стратегия — точка отсчёта."),

        ("Концентрат-5",
         StrategyParams(start_year=SY, end_year=EY, n_dogs=5, commission=0.001,
                        min_div_yield=0.0, max_div_yield=0.99, min_index_weight=0.0,
                        low5_mode=False),
         "5 собак вместо 10. Гипотеза: концентрация повышает доходность."),

        ("Качественные",
         StrategyParams(start_year=SY, end_year=EY, n_dogs=10, commission=0.001,
                        min_div_yield=0.05, max_div_yield=0.25, min_index_weight=0.01,
                        low5_mode=False),
         "Дивдоходность 5–25%, вес в индексе 1%+. Фильтр качества и ликвидности."),

        ("Высокая дивдоходность",
         StrategyParams(start_year=SY, end_year=EY, n_dogs=10, commission=0.001,
                        min_div_yield=0.10, max_div_yield=0.99, min_index_weight=0.0,
                        low5_mode=False),
         "Только акции с дивдоходностью 10%+. Гипотеза: верхний дециль обыгрывает рынок."),
    ]

    @st.cache_data(show_spinner="Считаем 4 стратегии…")
    def run_all_scenarios(benchmark_ticker):
        results = {}
        for name, params, _ in SCENARIOS:
            bench = load_benchmark(params.start_year, params.end_year, benchmark_ticker)
            results[name] = run_backtest(
                df_index, params,
                benchmark_returns=bench,
                risk_free_rates=get_risk_free_rates(),
            )
        return results

    results = run_all_scenarios(benchmark_ticker)

    COLORS = {
        "Классика":              "#93c5fd",
        "Концентрат-5":          "#f87171",
        "Качественные":          "#34d399",
        "Высокая дивдоходность": "#fbbf24",
    }

    # ─── Описание сценариев ────────────────────────────────────
    st.subheader("🎯 Сценарии")
    cols = st.columns(4)
    for i, (name, _, desc) in enumerate(SCENARIOS):
        with cols[i]:
            mr = results[name].metrics
            color_dot = COLORS[name]
            st.markdown(f"""
            <div style="background:#1e2130;padding:14px;border-radius:10px;border-left:4px solid {color_dot}">
              <div style="font-weight:700;font-size:15px;margin-bottom:6px;color:{color_dot}">● {name}</div>
              <div style="font-size:12px;color:#9ca3af;line-height:1.4">{desc}</div>
              <div style="margin-top:10px;font-size:13px;color:#e5e7eb">
                <span style="color:#9ca3af">CAGR:</span> <b style="color:#34d399">{mr['cagr']*100:.1f}%</b> ·
                <span style="color:#9ca3af">DD:</span> <b style="color:#f87171">{mr['max_drawdown']*100:.1f}%</b>
              </div>
            </div>""", unsafe_allow_html=True)

    st.divider()

    # ─── Сводная таблица метрик ────────────────────────────────
    st.subheader("📋 Сводная таблица метрик")

    metric_keys = [
        ("Полная доходность", "total_return", "pct"),
        ("CAGR",              "cagr",         "pct"),
        ("Волатильность",     "volatility",   "pct"),
        ("Max Drawdown",      "max_drawdown", "pct"),
        ("Sharpe",            "sharpe",       "num"),
        ("Sortino",           "sortino",      "num"),
        ("Calmar",            "calmar",       "num"),
        ("Omega",             "omega",        "num"),
        ("Win Rate",          "win_rate",     "pct"),
        ("Batting Avg",       "batting_avg",  "pct"),
        ("Alpha (год)",       "alpha",        "pct_signed"),
        ("Beta",              "beta",         "num"),
        ("Info Ratio",        "info_ratio",   "num"),
        ("Upside Capture",    "up_capture",   "pct"),
        ("Downside Capture",  "down_capture", "pct"),
        ("Лучший год",        "best_year",    "pct"),
        ("Худший год",        "worst_year",   "pct"),
        ("Ср. див. вклад",    "avg_div_contribution", "pct"),
    ]

    table_data = {"Метрика": [lbl for lbl, _, _ in metric_keys]}
    for name, _, _ in SCENARIOS:
        mt = results[name].metrics
        col_data = []
        for _, key, fmt in metric_keys:
            v = mt.get(key)
            if v is None:
                col_data.append("—")
            elif fmt == "pct_signed":
                col_data.append(f"{v*100:+.1f}%")
            elif fmt == "pct":
                col_data.append(f"{v*100:.1f}%")
            else:
                col_data.append(f"{v:.3f}")
        table_data[name] = col_data

    st.dataframe(
        pd.DataFrame(table_data),
        use_container_width=True, hide_index=True, height=680,
    )

    st.divider()

    # ─── Кривые капитала ───────────────────────────────────────
    st.subheader("📈 Кривые капитала")
    fig_eq = go.Figure()
    if 2022 in results["Классика"].rf_curve.index:
        fig_eq.add_vrect(
            x0=2021.5, x1=2022.5,
            fillcolor="rgba(248,113,113,0.10)",
            layer="below", line_width=0,
            annotation_text="Кризис 2022",
            annotation_position="top left",
            annotation_font=dict(color="#f87171", size=11),
        )
    for name, _, _ in SCENARIOS:
        eq = results[name].equity_curve * CAP
        fig_eq.add_trace(go.Scatter(
            x=list(eq.index), y=list(eq.values),
            name=name,
            line=dict(color=COLORS[name], width=2.5),
            mode="lines+markers", marker=dict(size=6),
        ))
    bc = results["Классика"].benchmark_curve
    if bc is not None:
        bench_eq = bc * CAP
        fig_eq.add_trace(go.Scatter(
            x=list(bench_eq.index), y=list(bench_eq.values),
            name=f"{benchmark_ticker} (бенчмарк)",
            line=dict(color="#9ca3af", width=2, dash="dash"),
        ))
    fig_eq.update_layout(
        template="plotly_dark", height=420,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=1.08),
        xaxis=dict(dtick=1),
        yaxis=dict(title="₽", tickformat=",.0f"),
        hovermode="x unified",
    )
    st.plotly_chart(fig_eq, use_container_width=True)

    # ─── Годовая доходность ────────────────────────────────────
    st.subheader("📊 Годовая доходность")
    fig_y = go.Figure()
    for name, _, _ in SCENARIOS:
        ann = results[name].annual
        fig_y.add_trace(go.Bar(
            name=name,
            x=[a.year for a in ann],
            y=[a.portfolio_return * 100 for a in ann],
            marker_color=COLORS[name],
        ))
    fig_y.add_hline(y=0, line_dash="dot", line_color="gray")
    fig_y.update_layout(
        template="plotly_dark", height=360,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", y=1.10),
        xaxis=dict(dtick=1, title="Год"),
        yaxis=dict(title="Доходность, %"),
        barmode="group",
    )
    st.plotly_chart(fig_y, use_container_width=True)

    # ─── Кризис 2022 ───────────────────────────────────────────
    st.subheader("🔻 Поведение в кризис 2022")
    cr_cols = st.columns(4)
    for i, (name, _, _) in enumerate(SCENARIOS):
        with cr_cols[i]:
            yr_2022 = next((a for a in results[name].annual if a.year == 2022), None)
            if yr_2022:
                ret   = yr_2022.portfolio_return * 100
                price = yr_2022.price_return * 100
                div   = yr_2022.div_return * 100
                css   = "positive" if ret >= 0 else "negative"
                st.markdown(f"""
                <div style="background:#1e2130;padding:14px;border-radius:10px;border-left:4px solid {COLORS[name]}">
                  <div style="font-weight:700;color:{COLORS[name]};margin-bottom:8px">{name}</div>
                  <div style="font-size:24px;font-weight:700" class="{css}">{ret:+.1f}%</div>
                  <div style="font-size:12px;color:#9ca3af;margin-top:6px">
                    Цена: {price:+.1f}%<br>Дивиденды: +{div:.1f}%<br>Акций: {yr_2022.n_stocks}
                  </div>
                </div>""", unsafe_allow_html=True)

    st.divider()

    # ─── Экспорт в Excel ───────────────────────────────────────
    st.subheader("⬇️ Экспорт результатов")

    @st.cache_data(show_spinner="Готовим Excel…")
    def build_excel(benchmark_ticker):
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            wb = writer.book
            fmt_pct    = wb.add_format({"num_format": "0.0%"})
            fmt_num    = wb.add_format({"num_format": "0.000"})
            fmt_money  = wb.add_format({"num_format": "#,##0"})
            fmt_header = wb.add_format({
                "bold": True, "bg_color": "#2E5FA3", "font_color": "white",
                "border": 1, "align": "center",
            })

            # Лист 1: Сводная
            df_sum = pd.DataFrame({"Метрика": [lbl for lbl, _, _ in metric_keys]})
            for name, _, _ in SCENARIOS:
                mt = results[name].metrics
                df_sum[name] = [mt.get(k, None) for _, k, _ in metric_keys]
            df_sum.to_excel(writer, sheet_name="Сводная", index=False)
            ws = writer.sheets["Сводная"]
            ws.set_column(0, 0, 28)
            ws.set_column(1, len(SCENARIOS), 18)
            for c in range(len(SCENARIOS) + 1):
                ws.write(0, c, df_sum.columns[c], fmt_header)
            for ri, (_, _, fmt_type) in enumerate(metric_keys, start=1):
                for ci in range(1, len(SCENARIOS) + 1):
                    val = df_sum.iloc[ri - 1, ci]
                    if pd.notna(val):
                        ws.write(ri, ci, val, fmt_pct if "pct" in fmt_type else fmt_num)

            # Лист 2: Доходность по годам
            years_set = sorted({a.year for r in results.values() for a in r.annual})
            df_y = pd.DataFrame({"Год": years_set})
            for name, _, _ in SCENARIOS:
                yr_map = {a.year: a.portfolio_return for a in results[name].annual}
                df_y[name] = [yr_map.get(y) for y in years_set]
            if bc is not None:
                br = bc.pct_change().dropna()
                df_y[benchmark_ticker] = [br.get(y) for y in years_set]
            rf_map = {a.year: a.rf_rate for a in results["Классика"].annual}
            df_y["Ставка ЦБ"] = [rf_map.get(y) for y in years_set]
            df_y.to_excel(writer, sheet_name="Доходность по годам", index=False)
            ws = writer.sheets["Доходность по годам"]
            ws.set_column(0, 0, 8)
            ws.set_column(1, df_y.shape[1] - 1, 18, fmt_pct)
            for c in range(df_y.shape[1]):
                ws.write(0, c, df_y.columns[c], fmt_header)

            # Лист 3: Кривые капитала
            all_yrs = sorted({y for r in results.values() for y in r.equity_curve.index})
            df_eq = pd.DataFrame({"Год": all_yrs})
            for name, _, _ in SCENARIOS:
                ec = results[name].equity_curve * CAP
                df_eq[name] = [ec.get(y) for y in all_yrs]
            if bc is not None:
                bench_eq2 = bc * CAP
                df_eq[benchmark_ticker] = [bench_eq2.get(y) for y in all_yrs]
            df_eq.to_excel(writer, sheet_name="Кривые капитала", index=False)
            ws = writer.sheets["Кривые капитала"]
            ws.set_column(0, 0, 8)
            ws.set_column(1, df_eq.shape[1] - 1, 16, fmt_money)
            for c in range(df_eq.shape[1]):
                ws.write(0, c, df_eq.columns[c], fmt_header)

            # Лист 4: Кризис 2022
            crisis = []
            for name, _, _ in SCENARIOS:
                y22 = next((a for a in results[name].annual if a.year == 2022), None)
                if y22:
                    crisis.append({
                        "Стратегия":      name,
                        "Итого 2022":     y22.portfolio_return,
                        "Вклад цены":     y22.price_return,
                        "Вклад дивов":    y22.div_return,
                        "Акций в портф.": y22.n_stocks,
                        "Ставка ЦБ":      y22.rf_rate,
                    })
            df_cr = pd.DataFrame(crisis)
            df_cr.to_excel(writer, sheet_name="Кризис 2022", index=False)
            ws = writer.sheets["Кризис 2022"]
            ws.set_column(0, 0, 25)
            ws.set_column(1, 5, 16, fmt_pct)
            for c in range(df_cr.shape[1]):
                ws.write(0, c, df_cr.columns[c], fmt_header)

            # Лист 5: Состав портфелей
            rows = []
            for name, _, _ in SCENARIOS:
                for a in results[name].annual:
                    for _, srow in a.stocks.iterrows():
                        rows.append({
                            "Стратегия":       name,
                            "Год":             a.year,
                            "Тикер":           srow["ticker"],
                            "Цена покупки":    srow["price_buy"],
                            "Цена продажи":    srow["price_sell"],
                            "Дивиденд, ₽":     srow["dividend_paid"],
                            "Дивдох. (отбор)": srow["prev_div_yield"],
                            "Рост цены":       srow["price_ret"],
                            "Дивдох. факт":    srow["div_ret"],
                            "Итого":           srow["total_ret"],
                        })
            df_st = pd.DataFrame(rows)
            df_st.to_excel(writer, sheet_name="Состав портфелей", index=False)
            ws = writer.sheets["Состав портфелей"]
            ws.set_column(0, 0, 22); ws.set_column(1, 1, 8)
            ws.set_column(2, 2, 10); ws.set_column(3, 5, 14)
            ws.set_column(6, 9, 14, fmt_pct)
            for c in range(df_st.shape[1]):
                ws.write(0, c, df_st.columns[c], fmt_header)

            # Лист 6: Параметры
            params_rows = []
            for name, params, desc in SCENARIOS:
                params_rows.append({
                    "Стратегия":    name,
                    "Описание":     desc,
                    "Период":       f"{params.start_year}–{params.end_year}",
                    "Собак":        params.n_dogs,
                    "Мин. дивдох.": params.min_div_yield,
                    "Макс. дивдох.":params.max_div_yield,
                    "Мин. вес":     params.min_index_weight,
                    "Комиссия":     params.commission,
                    "Low-5":        "Да" if params.low5_mode else "Нет",
                    "Бенчмарк":     benchmark_ticker,
                })
            df_p = pd.DataFrame(params_rows)
            df_p.to_excel(writer, sheet_name="Параметры", index=False)
            ws = writer.sheets["Параметры"]
            ws.set_column(0, 0, 22); ws.set_column(1, 1, 60)
            ws.set_column(2, 2, 12); ws.set_column(3, 3, 8)
            ws.set_column(4, 7, 14, fmt_pct); ws.set_column(8, 9, 10)
            for c in range(df_p.shape[1]):
                ws.write(0, c, df_p.columns[c], fmt_header)

        return buf.getvalue()

    excel_bytes = build_excel(benchmark_ticker)
    st.download_button(
        label="⬇️ Скачать сравнение в Excel",
        data=excel_bytes,
        file_name=f"dogs_moex_{benchmark_ticker}_{SY}-{EY}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )

    st.caption(
        f"Файл содержит листы: Сводная, Доходность по годам, Кривые капитала, "
        f"Кризис 2022, Состав портфелей, Параметры. Бенчмарк: {bench_label}."
    )
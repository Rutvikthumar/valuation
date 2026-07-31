"""
Ginzu-style FCFF Valuation — generic, any company.

A Streamlit front-end for ginzu_engine.py, a faithful Python port of
Damodaran's fcffsimpleginzu.xlsx. Plug in any company's numbers — nothing
is hardcoded.
"""
import json
import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ginzu_engine import run_ginzu, DEFAULTS

st.set_page_config(page_title="Ginzu Valuation", layout="wide")

DATA_FILE = "ginzu_companies.json"


def load_saved():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {}


def save_all(d):
    with open(DATA_FILE, "w") as f:
        json.dump(d, f, indent=2)


if "ginzu_companies" not in st.session_state:
    st.session_state.ginzu_companies = load_saved()

st.title("🧮 Ginzu-Style FCFF Valuation")
st.caption(
    "A generic Python port of Damodaran's classic fcffsimpleginzu.xlsx template. "
    "Enter any company's numbers — nothing here is pre-set to a specific company. "
    "R&D capitalization, operating-lease conversion, and employee-option value are "
    "out of scope; adjust your inputs for those before entering them here, same as "
    "you would on the spreadsheet's dedicated worksheets."
)

saved = list(st.session_state.ginzu_companies.keys())
load_choice = st.selectbox("Load a saved company (optional)", ["— New valuation —"] + saved)
p = st.session_state.ginzu_companies.get(load_choice, {}) if load_choice != "— New valuation —" else {}

st.subheader("1. Identity & base-year financials")
c1, c2 = st.columns(2)
ticker = c1.text_input("Ticker / short name (used as the save key)", p.get("ticker", ""))
company_name = c2.text_input("Company name", p.get("company_name", ""))

c1, c2, c3, c4 = st.columns(4)
revenue_ltm = c1.number_input("Revenue (LTM)", value=float(p.get("revenue_ltm", 0.0)))
ebit = c2.number_input("EBIT / operating income", value=float(p.get("ebit", 0.0)))
bv_equity = c3.number_input("Book value of equity", value=float(p.get("bv_equity", 0.0)))
bv_debt = c4.number_input("Book value of debt", value=float(p.get("bv_debt", 0.0)))

c1, c2, c3, c4 = st.columns(4)
cash = c1.number_input("Cash & marketable securities", value=float(p.get("cash", 0.0)))
non_op = c2.number_input("Non-operating assets", value=float(p.get("non_operating_assets", 0.0)))
minority = c3.number_input("Minority interests", value=float(p.get("minority_interests", 0.0)))
shares = c4.number_input("Shares outstanding", value=float(p.get("shares", 1.0)))

c1, c2, c3 = st.columns(3)
price = c1.number_input("Current stock price", value=float(p.get("price", 0.0)))
eff_tax = c2.number_input("Effective tax rate", value=float(p.get("eff_tax_rate", 0.20)), format="%.3f")
marg_tax = c3.number_input("Marginal tax rate", value=float(p.get("marginal_tax_rate", 0.25)), format="%.3f")

if revenue_ltm:
    st.info(f"Current pre-tax operating margin (computed) = {ebit / revenue_ltm:.2%}")

st.subheader("2. Growth & margin assumptions")
c1, c2, c3 = st.columns(3)
g_year1 = c1.number_input("Revenue growth, year 1", value=float(p.get("g_year1", 0.05)), format="%.3f")
g_years2_5 = c2.number_input("Revenue growth, years 2-5", value=float(p.get("g_years2_5", p.get("g_year1", 0.05))), format="%.3f")
riskfree_rate = c3.number_input("Risk-free rate (terminal growth default)", value=float(p.get("riskfree_rate", DEFAULTS["riskfree_rate"])), format="%.3f")
terminal_growth_rate = st.number_input("Terminal growth rate (perpetuity, usually = risk-free rate)", value=float(p.get("terminal_growth_rate", riskfree_rate)), format="%.3f")

c1, c2 = st.columns(2)
target_margin = c1.number_input("Target pre-tax operating margin (long-run)", value=float(p.get("target_margin", ebit / revenue_ltm if revenue_ltm else 0.10)), format="%.3f")
margin_convergence_year = c2.number_input("Year margin converges by", value=int(p.get("margin_convergence_year", DEFAULTS["margin_convergence_year"])), step=1)

st.subheader("3. Reinvestment efficiency (sales-to-capital ratio)")
c1, c2 = st.columns(2)
stc_1_5 = c1.number_input("Sales-to-capital, years 1-5", value=float(p.get("sales_to_capital_1_5", DEFAULTS["sales_to_capital_1_5"])))
stc_6_10 = c2.number_input("Sales-to-capital, years 6-10", value=float(p.get("sales_to_capital_6_10", DEFAULTS["sales_to_capital_6_10"])))

st.subheader("4. Cost of capital")
st.caption("Enter your own WACC directly (CAPM: risk-free rate + beta × equity risk premium, plus any country risk premium).")
c1, c2 = st.columns(2)
initial_cost_of_capital = c1.number_input("Initial cost of capital (years 1-5)", value=float(p.get("initial_cost_of_capital", 0.09)), format="%.4f")
terminal_cost_of_capital = c2.number_input("Terminal cost of capital (stable period)", value=float(p.get("terminal_cost_of_capital", riskfree_rate + 0.045)), format="%.4f")

with st.expander("Advanced overrides (optional — spreadsheet defaults used if left as-is)"):
    c1, c2, c3 = st.columns(3)
    nol = c1.number_input("NOL carried into year 1", value=float(p.get("nol_carryforward", 0.0)))
    p_fail = c2.number_input("Probability of failure", value=float(p.get("probability_of_failure", 0.0)), format="%.3f")
    distress_pct = c3.number_input("Distress proceeds, % of value/book", value=float(p.get("distress_proceeds_pct", 0.5)), format="%.2f")
    distress_tied_to = st.selectbox("Distress proceeds tied to", ["V (fair value)", "B (book value)"], index=0 if p.get("distress_tied_to", "V") == "V" else 1)
    keep_eff_tax = st.checkbox("Keep tax rate at effective rate through terminal year (don't converge to marginal)", value=p.get("keep_effective_tax_at_terminal", False))

if st.button("💾 Save & Value", type="primary"):
    if not ticker or not revenue_ltm or not shares:
        st.error("Ticker, revenue, and shares outstanding are required.")
    else:
        rec = dict(
            ticker=ticker, company_name=company_name or ticker,
            revenue_ltm=revenue_ltm, ebit=ebit, bv_equity=bv_equity, bv_debt=bv_debt,
            cash=cash, non_operating_assets=non_op, minority_interests=minority,
            shares=shares, price=price, eff_tax_rate=eff_tax, marginal_tax_rate=marg_tax,
            g_year1=g_year1, g_years2_5=g_years2_5,
            target_margin=target_margin, margin_convergence_year=margin_convergence_year,
            sales_to_capital_1_5=stc_1_5, sales_to_capital_6_10=stc_6_10,
            riskfree_rate=riskfree_rate, terminal_growth_rate=terminal_growth_rate,
            initial_cost_of_capital=initial_cost_of_capital, terminal_cost_of_capital=terminal_cost_of_capital,
            nol_carryforward=nol, probability_of_failure=p_fail, distress_proceeds_pct=distress_pct,
            distress_tied_to=distress_tied_to[0], keep_effective_tax_at_terminal=keep_eff_tax,
        )
        st.session_state.ginzu_companies[ticker] = rec
        save_all(st.session_state.ginzu_companies)
        st.session_state.ginzu_active = ticker
        st.success(f"Saved {ticker}.")

# ───────────────────────── RESULTS ─────────────────────────
active = st.session_state.get("ginzu_active")
tickers = list(st.session_state.ginzu_companies.keys())
if active in tickers or ticker in tickers:
    show = active if active in tickers else ticker
    c = st.session_state.ginzu_companies[show]
    r = run_ginzu(c)

    st.divider()
    st.header(f"Results — {c.get('company_name', show)} ({show})")
    m1, m2, m3 = st.columns(3)
    m1.metric("Estimated value / share", f"{r['value_per_share']:,.2f}")
    m2.metric("Current price", f"{r['price']:,.2f}")
    m3.metric("Price as % of value", f"{(r['price'] / r['value_per_share'] * 100) if r['value_per_share'] else 0:,.1f}%")

    df = pd.DataFrame({
        "Year": r["years"],
        "Revenue growth": [r["growth"][y] for y in r["years"]],
        "Revenue": [r["rev"][y] for y in r["years"]],
        "EBIT margin": [r["margin"][y] for y in r["years"]],
        "EBIT": [r["ebit"][y] for y in r["years"]],
        "EBIT(1-t)": [r["ebit_at"][y] for y in r["years"]],
        "Reinvestment": [r["reinv"][y] for y in r["years"]],
        "FCFF": [r["fcff"][y] for y in r["years"]],
        "Cost of capital": [r["wacc"][y] for y in r["years"]],
        "PV(FCFF)": r["pv_fcff"],
    })
    st.dataframe(
        df.style.format({
            "Revenue growth": "{:.2%}", "Revenue": "{:,.1f}", "EBIT margin": "{:.2%}",
            "EBIT": "{:,.1f}", "EBIT(1-t)": "{:,.1f}", "Reinvestment": "{:,.1f}",
            "FCFF": "{:,.1f}", "Cost of capital": "{:.2%}", "PV(FCFF)": "{:,.1f}",
        }),
        use_container_width=True, hide_index=True,
    )

    st.subheader("Value bridge")
    bridge = pd.DataFrame({
        "Item": ["PV of FCFF, years 1-10", "PV of terminal value", "Value of operating assets",
                 "- Debt", "- Minority interests", "+ Cash", "+ Non-operating assets",
                 "Value of equity", "/ Shares", "Value per share", "Current price", "Upside/(downside)"],
        "Amount": [r["pv_sum"], r["pv_terminal_value"], r["value_ops"],
                   -c["bv_debt"], -c["minority_interests"], c["cash"], c["non_operating_assets"],
                   r["value_equity"], c["shares"], r["value_per_share"], r["price"], r["upside"]],
    })
    st.dataframe(bridge.style.format({"Amount": "{:,.2f}"}), use_container_width=True, hide_index=True)

    fig = go.Figure()
    fig.add_trace(go.Bar(x=[f"Yr{y}" for y in r["years"]], y=[r["fcff"][y] for y in r["years"]], name="FCFF", marker_color="#2F5496"))
    fig.update_layout(title="FCFF by year", height=350)
    st.plotly_chart(fig, use_container_width=True)

    csv = df.to_csv(index=False).encode()
    st.download_button("⬇️ Download projection as CSV", csv, file_name=f"{show}_ginzu_projection.csv")
else:
    st.info("Fill in the inputs above and click **Save & Value** to see results.")

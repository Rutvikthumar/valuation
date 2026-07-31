"""
FCFF Valuation Studio — Streamlit front-end for the Damodaran-style
history-anchored DCF + Monte Carlo engine.

Run locally:   streamlit run app.py
Deploy free:   push this repo to GitHub, then connect it at
               https://share.streamlit.io (Streamlit Community Cloud).
"""
import json
import os

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine import run_dcf, run_mc, get_rev_growth, RFRATE_DEFAULT

st.set_page_config(page_title="FCFF Valuation Studio", layout="wide")

DATA_FILE = "companies.json"


def load_companies():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {}


def save_companies(companies):
    with open(DATA_FILE, "w") as f:
        json.dump(companies, f, indent=2)


if "companies" not in st.session_state:
    st.session_state.companies = load_companies()

st.title("📊 FCFF Valuation Studio")
st.caption(
    "Growth anchored to 3–5yr historical revenue CAGR with mandatory linear "
    "decay to the risk-free rate. Margins are sector benchmarks, not management "
    "guidance. Enter fundamentals yourself — this model deliberately does not "
    "pull management-guided projections."
)

tab_input, tab_results, tab_compare = st.tabs(["➕ Add / Edit Company", "📈 Results", "⚖️ Compare Saved"])

# ───────────────────────── INPUT TAB ─────────────────────────
with tab_input:
    existing = list(st.session_state.companies.keys())
    load_choice = st.selectbox("Load existing company (optional)", ["— New company —"] + existing)
    prefill = st.session_state.companies.get(load_choice, {}) if load_choice != "— New company —" else {}

    st.subheader("Identity")
    c1, c2, c3 = st.columns(3)
    ticker = c1.text_input("Ticker", prefill.get("ticker", ""))
    name = c2.text_input("Company name", prefill.get("name", ""))
    sector = c3.text_input("Sector", prefill.get("sector", ""))

    st.subheader("Base financials (most recent fiscal year, $M unless noted)")
    c1, c2, c3, c4 = st.columns(4)
    revenue = c1.number_input("Revenue", value=float(prefill.get("revenue", 0)))
    current_margin = c2.number_input("Current EBIT margin", value=float(prefill.get("current_margin", 0.15)), format="%.3f")
    interest_expense = c3.number_input("Interest expense", value=float(prefill.get("interest_expense", 0)))
    shares = c4.number_input("Shares outstanding (M)", value=float(prefill.get("shares", 100)))

    c1, c2, c3, c4 = st.columns(4)
    bv_equity = c1.number_input("BV of equity", value=float(prefill.get("bv_equity", 0)))
    bv_debt = c2.number_input("BV of debt", value=float(prefill.get("bv_debt", 0)))
    cash = c3.number_input("Cash & equivalents", value=float(prefill.get("cash", 0)))
    non_op = c4.number_input("Non-operating assets", value=float(prefill.get("non_op", 0)))

    c1, c2, c3 = st.columns(3)
    minority = c1.number_input("Minority interests", value=float(prefill.get("minority", 0)))
    price = c2.number_input("Current stock price ($)", value=float(prefill.get("price", 0.0)))
    eff_tax = c3.number_input("Effective tax rate", value=float(prefill.get("eff_tax", 0.21)), format="%.3f")
    marg_tax = st.number_input("Marginal tax rate (applied by Yr 5+)", value=float(prefill.get("marg_tax", 0.21)), format="%.3f")

    st.subheader("Historical revenue (for the CAGR anchor — most recent last)")
    hist_str = st.text_input(
        "Comma-separated revenue history, e.g. 26490,31350,34860,37900,41530",
        value=",".join(str(x) for x in prefill.get("rev_hist", [])),
    )
    yrs_str = st.text_input(
        "Matching fiscal-year labels, e.g. FY22,FY23,FY24,FY25,FY26",
        value=",".join(prefill.get("rev_hist_yrs", [])),
    )
    rev_hist = [float(x) for x in hist_str.split(",") if x.strip()] if hist_str.strip() else []
    rev_hist_yrs = [x.strip() for x in yrs_str.split(",") if x.strip()]

    cagr_3yr = None
    cagr_5yr = None
    if len(rev_hist) >= 4:
        cagr_3yr = (rev_hist[-1] / rev_hist[-4]) ** (1 / 3) - 1
    if len(rev_hist) >= 6:
        cagr_5yr = (rev_hist[-1] / rev_hist[-6]) ** (1 / 5) - 1
    if cagr_3yr is not None:
        st.info(f"3-yr CAGR (computed): {cagr_3yr:+.1%}" + (f"  |  5-yr CAGR: {cagr_5yr:+.1%}" if cagr_5yr else ""))

    st.subheader("Growth & margin assumptions")
    c1, c2, c3 = st.columns(3)
    g_yr1 = c1.number_input(
        "Year-1 growth used in model (your judgment — usually avg of 3yr/5yr CAGR, haircut for risk)",
        value=float(prefill.get("g_yr1", cagr_3yr or 0.05)), format="%.3f",
    )
    terminal_g = c2.number_input("Terminal growth rate (default = risk-free rate)", value=float(prefill.get("terminal_g", RFRATE_DEFAULT)), format="%.3f")
    margin_yr = c3.number_input("Years to converge to target margin", value=int(prefill.get("margin_yr", 5)), step=1)
    target_margin = st.number_input("Target EBIT margin at convergence", value=float(prefill.get("target_margin", current_margin)), format="%.3f")

    st.subheader("Reinvestment (sales-to-capital ratio) & discount rate")
    c1, c2 = st.columns(2)
    sc_1_5 = c1.number_input("Sales-to-capital, Yrs 1-5", value=float(prefill.get("sc_1_5", 1.5)))
    sc_6_10 = c2.number_input("Sales-to-capital, Yrs 6-10", value=float(prefill.get("sc_6_10", 1.5)))
    c1, c2, c3, c4 = st.columns(4)
    beta = c1.number_input("Beta", value=float(prefill.get("beta", 1.0)))
    erp = c2.number_input("Equity risk premium", value=float(prefill.get("erp", 0.055)), format="%.3f")
    init_wacc = c3.number_input("Initial WACC", value=float(prefill.get("init_wacc", 0.09)), format="%.3f")
    stable_wacc = c4.number_input("Stable-state WACC", value=float(prefill.get("stable_wacc", 0.088)), format="%.3f")

    st.subheader("Monte Carlo standard deviations (uncertainty bands)")
    c1, c2, c3 = st.columns(3)
    mc_std_g = c1.number_input("Std dev — growth", value=float(prefill.get("mc_std_g", 0.02)), format="%.3f")
    mc_std_m = c2.number_input("Std dev — margin", value=float(prefill.get("mc_std_m", 0.015)), format="%.3f")
    mc_std_w = c3.number_input("Std dev — WACC", value=float(prefill.get("mc_std_w", 0.008)), format="%.3f")

    growth_note = st.text_area("Growth note (optional, for your own record)", prefill.get("growth_note", ""))
    margin_note = st.text_area("Margin note (optional)", prefill.get("margin_note", ""))

    if st.button("💾 Save & Value this company", type="primary"):
        if not ticker or not rev_hist or shares == 0:
            st.error("Ticker, revenue history, and shares outstanding are required.")
        else:
            company = dict(
                name=name or ticker, ticker=ticker, sector=sector,
                revenue=revenue, ebit_margin=current_margin, interest_expense=interest_expense,
                bv_equity=bv_equity, bv_debt=bv_debt, cash=cash, non_op=non_op, minority=minority,
                shares=shares, price=price, eff_tax=eff_tax, marg_tax=marg_tax,
                rev_hist=rev_hist, rev_hist_yrs=rev_hist_yrs,
                cagr_3yr=cagr_3yr, cagr_5yr=cagr_5yr, g_yr1=g_yr1, terminal_g=terminal_g,
                current_margin=current_margin, target_margin=target_margin, margin_yr=margin_yr,
                sc_1_5=sc_1_5, sc_6_10=sc_6_10,
                beta=beta, erp=erp, init_wacc=init_wacc, stable_wacc=stable_wacc,
                mc_std_g=mc_std_g, mc_std_m=mc_std_m, mc_std_w=mc_std_w,
                growth_note=growth_note, margin_note=margin_note,
            )
            st.session_state.companies[ticker] = company
            save_companies(st.session_state.companies)
            st.session_state.active_ticker = ticker
            st.success(f"Saved {ticker}. Switch to the Results tab to see the valuation.")

# ───────────────────────── RESULTS TAB ─────────────────────────
with tab_results:
    tickers = list(st.session_state.companies.keys())
    if not tickers:
        st.info("Add a company in the first tab to see results here.")
    else:
        default_idx = tickers.index(st.session_state.get("active_ticker", tickers[0])) if st.session_state.get("active_ticker") in tickers else 0
        sel = st.selectbox("Company", tickers, index=default_idx)
        c = st.session_state.companies[sel]
        res = run_dcf(c)
        n_sim = st.slider("Monte Carlo trials", 1000, 20000, 10000, step=1000)
        mc = run_mc(c, n_sim=n_sim)

        vps, price = res["vps"], c["price"]
        upside = (vps - price) / price if price else 0
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Market price", f"${price:,.2f}")
        m2.metric("Intrinsic value / share", f"${vps:,.2f}", f"{upside:+.1%}")
        m3.metric("ROIC vs WACC spread", f"{(res['roic'] - c['init_wacc']):+.1%}")
        m4.metric("P(undervalued), Monte Carlo", f"{mc['prob_uv']:.1%}")

        st.subheader("10-year FCFF projection")
        years = list(range(1, 11))
        df = pd.DataFrame({
            "Year": years,
            "Revenue growth": [get_rev_growth(c, y) for y in years],
            "Revenue ($M)": [res["rev"][y] for y in years],
            "EBIT margin": [res["mg"][y] for y in years],
            "EBIT ($M)": [res["ebit"][y] for y in years],
            "NOPAT ($M)": [res["nopat"][y] for y in years],
            "FCFF ($M)": [res["fcff"][y] for y in years],
            "PV of FCFF ($M)": res["pv_fcffs"],
        })
        st.dataframe(
            df.style.format({
                "Revenue growth": "{:.1%}", "Revenue ($M)": "{:,.0f}", "EBIT margin": "{:.1%}",
                "EBIT ($M)": "{:,.0f}", "NOPAT ($M)": "{:,.0f}", "FCFF ($M)": "{:,.0f}", "PV of FCFF ($M)": "{:,.0f}",
            }),
            use_container_width=True, hide_index=True,
        )

        st.subheader("Value bridge")
        bridge = pd.DataFrame({
            "Item": ["PV of 10yr FCFFs", "PV of terminal value", "Value of operating assets",
                     "- Debt", "- Minority interest", "+ Cash", "+ Non-operating assets",
                     "Value of equity", "Value per share", "Current price"],
            "$M / $": [res["pv_sum"], res["pv_tv"], res["val_ops"], -c["bv_debt"], -c["minority"],
                       c["cash"], c["non_op"], res["val_eq"], res["vps"], c["price"]],
        })
        st.dataframe(bridge.style.format({"$M / $": "{:,.1f}"}), use_container_width=True, hide_index=True)

        st.subheader(f"Monte Carlo distribution — {n_sim:,} trials")
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=mc["vals"], nbinsx=60, marker_color="#4472C4", name="Simulated intrinsic value"))
        fig.add_vline(x=price, line_color="red", line_dash="dash", annotation_text="Market price")
        fig.add_vline(x=mc["mean"], line_color="green", line_dash="dot", annotation_text="Mean")
        fig.update_layout(xaxis_title="Intrinsic value / share ($)", yaxis_title="Frequency", height=420)
        st.plotly_chart(fig, use_container_width=True)

        st.caption(
            f"Bear P5 ${mc['p5']:.2f}  |  P25 ${mc['p25']:.2f}  |  Median ${mc['median']:.2f}  |  "
            f"P75 ${mc['p75']:.2f}  |  Bull P95 ${mc['p95']:.2f}  |  Std dev ${mc['std']:.2f}"
        )
        if c.get("growth_note"):
            st.info(f"**Growth note:** {c['growth_note']}")
        if c.get("margin_note"):
            st.info(f"**Margin note:** {c['margin_note']}")

        csv = df.to_csv(index=False).encode()
        st.download_button("⬇️ Download projection as CSV", csv, file_name=f"{sel}_fcff_projection.csv")

# ───────────────────────── COMPARE TAB ─────────────────────────
with tab_compare:
    tickers = list(st.session_state.companies.keys())
    if len(tickers) < 1:
        st.info("Add companies to compare them here.")
    else:
        rows = []
        for t in tickers:
            c = st.session_state.companies[t]
            r = run_dcf(c)
            rows.append({
                "Ticker": t, "Name": c["name"], "Price": c["price"],
                "Intrinsic value": r["vps"],
                "Upside": (r["vps"] - c["price"]) / c["price"] if c["price"] else 0,
                "ROIC": r["roic"], "WACC": c["init_wacc"], "EVA ($M)": r["eva"],
            })
        cdf = pd.DataFrame(rows)
        st.dataframe(
            cdf.style.format({"Price": "${:,.2f}", "Intrinsic value": "${:,.2f}", "Upside": "{:+.1%}",
                               "ROIC": "{:.1%}", "WACC": "{:.1%}", "EVA ($M)": "{:,.0f}"}),
            use_container_width=True, hide_index=True,
        )
        if st.button("🗑️ Delete a company"):
            st.session_state.show_delete = True
        if st.session_state.get("show_delete"):
            to_del = st.selectbox("Which one?", tickers, key="del_select")
            if st.button("Confirm delete"):
                del st.session_state.companies[to_del]
                save_companies(st.session_state.companies)
                st.session_state.show_delete = False
                st.rerun()

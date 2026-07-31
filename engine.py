"""
Damodaran FCFF Valuation Engine — History-Anchored, No Guidance
Extracted and cleaned from the original single-file script.

Growth is anchored to 3-5yr historical CAGR with mandatory linear decay
to the terminal (risk-free) rate. Margins are sector benchmarks, not
management guidance. This module is UI-agnostic — the Streamlit app
(app.py) is the only thing that changed; the math is untouched.
"""
import numpy as np

RFRATE_DEFAULT = 0.045  # 10-yr Treasury proxy — override per company if needed


def get_rev_growth(c, yr, n=10):
    """Linear interpolation: g_yr1 -> terminal_g over n years."""
    return c["g_yr1"] + (yr - 1) * (c["terminal_g"] - c["g_yr1"]) / (n - 1)


def get_margin(c, yr):
    if yr <= c["margin_yr"]:
        step = (c["target_margin"] - c["current_margin"]) / c["margin_yr"]
        return c["current_margin"] + yr * step
    return c["target_margin"]


def get_tax(c, yr):
    if yr <= 5:
        return c["eff_tax"]
    step = (c["marg_tax"] - c["eff_tax"]) / 5
    return min(c["eff_tax"] + (yr - 5) * step, c["marg_tax"])


def get_wacc(c, yr):
    if yr <= 5:
        return c["init_wacc"]
    step = (c["init_wacc"] - c["stable_wacc"]) / 5
    return max(c["init_wacc"] - (yr - 5) * step, c["stable_wacc"])


def run_dcf(c, n=10):
    rev = [0] * (n + 2); mg = [0] * (n + 2); ebit = [0] * (n + 2)
    tax = [0] * (n + 2); nopat = [0] * (n + 2); reinv = [0] * (n + 2)
    fcff = [0] * (n + 2); wc = [0] * (n + 2); disc = [0] * (n + 2)
    gr = [0] * (n + 2)

    rev[0] = c["revenue"]; mg[0] = c["current_margin"]; ebit[0] = rev[0] * mg[0]

    for yr in range(1, n + 1):
        gr[yr] = get_rev_growth(c, yr)
        rev[yr] = rev[yr - 1] * (1 + gr[yr])
        mg[yr] = get_margin(c, yr)
        ebit[yr] = rev[yr] * mg[yr]
        tax[yr] = get_tax(c, yr)
        nopat[yr] = ebit[yr] * (1 - tax[yr])
        sc = c["sc_1_5"] if yr <= 5 else c["sc_6_10"]
        reinv[yr] = max(0, (rev[yr] - rev[yr - 1]) / sc) if rev[yr] > rev[yr - 1] else 0
        fcff[yr] = nopat[yr] - reinv[yr]
        wc[yr] = get_wacc(c, yr)
        disc[yr] = (1 / (1 + wc[1])) if yr == 1 else disc[yr - 1] / (1 + wc[yr])

    pv_sum = sum(fcff[yr] * disc[yr] for yr in range(1, n + 1))
    g = c["terminal_g"]; sw = c["stable_wacc"]
    tr = g / sw
    term_rev = rev[n] * (1 + g)
    term_ebit = term_rev * c["target_margin"]
    term_nopat = term_ebit * (1 - c["marg_tax"])
    term_fcff = term_nopat * (1 - tr)
    tv = term_fcff / (sw - g)
    pv_tv = tv * disc[n]
    val_ops = pv_sum + pv_tv
    val_eq = val_ops - c["bv_debt"] - c["minority"] + c["cash"] + c["non_op"]
    vps = val_eq / c["shares"]
    ic = c["bv_equity"] + c["bv_debt"] - c["cash"]
    nopat0 = ebit[0] * (1 - c["eff_tax"])
    roic = nopat0 / ic if ic > 0 else 0
    eva = (roic - c["init_wacc"]) * ic

    return dict(
        rev=rev, mg=mg, ebit=ebit, tax=tax, nopat=nopat, reinv=reinv,
        fcff=fcff, wc=wc, disc=disc, gr=gr,
        pv_fcffs=[fcff[yr] * disc[yr] for yr in range(1, n + 1)],
        pv_sum=pv_sum, tv=tv, pv_tv=pv_tv,
        val_ops=val_ops, val_eq=val_eq, vps=vps,
        ic=ic, roic=roic, eva=eva, nopat0=nopat0,
        term_fcff=term_fcff, term_rev=term_rev, term_ebit=term_ebit,
        term_nopat=term_nopat, term_reinv_rate=tr,
    )


def run_mc(c, n_sim=10000, seed=42):
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_sim):
        cm = c.copy()
        cm["g_yr1"] = rng.normal(c["g_yr1"], c["mc_std_g"])
        cm["target_margin"] = rng.normal(c["target_margin"], c["mc_std_m"])
        cm["init_wacc"] = max(0.04, rng.normal(c["init_wacc"], c["mc_std_w"]))
        cm["stable_wacc"] = max(0.04, rng.normal(c["stable_wacc"], c["mc_std_w"] * 0.7))
        try:
            r = run_dcf(cm)
            v = r["vps"]
            if -500 < v < c["price"] * 15:
                vals.append(v)
        except Exception:
            pass
    vals = np.array(vals)
    return dict(
        vals=vals, mean=np.mean(vals), median=np.median(vals),
        std=np.std(vals), p5=np.percentile(vals, 5), p25=np.percentile(vals, 25),
        p75=np.percentile(vals, 75), p95=np.percentile(vals, 95),
        prob_uv=float(np.mean(vals > c["price"])), n=len(vals),
    )


REQUIRED_FIELDS = [
    "name", "ticker", "sector",
    "revenue", "ebit_margin", "interest_expense",
    "bv_equity", "bv_debt", "cash", "non_op", "minority",
    "shares", "price", "eff_tax", "marg_tax",
    "rev_hist", "rev_hist_yrs", "cagr_3yr", "cagr_5yr", "g_yr1", "terminal_g",
    "current_margin", "target_margin", "margin_yr",
    "sc_1_5", "sc_6_10",
    "beta", "erp", "init_wacc", "stable_wacc",
    "mc_std_g", "mc_std_m", "mc_std_w",
]

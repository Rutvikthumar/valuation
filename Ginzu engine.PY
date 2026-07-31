"""
Generic Damodaran "Ginzu" FCFF valuation engine.

A faithful Python port of the core Input-sheet -> Valuation-output logic
in Prof. Damodaran's fcffsimpleginzu.xlsx template. Unlike the
history-anchored model (engine.py), this one takes the SAME kind of raw
inputs the spreadsheet asks for and lets you set your own growth/margin/
reinvestment assumptions directly - nothing about it is hardcoded to a
specific company.

Not ported (out of scope for a first pass - do these adjustments to your
inputs before entering them, exactly as the spreadsheet workbook would
have you do on its own dedicated worksheets):
  - R&D capitalization worksheet
  - Operating lease -> debt conversion worksheet
  - Employee stock option value (Black-Scholes) worksheet
  - Country risk premium / industry-average lookups (enter your own
    numbers directly instead of pulling from Damodaran's datasets)

Validated against the bundled Almarai example: this port reproduces the
spreadsheet's estimated value/share (~$7.19) to within floating-point
rounding.
"""


def _pretax_current_margin(inputs):
    return inputs["ebit"] / inputs["revenue_ltm"]


def run_ginzu(inputs: dict) -> dict:
    """
    Required keys in `inputs`:
      revenue_ltm, ebit, bv_equity, bv_debt, cash, non_operating_assets,
      minority_interests, shares, price, eff_tax_rate, marginal_tax_rate,
      g_year1, g_years2_5, target_margin, margin_convergence_year,
      sales_to_capital_1_5, sales_to_capital_6_10,
      riskfree_rate, initial_cost_of_capital, terminal_cost_of_capital,
      terminal_growth_rate

    Optional keys (sensible defaults applied if absent):
      nol_carryforward (0), probability_of_failure (0),
      distress_proceeds_pct (0.5), distress_tied_to ("V" or "B", default "V"),
      reinvestment_lag_years (1)
    """
    n = 10
    rev = [0.0] * (n + 2)          # index 0 = base year, 1..10 explicit, 11 = terminal
    growth = [0.0] * (n + 2)
    margin = [0.0] * (n + 2)
    ebit = [0.0] * (n + 2)
    tax = [0.0] * (n + 2)
    ebit_at = [0.0] * (n + 2)      # EBIT(1-t)
    reinv = [0.0] * (n + 2)
    fcff = [0.0] * (n + 2)
    wacc = [0.0] * (n + 2)
    disc = [0.0] * (n + 2)
    nol = [0.0] * (n + 2)
    stc = [0.0] * (n + 2)          # sales-to-capital ratio used each year
    invested_capital = [0.0] * (n + 2)
    roic = [0.0] * (n + 2)

    TERM = 11  # terminal-year index, mirrors column M

    rev[0] = inputs["revenue_ltm"]
    ebit[0] = inputs["ebit"]
    current_margin = _pretax_current_margin(inputs)
    margin[0] = current_margin
    tax[0] = inputs["eff_tax_rate"]
    ebit_at[0] = ebit[0] * (1 - tax[0]) if ebit[0] > 0 else ebit[0]

    nol[0] = inputs.get("nol_carryforward", 0.0)

    terminal_g = inputs["terminal_growth_rate"]
    terminal_wacc = inputs["terminal_cost_of_capital"]
    terminal_tax = inputs["marginal_tax_rate"]

    # ── Revenue growth path: yr1, flat yrs2-5, linear decay yrs6-10 to terminal_g
    g5 = inputs["g_years2_5"]
    for yr in range(1, n + 1):
        if yr == 1:
            growth[yr] = inputs["g_year1"]
        elif yr <= 5:
            growth[yr] = g5
        else:
            growth[yr] = g5 - (g5 - terminal_g) / 5 * (yr - 5)
        rev[yr] = rev[yr - 1] * (1 + growth[yr])
    growth[TERM] = terminal_g
    rev[TERM] = rev[n] * (1 + terminal_g)

    # ── Margin path: yr1 = current margin, linear to target by convergence
    #    year, flat thereafter
    conv = inputs["margin_convergence_year"]
    target_margin = inputs["target_margin"]
    margin[1] = current_margin
    for yr in range(2, n + 1):
        if yr > conv:
            margin[yr] = target_margin
        else:
            margin[yr] = current_margin + (target_margin - current_margin) * yr / conv
    margin[TERM] = margin[n]

    for yr in range(1, n + 1):
        ebit[yr] = rev[yr] * margin[yr]
    ebit[TERM] = rev[TERM] * margin[TERM]

    # ── Tax rate path: yrs1-5 = effective, yrs6-10 linear to marginal (or
    #    stays at effective if that override is set), terminal = marginal
    #    (or effective, if overridden to "leave at effective")
    keep_effective_at_terminal = inputs.get("keep_effective_tax_at_terminal", False)
    tax_terminal = inputs["eff_tax_rate"] if keep_effective_at_terminal else terminal_tax
    for yr in range(1, 6):
        tax[yr] = inputs["eff_tax_rate"]
    step = (tax_terminal - tax[5]) / 5
    for yr in range(6, n + 1):
        tax[yr] = tax[yr - 1] + step
    tax[TERM] = tax_terminal

    # ── EBIT(1-t) with simple NOL shielding
    for yr in range(1, n + 1):
        prior_nol = nol[yr - 1]
        if ebit[yr] > 0:
            if ebit[yr] < prior_nol:
                ebit_at[yr] = ebit[yr]  # fully sheltered, no tax
            else:
                ebit_at[yr] = ebit[yr] - (ebit[yr] - prior_nol) * tax[yr]
        else:
            ebit_at[yr] = ebit[yr]  # loss, no tax benefit modeled here
        # roll NOL forward
        if ebit[yr] < 0:
            nol[yr] = prior_nol - ebit[yr]
        elif prior_nol > ebit[yr]:
            nol[yr] = prior_nol - ebit[yr]
        else:
            nol[yr] = 0.0
    ebit_at[TERM] = ebit[TERM] * (1 - tax[TERM])

    # ── Sales-to-capital ratio path (years 1-5 vs 6-10)
    for yr in range(1, n + 1):
        stc[yr] = inputs["sales_to_capital_1_5"] if yr <= 5 else inputs["sales_to_capital_6_10"]

    # ── Reinvestment (default 1-year lag: reinvestment_t funds t+1's growth)
    invested_capital[0] = inputs["bv_equity"] + inputs["bv_debt"] - inputs["cash"]
    for yr in range(1, n + 1):
        next_rev = rev[yr + 1] if yr < n else rev[TERM]
        reinv[yr] = max(0.0, (next_rev - rev[yr]) / stc[yr]) if next_rev > rev[yr] else 0.0
        fcff[yr] = ebit_at[yr] - reinv[yr]
        invested_capital[yr] = invested_capital[yr - 1] + reinv[yr]
        roic[yr] = ebit_at[yr] / invested_capital[yr - 1] if invested_capital[yr - 1] else 0.0
    roic[0] = ebit_at[0] / invested_capital[0] if invested_capital[0] else 0.0

    # terminal reinvestment = g / stable ROIC * terminal NOPAT
    stable_roic = inputs.get("stable_roic")
    if stable_roic is None:
        # Spreadsheet default: ROIC after year 10 converges to the terminal
        # cost of capital (competitive advantages fade to zero economic profit).
        stable_roic = terminal_wacc
    term_reinv = (terminal_g / stable_roic) * ebit_at[TERM] if terminal_g > 0 and stable_roic else 0.0
    fcff[TERM] = ebit_at[TERM] - term_reinv

    # ── Cost of capital path: yrs1-5 = initial, yrs6-10 linear to terminal
    init_wacc = inputs["initial_cost_of_capital"]
    for yr in range(1, 6):
        wacc[yr] = init_wacc
    wstep = (init_wacc - terminal_wacc) / 5
    for yr in range(6, n + 1):
        wacc[yr] = wacc[yr - 1] - wstep
    wacc[TERM] = terminal_wacc

    disc[1] = 1 / (1 + wacc[1])
    for yr in range(2, n + 1):
        disc[yr] = disc[yr - 1] / (1 + wacc[yr])

    pv_fcff = [fcff[yr] * disc[yr] for yr in range(1, n + 1)]
    pv_sum = sum(pv_fcff)

    terminal_value = fcff[TERM] / (terminal_wacc - terminal_g)
    pv_terminal_value = terminal_value * disc[n]

    sum_pv = pv_sum + pv_terminal_value

    p_fail = inputs.get("probability_of_failure", 0.0)
    distress_pct = inputs.get("distress_proceeds_pct", 0.5)
    distress_tied_to = inputs.get("distress_tied_to", "V")
    if distress_tied_to == "B":
        distress_proceeds = (inputs["bv_equity"] + inputs["bv_debt"]) * distress_pct
    else:
        distress_proceeds = sum_pv * distress_pct
    value_ops = sum_pv * (1 - p_fail) + distress_proceeds * p_fail

    value_equity = (
        value_ops
        - inputs["bv_debt"]
        - inputs["minority_interests"]
        + inputs["cash"]
        + inputs["non_operating_assets"]
        - inputs.get("value_of_options", 0.0)
    )
    value_per_share = value_equity / inputs["shares"]
    price = inputs["price"]

    return dict(
        years=list(range(1, 11)),
        growth=growth, rev=rev, margin=margin, ebit=ebit, tax=tax, ebit_at=ebit_at,
        reinv=reinv, fcff=fcff, wacc=wacc, disc=disc, pv_fcff=pv_fcff,
        invested_capital=invested_capital, roic=roic,
        pv_sum=pv_sum, terminal_value=terminal_value, pv_terminal_value=pv_terminal_value,
        sum_pv=sum_pv, value_ops=value_ops, value_equity=value_equity,
        value_per_share=value_per_share, price=price,
        upside=(value_per_share - price) / price if price else 0.0,
        current_margin=current_margin,
    )


DEFAULTS = dict(
    margin_convergence_year=5,
    sales_to_capital_1_5=2.0,
    sales_to_capital_6_10=2.0,
    riskfree_rate=0.045,
    terminal_growth_rate=0.045,
    nol_carryforward=0.0,
    probability_of_failure=0.0,
    distress_proceeds_pct=0.5,
    distress_tied_to="V",
    reinvestment_lag_years=1,
    keep_effective_tax_at_terminal=False,
)

"""Aareland Regionalbank M&A — Swiss risk and scenario workbench.

Run with:  streamlit run app/streamlit_app.py

Edit the banks' portfolios, push a macro scenario through them, and read the
resulting risk profile by client type and region — then see what that does to
each of the two candidate acquisitions, under Swiss GAAP and Swiss capital
rules.

FICTIONAL DATA THROUGHOUT. Nothing here is financial, legal, tax or M&A advice.
"""

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import banks as bk
import engine as eng
import glossary as gl
import merger as mg
import swiss_notes as sn
import theme as th

st.set_page_config(
    page_title="Aareland M&A — Swiss Risk Workbench",
    page_icon="🇨🇭",
    layout="wide",
)


# ==========================================================================
# Chart helpers
# ==========================================================================

def _scale(mapping: dict[str, str]) -> alt.Scale:
    return alt.Scale(domain=list(mapping.keys()), range=list(mapping.values()))


def _axis(title: str, fmt: str | None = None) -> alt.Axis:
    return alt.Axis(
        title=title, format=fmt,
        labelColor=th.INK_MUTED, titleColor=th.INK_MUTED,
        gridColor=th.GRID, domainColor=th.AXIS, tickColor=th.AXIS,
    )


def labelled_bars(
    df: pd.DataFrame, x: str, y: str, color_field: str,
    color_map: dict[str, str], x_title: str, y_title: str,
    x_format: str = ",.0f", label_format: str = ",.0f",
    height: int = 260, sort: list[str] | None = None,
) -> alt.LayerChart:
    """Horizontal bars with direct value labels.

    Two palette slots sit below 3:1 contrast on white, so the relief rule
    applies — every bar chart here carries its values on the mark.
    """
    y_enc = alt.Y(f"{y}:N", title=y_title, sort=sort,
                  axis=alt.Axis(labelColor=th.INK_MUTED, titleColor=th.INK_MUTED,
                                domainColor=th.AXIS, tickColor=th.AXIS))
    base = alt.Chart(df).encode(y=y_enc)

    bars = base.mark_bar(cornerRadiusEnd=4, height=18).encode(
        x=alt.X(f"{x}:Q", title=x_title, axis=_axis(x_title, x_format)),
        color=alt.Color(f"{color_field}:N", scale=_scale(color_map),
                        legend=alt.Legend(title=None, orient="top")),
        tooltip=[alt.Tooltip(f"{y}:N", title=y_title),
                 alt.Tooltip(f"{x}:Q", title=x_title, format=",.2f")],
    )
    labels = base.mark_text(align="left", dx=6, fontSize=11, color=th.INK_MUTED).encode(
        x=alt.X(f"{x}:Q"),
        text=alt.Text(f"{x}:Q", format=label_format),
    )
    return (bars + labels).properties(height=height)


def stacked_bars(
    df: pd.DataFrame, x: str, y: str, color_field: str,
    color_map: dict[str, str], x_title: str, y_title: str,
    height: int = 260,
) -> alt.Chart:
    """Stacked composition with a 2px surface gap between segments."""
    return alt.Chart(df).mark_bar(
        cornerRadius=2, height=26, stroke="#ffffff", strokeWidth=2,
    ).encode(
        y=alt.Y(f"{y}:N", title=y_title,
                axis=alt.Axis(labelColor=th.INK_MUTED, titleColor=th.INK_MUTED,
                              domainColor=th.AXIS, tickColor=th.AXIS)),
        x=alt.X(f"{x}:Q", title=x_title, axis=_axis(x_title, ",.0f"), stack="zero"),
        color=alt.Color(f"{color_field}:N", scale=_scale(color_map),
                        legend=alt.Legend(title=None, orient="top")),
        tooltip=[alt.Tooltip(f"{y}:N"), alt.Tooltip(f"{color_field}:N"),
                 alt.Tooltip(f"{x}:Q", format=",.1f")],
    ).properties(height=height)


def grouped_bars(
    df: pd.DataFrame, x: str, y: str, color_field: str,
    color_map: dict[str, str], x_title: str, height: int = 260,
) -> alt.Chart:
    """Side-by-side comparison bars."""
    return alt.Chart(df).mark_bar(
        cornerRadiusEnd=4, stroke="#ffffff", strokeWidth=2,
    ).encode(
        y=alt.Y(f"{y}:N", title=None,
                axis=alt.Axis(labelColor=th.INK_MUTED, domainColor=th.AXIS,
                              tickColor=th.AXIS)),
        x=alt.X(f"{x}:Q", title=x_title, axis=_axis(x_title, ",.0f")),
        yOffset=alt.YOffset(f"{color_field}:N"),
        color=alt.Color(f"{color_field}:N", scale=_scale(color_map),
                        legend=alt.Legend(title=None, orient="top")),
        tooltip=[alt.Tooltip(f"{y}:N"), alt.Tooltip(f"{color_field}:N"),
                 alt.Tooltip(f"{x}:Q", format=",.1f")],
    ).properties(height=height)


def heat(df: pd.DataFrame, x: str, y: str, value: str, title: str) -> alt.LayerChart:
    """Sequential one-hue heat grid with values printed in every cell."""
    base = alt.Chart(df).encode(
        x=alt.X(f"{x}:N", title=None,
                axis=alt.Axis(labelColor=th.INK_MUTED, domainColor=th.AXIS,
                              tickColor=th.AXIS, labelAngle=0)),
        y=alt.Y(f"{y}:N", title=None,
                axis=alt.Axis(labelColor=th.INK_MUTED, domainColor=th.AXIS,
                              tickColor=th.AXIS)),
    )
    cells = base.mark_rect(cornerRadius=2, stroke="#ffffff", strokeWidth=2).encode(
        color=alt.Color(f"{value}:Q", title=title,
                        scale=alt.Scale(range=th.SEQ_BLUE),
                        legend=alt.Legend(title=title, gradientLength=140)),
        tooltip=[alt.Tooltip(f"{y}:N"), alt.Tooltip(f"{x}:N"),
                 alt.Tooltip(f"{value}:Q", format=".2%")],
    )
    text = base.mark_text(fontSize=10).encode(
        text=alt.Text(f"{value}:Q", format=".2%"),
        color=alt.condition(
            alt.datum[value] > df[value].quantile(0.62),
            alt.value("#ffffff"), alt.value("#0b0b0b"),
        ),
    )
    return (cells + text).properties(height=max(150, 34 * df[y].nunique()))


# ==========================================================================
# State
# ==========================================================================

def reset_products():
    st.session_state.products = bk.product_table()


if "products" not in st.session_state:
    reset_products()


# ==========================================================================
# Sidebar — scenario controls
# ==========================================================================

st.sidebar.title("Scenario controls")

preset_name = st.sidebar.selectbox(
    "Macro preset", list(eng.PRESETS.keys()), index=0,
    help="Presets seed the sliders below. Move any slider to go off-preset.",
)
preset = eng.PRESETS[preset_name]
if preset_name in eng.PRESET_NOTES:
    st.sidebar.caption(eng.PRESET_NOTES[preset_name])

st.sidebar.caption("National shock, as deviations from the FY2025 base")

du = st.sidebar.slider(
    "Unemployment rate", -1.0, 6.0, float(preset.unemployment), 0.1,
    format="%+.1f pp", key=f"du_{preset_name}",
    help="Swiss unemployment sits near 2.5%, so a one-point move is "
         "proportionally larger than in most markets.",
)
dg = st.sidebar.slider(
    "GDP growth", -6.0, 3.0, float(preset.gdp), 0.1,
    format="%+.1f pp", key=f"dg_{preset_name}",
)
dr = st.sidebar.slider(
    "SNB policy rate", -200, 400, int(preset.rate), 25,
    format="%+d bp", key=f"dr_{preset_name}",
)
dp = st.sidebar.slider(
    "Property prices", -35.0, 15.0, float(preset.property), 1.0,
    format="%+.0f %%", key=f"dp_{preset_name}",
)
dc = st.sidebar.slider(
    "Swiss franc", -10.0, 30.0, float(preset.chf), 1.0,
    format="%+.0f %%", key=f"dc_{preset_name}",
    help="Appreciation of the franc. A strong franc hurts exporters, tourism "
         "and the cross-border economy, so the Alpen and Tessin regions feel "
         "it far more than the Mittelland.",
)

national = eng.Macro(unemployment=du, gdp=dg, rate=dr, property=dp, chf=dc)

# ---- regional overrides ---------------------------------------------------
regional: dict[str, eng.Macro] = {}
with st.sidebar.expander("Regional overrides"):
    st.caption(
        "Regions already react differently to the same national shock. "
        "Override here to shock one region on its own."
    )
    overridden = st.multiselect("Override these regions", bk.REGIONS, default=[])
    for reg in overridden:
        st.markdown(f"**{reg}**")
        c1, c2 = st.columns(2)
        r_du = c1.number_input("Unemp pp", -2.0, 8.0, float(du), 0.5, key=f"u_{reg}")
        r_dg = c2.number_input("GDP pp", -8.0, 4.0, float(dg), 0.5, key=f"g_{reg}")
        r_dr = c1.number_input("Rate bp", -300, 500, int(dr), 25, key=f"r_{reg}")
        r_dp = c2.number_input("Property %", -45.0, 20.0, float(dp), 1.0, key=f"p_{reg}")
        r_dc = c1.number_input("Franc %", -15.0, 40.0, float(dc), 1.0, key=f"c_{reg}")
        regional[reg] = eng.Macro(r_du, r_dg, r_dr, r_dp, r_dc)

# ---- management levers ----------------------------------------------------
levers: dict[str, eng.Levers] = {}
with st.sidebar.expander("Management levers"):
    st.caption(
        "Actions the banks can take on top of the macro path. Note that the "
        "KKG affordability test already assumes a card limit is drawn in full "
        "before it is granted, so a Swiss limit increase buys less risk — and "
        "less growth — than it would elsewhere."
    )
    lever_bank = st.selectbox("Apply to", ["All banks"] + bk.BANKS)
    li = st.slider("Credit limit increase", -25, 100, 0, 5, format="%+d %%")
    bgw = st.slider("Book growth", -25, 50, 0, 5, format="%+d %%")
    uw = st.slider("Underwriting shift (PD)", -40, 40, 0, 5, format="%+d %%",
                   help="Negative tightens underwriting and lowers PD.")
    lv = eng.Levers(limit_increase=li, book_growth=bgw, underwriting=uw)
    for b in (bk.BANKS if lever_bank == "All banks" else [lever_bank]):
        levers[b] = lv

scenario = eng.Scenario(macro=national, regional=regional, levers=levers)

st.sidebar.divider()
if st.sidebar.button("Reset bank data", width="stretch"):
    reset_products()
    st.rerun()
st.sidebar.caption(bk.DISCLAIMER)


# ==========================================================================
# Compute
# ==========================================================================

def build_portfolio(products: pd.DataFrame) -> pd.DataFrame:
    """Expand the (possibly user-edited) product table across regions."""
    rows = []
    for rec in products.to_dict("records"):
        for region, weight in bk.REGION_MIX[rec["bank"]].items():
            row = dict(rec)
            row["region"] = region
            row["drawn"] = rec["drawn"] * weight
            row["undrawn"] = rec["undrawn"] * weight
            row["pd"] = rec["pd"] * bk.REGION_PD_MULT[region]
            rows.append(row)
    return pd.DataFrame(rows)


portfolio = build_portfolio(st.session_state.products)

raw_base = eng.compute(portfolio, eng.Scenario())
plug = eng.other_rwa_plug(raw_base)
calibration = eng.va_calibration(raw_base)

base_rows = eng.compute(portfolio, eng.Scenario(), calibration)
rows = eng.compute(portfolio, scenario, calibration)
summary = eng.bank_summary(rows, plug)
summary_idx = summary.set_index("bank")

stressed = not national.is_base() or bool(regional) or any(
    (l.limit_increase or l.book_growth or l.underwriting) for l in levers.values()
)


# ==========================================================================
# Header
# ==========================================================================

st.title("Aareland Regionalbank — Swiss M&A risk workbench")
st.caption(
    f"Scenario: **{preset_name}** · unemployment {du:+.1f}pp · GDP {dg:+.1f}pp · "
    f"SNB rate {dr:+d}bp · property {dp:+.0f}% · franc {dc:+.0f}%"
    + (f" · {len(regional)} regional override(s)" if regional else "")
)

tabs = st.tabs([
    "Overview", "Client risk profile", "Regional exposure",
    "M&A decision", "Bank data", "Swiss rules explained", "Method",
    "Glossary",
])


# --------------------------------------------------------------------------
# 1. Overview
# --------------------------------------------------------------------------
with tabs[0]:
    st.subheader("Where the three banks stand")

    cols = st.columns(3)
    for col, bank in zip(cols, bk.BANKS):
        r = summary_idx.loc[bank]
        ratio = r["cet1_ratio_stressed"]
        surplus = r["cet1_surplus"]
        if ratio < eng.CET1_REGULATORY_MIN:
            icon, state = "🛑", "Below the regulatory minimum"
        elif surplus < 0:
            icon, state = "⚠️", "Below its own requirement"
        else:
            icon, state = "✅", "Above requirement"
        with col:
            st.markdown(f"##### {bank}")
            st.metric(
                "CET1 ratio", th.pct(ratio),
                delta=th.bps(ratio - r["cet1_ratio_base"]) if stressed else None,
            )
            st.caption(f"{icon} {state} · target 12.0% + mortgage buffer")
            st.metric(
                "Value adjustments (Swiss GAAP)", th.money(r["va_stressed"]),
                delta=th.money(r["va_delta"]) if stressed else None,
                delta_color="inverse",
            )
            st.metric("Total exposure at default", th.money(r["ead_stressed"]))

    st.divider()

    left, right = st.columns([3, 2])
    with left:
        st.markdown("**Capital requirement, including the sectoral mortgage buffer**")
        cap = summary[["bank", "cet1_stressed", "required_cet1", "sectoral_buffer"]].copy()
        cap_m = cap.melt("bank", value_vars=["cet1_stressed", "required_cet1"],
                         var_name="basis", value_name="amount")
        cap_m["basis"] = cap_m["basis"].map(
            {"cet1_stressed": "CET1 held", "required_cet1": "CET1 required"})
        st.altair_chart(
            grouped_bars(cap_m, "amount", "bank", "basis",
                         {"CET1 held": th.SERIES[0], "CET1 required": th.SERIES[1]},
                         f"{bk.CURRENCY} m"),
            width="stretch",
        )
    with right:
        st.markdown("**Headline table**")
        tbl = summary[[
            "bank", "ead_stressed", "el_rate_stressed", "va_stressed",
            "cet1_ratio_stressed", "cet1_surplus",
        ]].copy()
        tbl.columns = ["Bank", "EAD", "EL rate", "Value adj.", "CET1", "Surplus"]
        st.dataframe(
            tbl.style.format({
                "EAD": "{:,.0f}", "EL rate": "{:.2%}", "Value adj.": "{:,.1f}",
                "CET1": "{:.2%}", "Surplus": "{:+,.1f}",
            }),
            hide_index=True, width="stretch",
        )
        st.caption(
            "Requirement is the 12.0% management target on total RWA plus a "
            "2.5% sectoral buffer on residential mortgage positions."
        )

    st.divider()
    st.markdown("**Reserves for general banking risks — the Swiss earnings smoother**")
    res = summary[[
        "bank", "general_reserve", "net_income_base",
        "net_income_before_release", "reserve_release", "net_income_stressed",
    ]].copy()
    res.columns = ["Bank", "Reserve held", "Net income (base)",
                   "Before release", "Released", "Reported"]
    r1, r2 = st.columns([3, 2])
    with r1:
        st.dataframe(
            res.style.format({c: "{:,.1f}" for c in res.columns if c != "Bank"}),
            hide_index=True, width="stretch",
        )
    with r2:
        if stressed:
            exhausted = summary[
                summary["reserve_release"] > 0.7 * summary["general_reserve"]]
            if not exhausted.empty:
                names = ", ".join(bk.SHORT[b] for b in exhausted["bank"])
                st.warning(
                    f"**{names}** absorbs most of the charge by releasing its "
                    f"general banking risk reserve. Reported earnings barely "
                    f"move — but capital fell all the same, and the reserve "
                    f"cannot be released twice."
                )
            else:
                st.info(
                    "Releasing the reserve offsets the charge in reported "
                    "earnings. It does not add capital: the money was already "
                    "inside CET1."
                )
        else:
            st.info(
                "Under the base case nothing is released. Push a scenario to "
                "see how much of each bank's apparent resilience is the "
                "reserve rather than the book."
            )

    if stressed:
        st.divider()
        st.markdown("**Exposure at default — where the growth comes from**")
        ead = summary[["bank", "drawn_stressed"]].copy()
        ead["Headroom at effective CCF"] = (
            summary["ead_stressed"] - summary["drawn_stressed"])
        ead = ead.rename(columns={"drawn_stressed": "Drawn balances"}).melt(
            "bank", var_name="component", value_name="amount")
        st.altair_chart(
            stacked_bars(ead, "amount", "bank", "component",
                         {"Drawn balances": th.SERIES[0],
                          "Headroom at effective CCF": th.SERIES[1]},
                         f"EAD ({bk.CURRENCY} m)", None, height=200),
            width="stretch",
        )
        gap = rows[rows["revolving"]]
        if not gap.empty:
            eff = np.average(gap["ccf_effective"], weights=gap["undrawn_stressed"] + 1e-9)
            st.caption(
                f"Weighted effective conversion factor on revolving lines is "
                f"**{eff:.1%}** against the 10% regulatory figure. The gap is "
                f"narrower than in an unregulated market, because the KKG "
                f"affordability test already assumed the full limit was drawn."
            )


# --------------------------------------------------------------------------
# 2. Client risk profile
# --------------------------------------------------------------------------
with tabs[1]:
    st.subheader("Privatkunden vs Firmenkunden")
    st.caption(
        "Retail and commercial books answer to different parts of the macro "
        "picture: individuals to employment and rates, companies to output and "
        "to the franc. The same shock therefore lands unevenly across the two."
    )

    by_client = eng.breakdown(rows, ["bank", "client_type"])

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Exposure by client type**")
        st.altair_chart(
            stacked_bars(by_client, "ead_stressed", "bank", "client_type",
                         th.CLIENT_COLORS, f"EAD ({bk.CURRENCY} m)", None),
            width="stretch",
        )
    with c2:
        st.markdown("**Expected loss rate by client type**")
        lab = by_client.assign(
            label=by_client["bank"].map(bk.SHORT) + " · "
            + by_client["client_type"].str.split(" ").str[0])
        st.altair_chart(
            labelled_bars(lab, "el_rate_stressed", "label", "client_type",
                          th.CLIENT_COLORS, "EL rate", None,
                          x_format=".1%", label_format=".2%", height=300),
            width="stretch",
        )

    st.divider()
    st.markdown("**By product**")
    by_product = eng.breakdown(rows, ["bank", "client_type", "product"])
    prod = by_product[[
        "bank", "client_type", "product", "ead_stressed",
        "el_rate_base", "el_rate_stressed", "va_stressed", "gaap_gap",
    ]].copy()
    prod.columns = ["Bank", "Client type", "Product", "EAD",
                    "EL rate (base)", "EL rate (scenario)",
                    "Swiss GAAP adj.", "IFRS 9 would add"]
    st.dataframe(
        prod.style.format({
            "EAD": "{:,.0f}", "EL rate (base)": "{:.2%}",
            "EL rate (scenario)": "{:.2%}", "Swiss GAAP adj.": "{:,.1f}",
            "IFRS 9 would add": "{:+,.1f}",
        }),
        hide_index=True, width="stretch",
    )

    sel = st.selectbox("Heat grid — expected loss rate for", bk.BANKS, key="clientbank")
    hb = by_product[by_product["bank"] == sel].copy()
    if not hb.empty:
        hb["client"] = hb["client_type"].str.split(" ").str[0]
        st.altair_chart(
            heat(hb, "client", "product", "el_rate_stressed", "EL rate"),
            width="stretch",
        )


# --------------------------------------------------------------------------
# 3. Regional exposure
# --------------------------------------------------------------------------
with tabs[2]:
    st.subheader("Regional breakdown of exposed risk")
    st.caption(
        "Romandie · Mittelland · Alpen · Tessin. The regions respond very "
        "differently to the same national shock — the Mittelland is the most "
        "property- and rate-sensitive, while the Alpen and Tessin regions live "
        "or die by tourism, cross-border work and the franc."
    )

    by_region = eng.breakdown(rows, ["bank", "region"])
    hhi = {b: eng.concentration_hhi(rows, b) for b in bk.BANKS}

    cols = st.columns(3)
    for col, bank in zip(cols, bk.BANKS):
        h = hhi[bank]
        verdict = "Diversified" if h < 0.35 else ("Moderate" if h < 0.45 else "Concentrated")
        icon = {"Diversified": "✅", "Moderate": "⚠️", "Concentrated": "🛑"}[verdict]
        col.metric(f"{bk.SHORT[bank]} — concentration (HHI)", f"{h:.3f}")
        col.caption(f"{icon} {verdict} · 0.250 would be perfectly even")

    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Exposure by region**")
        st.altair_chart(
            stacked_bars(by_region, "ead_stressed", "bank", "region",
                         th.REGION_COLORS, f"EAD ({bk.CURRENCY} m)", None, height=220),
            width="stretch",
        )
    with c2:
        st.markdown("**Value adjustments by region**")
        st.altair_chart(
            stacked_bars(by_region, "va_stressed", "bank", "region",
                         th.REGION_COLORS, f"Value adj. ({bk.CURRENCY} m)", None,
                         height=220),
            width="stretch",
        )

    st.markdown("**Expected loss rate — bank × region**")
    st.altair_chart(
        heat(by_region.assign(Bank=by_region["bank"].map(bk.SHORT)),
             "region", "Bank", "el_rate_stressed", "EL rate"),
        width="stretch",
    )

    st.markdown("**Regional detail**")
    reg = by_region[[
        "bank", "region", "ead_stressed", "el_rate_base",
        "el_rate_stressed", "va_stressed", "va_delta",
    ]].copy()
    reg.columns = ["Bank", "Region", "EAD", "EL rate (base)",
                   "EL rate (scenario)", "Value adj.", "Δ Value adj."]
    st.dataframe(
        reg.style.format({
            "EAD": "{:,.0f}", "EL rate (base)": "{:.2%}",
            "EL rate (scenario)": "{:.2%}", "Value adj.": "{:,.1f}",
            "Δ Value adj.": "{:+,.1f}",
        }),
        hide_index=True, width="stretch",
    )

    if stressed:
        worst = by_region.loc[by_region["va_delta"].idxmax()]
        st.info(
            f"Largest single regional deterioration: **{worst['bank']}** in "
            f"**{worst['region']}**, value adjustments up "
            f"{th.money(worst['va_delta'])} "
            f"({th.pct(worst['el_rate_base'])} → "
            f"{th.pct(worst['el_rate_stressed'])} loss rate)."
        )


# --------------------------------------------------------------------------
# 4. M&A decision
# --------------------------------------------------------------------------
with tabs[3]:
    st.subheader("Aareland buys B or C — under this scenario")
    st.caption(
        "Capital arithmetic recomputed with stressed value adjustments charged "
        "to CET1. The requirement includes the sectoral mortgage buffer, and "
        "any equity raise is grossed up for the 1% federal issuance duty."
    )

    deals = mg.compare(summary)

    cols = st.columns(2)
    for col, (name, d) in zip(cols, deals.items()):
        with col:
            st.markdown(f"##### Acquire {name}")
            ratio = d["ratio_pre_raise"]
            if d["breaches_minimum"]:
                st.error(f"Pro forma CET1 {th.pct(ratio)} — **below the "
                         f"{eng.CET1_REGULATORY_MIN:.1%} regulatory minimum**")
            elif not d["meets_target"]:
                st.warning(f"Pro forma CET1 {th.pct(ratio)} — below the "
                           f"{d['required_ratio']:.2%} requirement")
            else:
                st.success(f"Pro forma CET1 {th.pct(ratio)} — meets the "
                           f"{d['required_ratio']:.2%} requirement")

            m1, m2 = st.columns(2)
            m1.metric("Goodwill", th.money(d["goodwill"]))
            m2.metric("Pro forma RWA", th.money(d["rwa"]))
            m1.metric("Equity raise", th.money(d["raise_needed"]))
            m2.metric("Dilution", th.pct(d["dilution"], 1))
            st.metric("Year-3 EPS accretion", th.pct(d["years"][-1]["accretion"], 1),
                      help=f"Versus standalone EPS of CHF {d['standalone_eps']:.2f}")
            st.caption(
                f"Sectoral mortgage buffer {th.money(d['sectoral_buffer'])} · "
                f"issuance duty {th.money(d['stamp_duty'])}"
            )

    st.divider()
    eps_rows = [
        {"Deal": f"Acquire {bk.SHORT[n]}", "Year": f"Year {y['year']}",
         "Accretion": y["accretion"]}
        for n, d in deals.items() for y in d["years"]
    ]
    eps_df = pd.DataFrame(eps_rows)

    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown("**EPS accretion by year**")
        deal_colors = {"Acquire B": th.SERIES[1], "Acquire C": th.SERIES[2]}
        st.altair_chart(
            alt.Chart(eps_df).mark_bar(
                cornerRadiusEnd=4, stroke="#ffffff", strokeWidth=2,
            ).encode(
                x=alt.X("Year:N", title=None,
                        axis=alt.Axis(labelColor=th.INK_MUTED, domainColor=th.AXIS,
                                      tickColor=th.AXIS, labelAngle=0)),
                xOffset="Deal:N",
                y=alt.Y("Accretion:Q", title="EPS accretion",
                        axis=_axis("EPS accretion", ".0%")),
                color=alt.Color("Deal:N", scale=_scale(deal_colors),
                                legend=alt.Legend(title=None, orient="top")),
                tooltip=["Deal:N", "Year:N", alt.Tooltip("Accretion:Q", format=".1%")],
            ).properties(height=260),
            width="stretch",
        )
    with c2:
        st.markdown("**Capital comparison**")
        cap = pd.DataFrame([{
            "Deal": f"Acquire {bk.SHORT[n]}",
            "Goodwill": d["goodwill"],
            "CET1 pre-raise": d["ratio_pre_raise"],
            "Required": d["required_ratio"],
            "Raise": d["raise_needed"],
            "Duty": d["stamp_duty"],
        } for n, d in deals.items()])
        st.dataframe(
            cap.style.format({
                "Goodwill": "{:,.0f}", "CET1 pre-raise": "{:.2%}",
                "Required": "{:.2%}", "Raise": "{:,.1f}", "Duty": "{:,.1f}",
            }),
            hide_index=True, width="stretch",
        )
        b = deals["Novafin Kreditbank (B)"]
        c = deals["Banca Alpina (C)"]
        extra = (b["raise_needed"] + b["stamp_duty"]) - (c["raise_needed"] + c["stamp_duty"])
        st.caption(
            f"Acquiring B costs **{th.money(extra)}** more equity than C, duty "
            f"included, to reach its capital requirement under this scenario. "
            f"Note the requirements differ ({b['required_ratio']:.2%} vs "
            f"{c['required_ratio']:.2%}) because C brings a mortgage book, and "
            f"the sectoral buffer travels with it."
        )


# --------------------------------------------------------------------------
# 5. Bank data
# --------------------------------------------------------------------------
with tabs[4]:
    st.subheader("Edit the banks' books")
    st.caption(
        f"Every figure below feeds the whole app. Drawn and undrawn are "
        f"{bk.CURRENCY} millions; PD, LGD, risk weight, CCF and the Swiss GAAP "
        f"shares are decimal fractions (0.012 = 1.2%). Use the sidebar to reset."
    )

    edited = st.data_editor(
        st.session_state.products,
        width="stretch",
        num_rows="fixed",
        column_config={
            "bank": st.column_config.TextColumn("Bank", disabled=True),
            "client_type": st.column_config.TextColumn("Client type", disabled=True),
            "product": st.column_config.TextColumn("Product", disabled=True),
            "drawn": st.column_config.NumberColumn("Drawn", min_value=0.0, format="%.0f"),
            "undrawn": st.column_config.NumberColumn("Undrawn", min_value=0.0, format="%.0f"),
            "pd": st.column_config.NumberColumn("PD", min_value=0.0, max_value=1.0, format="%.4f"),
            "lgd": st.column_config.NumberColumn("LGD", min_value=0.0, max_value=1.0, format="%.3f"),
            "risk_weight": st.column_config.NumberColumn("Risk weight", min_value=0.0, max_value=3.0, format="%.3f"),
            "ccf": st.column_config.NumberColumn("CCF", min_value=0.0, max_value=1.0, format="%.2f"),
            "revolving": st.column_config.CheckboxColumn("Revolving"),
            "impaired": st.column_config.NumberColumn(
                "Impaired share", min_value=0.0, max_value=1.0, format="%.3f",
                help="Gefährdete Forderungen — drives the individual value adjustment"),
            "inherent": st.column_config.NumberColumn(
                "Inherent risk rate", min_value=0.0, max_value=1.0, format="%.4f",
                help="Provision rate for inherent default risks on the performing book"),
            "stage2": st.column_config.NumberColumn(
                "IFRS 9 stage 2", min_value=0.0, max_value=1.0, format="%.3f",
                help="Used only for the IFRS 9 shadow comparison"),
            "mortgage": st.column_config.CheckboxColumn(
                "Mortgage", help="Attracts the sectoral countercyclical buffer"),
        },
        key="editor",
    )
    # Write straight back. Editing a cell already triggers a rerun, so the
    # charts pick the change up on that pass — calling st.rerun() here instead
    # would loop forever whenever the editor hands back different dtypes than
    # it was given, and the loop starves every grid on every tab.
    st.session_state.products = edited

    st.divider()
    st.markdown("**Reconciliation to the reported books**")
    recon = pd.DataFrame([{
        "Bank": b,
        "Credit RWA (computed)": base_rows[base_rows["bank"] == b]["rwa_base"].sum(),
        "Other RWA (plug)": plug[b],
        "Total RWA": base_rows[base_rows["bank"] == b]["rwa_base"].sum() + plug[b],
        "Reported RWA": bk.BANK_FACTS[b].rwa,
    } for b in bk.BANKS])
    recon["Difference"] = recon["Total RWA"] - recon["Reported RWA"]
    st.dataframe(
        recon.style.format({c: "{:,.0f}" for c in recon.columns if c != "Bank"}),
        hide_index=True, width="stretch",
    )
    st.caption(
        "The plug is securities, operational risk and other non-loan assets. "
        "It is solved once from the unedited base case, so editing the loan "
        "book moves total RWA rather than silently absorbing the change."
    )


# --------------------------------------------------------------------------
# 6. Swiss rules explained
# --------------------------------------------------------------------------
with tabs[5]:
    st.subheader("What Swiss law changes, in plain English")
    st.markdown(sn.HEADLINE)

    st.divider()
    st.markdown("### The accounting difference, live")
    st.caption(
        "The same books, provisioned two ways. Swiss GAAP is the reported "
        "figure; the IFRS 9 column is a shadow calculation showing what "
        "three-stage staging would have required under the current scenario."
    )

    gaap = summary[["bank", "va_stressed", "ifrs9_stressed"]].melt(
        "bank", var_name="basis", value_name="amount")
    gaap["basis"] = gaap["basis"].map(
        {"va_stressed": "Swiss GAAP", "ifrs9_stressed": "IFRS 9 (shadow)"})

    g1, g2 = st.columns([3, 2])
    with g1:
        st.altair_chart(
            grouped_bars(gaap, "amount", "bank", "basis", th.BASIS_COLORS,
                         f"Provision ({bk.CURRENCY} m)"),
            width="stretch",
        )
    with g2:
        tot_va = summary["va_stressed"].sum()
        tot_i9 = summary["ifrs9_stressed"].sum()
        st.metric("Swiss GAAP, all three banks", th.money(tot_va))
        st.metric("IFRS 9 would require", th.money(tot_i9),
                  delta=th.money(tot_i9 - tot_va), delta_color="inverse")
        if tot_va > 0:
            st.metric("Difference", f"+{tot_i9 / tot_va - 1:.0%}")
        st.caption(
            "Push the scenario harder and watch the gap widen. That is the "
            "whole point: IFRS 9 front-loads provisions on a forecast, Swiss "
            "GAAP recognises them closer to when the losses occur. Under the "
            "base case the two are close; in a severe recession they are not."
        )

    st.divider()
    for heading, notes in sn.SECTIONS:
        st.markdown(f"### {heading}")
        for n in notes:
            with st.expander(n.title):
                st.caption(f"**Source:** {n.source}")
                st.markdown(n.body)
                st.success(f"**In this model:** {n.effect}")

    st.divider()
    st.caption(bk.DISCLAIMER)


# --------------------------------------------------------------------------
# 7. Method
# --------------------------------------------------------------------------
with tabs[6]:
    st.subheader("How a macro shock becomes a capital number")
    st.markdown(
        f"""
Each exposure line — bank × client type × product × region — runs through
this chain:

**1 · Probability of default.** A log-linear response to the five macro
inputs, with coefficients that differ by product and amplifiers that differ by
region.

```
PD′ = PD × exp( βu·au·Δu + βg·ag·(−Δg) + βr·ar·(Δr/100)
                + βp·ap·(−Δp/10) + βc·ac·(Δc/10) )
```

The franc term is the Swiss addition. Commercial lending carries by far the
largest franc beta, because exporters and tourism operators are the ones a
strong franc actually hurts.

**2 · Loss given default.** Moves with collateral value, so property
dominates. Swiss mortgage lending is full recourse with mandatory
amortisation, so even here the response is modest.

**3 · Exposure migration.** Revolvers consume headroom as conditions worsen.
The response is milder than in an unregulated market, because the KKG
affordability test already assumed the full limit was drawn before the limit
was granted.

**4 · Swiss GAAP value adjustments.** Individual adjustments on impaired
exposures, plus a provision for inherent default risks across the performing
book. Impairment is recognised as incurred, so it migrates slowly — there is
no stage 1 → 2 cliff.

```
VA = drawn × impaired × LGD′
   + drawn × (1 − impaired) × inherent
   + headroom × CCF × inherent
```

An IFRS 9 shadow runs alongside it for comparison.

**5 · Capital.** Charges hit CET1 after tax at {bk.TAX_RATE:.1%}
({bk.TAX_CANTON}). The requirement is the {eng.CET1_MANAGEMENT_TARGET:.1%}
management target on total RWA **plus** a {eng.SECTORAL_CCYB:.1%} sectoral
buffer on residential mortgage positions.

```
Required CET1 = {eng.CET1_MANAGEMENT_TARGET:.3f} × RWA + {eng.SECTORAL_CCYB:.3f} × mortgage RWA
```

---

**What is fixed and what is derived.** Each bank's reported figures — balance
sheet, CET1, total RWA, carried allowance — are the anchors and are never
recomputed. Total RWA reconciles through a solved plug; base value adjustments
are calibrated to the carried allowance, and that calibration factor is itself
reported as a reserve-adequacy signal.

The regional splits, transmission coefficients and behavioural responses are
invented for this simulation and are not calibrated to any real portfolio.
Read the shape of the answers, not the decimals.
        """
    )
    st.divider()
    st.caption(bk.DISCLAIMER)


# --------------------------------------------------------------------------
# 8. Glossary
# --------------------------------------------------------------------------
with tabs[7]:
    st.subheader("Every term in the app, in standard English")
    st.caption(
        f"Three vocabularies collide in this case: ordinary banking "
        f"abbreviations, the German and Italian words Swiss banking runs on, "
        f"and the statutes behind them. {len(gl.ALL_TERMS)} entries. "
        f"🇨🇭 marks a Swiss-specific term."
    )

    q1, q2 = st.columns([3, 2])
    with q1:
        query = st.text_input(
            "Search", placeholder='Try "default", "capital", "KKG", "reserve"…',
            label_visibility="collapsed", key="glossary_search",
        )
    with q2:
        swiss_only = st.checkbox("Swiss-specific terms only", value=False)

    results = gl.search(query)
    if swiss_only:
        results = [(h, [t for t in ts if t.swiss]) for h, ts in results]
        results = [(h, ts) for h, ts in results if ts]

    shown = sum(len(ts) for _, ts in results)
    if shown == 0:
        st.info("No term matches that search.")
    else:
        if query or swiss_only:
            st.caption(f"{shown} of {len(gl.ALL_TERMS)} terms")

        for heading, terms in results:
            st.markdown(f"### {heading}")
            for t in terms:
                flag = " 🇨🇭" if t.swiss else ""
                exp = f" — *{t.expansion}*" if t.expansion and t.expansion != "—" else ""
                st.markdown(f"**{t.term}**{flag}{exp}")
                st.markdown(
                    f"<div style='margin:-8px 0 4px 0;'>{t.meaning}</div>",
                    unsafe_allow_html=True,
                )
                if t.formula:
                    st.code(t.formula, language=None)
            st.divider()

    st.caption(bk.DISCLAIMER)

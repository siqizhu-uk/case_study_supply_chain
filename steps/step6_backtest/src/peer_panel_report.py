"""Step 6d outputs: panel tables, the external test on Nordic, a figure and the markdown section of step6_report.md."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from composite import factor_frame, factor_z  # noqa: E402
from cycle_test import cycle_stability  # noqa: E402
from peer_panel import (load_panel, industry_factor, build_design, walk_forward, score, full_sample, by_firm,  # noqa: E402
                        nordic_external, _fit, _expanding_z, hierarchical, phase_test, meta_regression, meta_table)

MAIN = "FE + both"
PEER_CHAR = Path(__file__).resolve().parents[3] / "pipelines" / "D_peer_panel" / "config" / "peer_characteristics.csv"


def run_peer_panel(s3: pd.DataFrame, cfg: dict, composite_first: str) -> dict:
    ind = industry_factor()
    d = build_design(load_panel(), ind, cfg)
    wf = walk_forward(d, cfg)
    sc = score(wf)
    fs = full_sample(d)
    ne = nordic_external(d, s3, ind, cfg, composite_first)
    # the same industry factor: peers' slope vs Nordic's own (signed, pts of beat per sd)
    sign = cfg["peer_panel"]["factors"]["industry_mchp_days"]["sign"]
    peer_b = float(_fit(d.dropna(subset=["fe", "z_industry"]), ["z_industry"])[0])
    Z = factor_z(factor_frame(s3, cfg), cfg)
    dd = pd.concat([s3["nordic_beat_vs_guide_pct"], sign * Z["mchp_disti_days_change"]], axis=1).dropna()
    nordic_b = float(np.polyfit(dd.iloc[:, 1], dd.iloc[:, 0], 1)[0])
    nr = pd.DataFrame({"beat_pct": s3["nordic_beat_vs_guide_pct"]})
    nr["fe"] = nr["beat_pct"].shift(1).expanding().mean()
    nr["z_industry"] = sign * _expanding_z(ind, cfg["peer_panel"]["min_z_history"]).reindex(nr.index)
    nr = nr.assign(company="NORDIC").reset_index().rename(columns={"index": "quarter"})
    ch = pd.read_csv(PEER_CHAR)
    like = ch.loc[ch["distribution_share"] >= cfg["peer_similarity"]["criteria"]["min_distribution_share"], "company"].tolist()
    hier = hierarchical(d, nr)
    return {"cycle": cycle_stability(s3, cfg), "hier": hier, "hier_like": hierarchical(d, nr, peers=like), "meta": meta_regression(hier, cfg), "phase": phase_test(d, cfg),
            "design": d, "walkforward": wf, "scores": sc, "full_sample": fs, "by_firm": by_firm(wf, MAIN),
            "nordic_external": ne, "slopes": {"peer_industry_b": peer_b, "nordic_industry_b": nordic_b, "nordic_n": len(dd)}}


def _figure(r: dict, d: Path) -> Path:
    fig, ax = plt.subplots(1, 3, figsize=(15, 4))
    sc = r["scores"].set_index("model")
    a = ax[0]
    a.barh(range(len(sc)), sc["oos_r2_vs_firm_mean"], color=["#4C78A8" if m.startswith("benchmark") else "#E45756" for m in sc.index])
    a.set_yticks(range(len(sc))); a.set_yticklabels(sc.index, fontsize=8); a.axvline(0, color="k", lw=.6)
    a.set_title(f"Peers: out-of-sample R² vs each firm's mean beat\n({int(sc['firm_quarters'].max())} firm-quarters, {int(sc['quarters'].max())} quarters)", fontsize=10)
    a = ax[1]
    s = r["slopes"]
    a.bar([f"{r['hier']['df'] + 1} peers\n(several cycles)", f"Nordic\n(n={s['nordic_n']}, one cycle)"], [s["peer_industry_b"], s["nordic_industry_b"]], color=["#4C78A8", "#E45756"])
    a.set_title("Same factor, same sign: beat per 1 sd of\nfalling Microchip distributor days", fontsize=10); a.set_ylabel("pts of beat")
    a = ax[2]
    ne = r["nordic_external"]
    x = pd.PeriodIndex(ne["quarter"], freq="Q").to_timestamp()
    a.bar(x, ne["actual"], width=50, color="#cccccc", label="Nordic actual beat")
    a.plot(x, ne[MAIN], "o-", color="#4C78A8", label="peer coefficients applied to Nordic")
    a.plot(x, ne["benchmark_past4"], "s--", color="#999", label="past-4 benchmark")
    a.axhline(0, color="k", lw=.6); a.legend(fontsize=7); a.set_title("External test on Nordic", fontsize=10)
    for a in ax:
        a.grid(alpha=.3)
    fig.tight_layout()
    f = d / "peer_panel.png"
    fig.savefig(f, dpi=120); plt.close(fig)
    return f


def section(r: dict, comp: dict | None) -> str:
    sc, fs, s = r["scores"].set_index("model"), r["full_sample"], r["slopes"]
    m = sc.loc[MAIN]
    ne = r["nordic_external"]
    rm = lambda c: float(np.sqrt(((ne[c] - ne["actual"]) ** 2).mean()))       # noqa: E731
    both = fs[fs["spec"] == MAIN].set_index("factor")
    ratio = s["nordic_industry_b"] / s["peer_industry_b"] if s["peer_industry_b"] else np.nan
    md = ["## 8. Peer panel: does the mechanism hold across companies and cycles? (step 6d)\n",
          f"The Nordic composite rests on ~2 independent observations. {int(m['firms'])} peers (Pipeline D: "
          f"{', '.join(sorted(r['design']['company'].unique()))}; every guide quote-checked, structural breaks excluded) give several cycles. The panel is estimated on the peers "
          "only and then applied to Nordic, which it never saw. Pooling adds information for firm-specific factors; the industry factor is "
          "common to all firms, so its standard errors are clustered by quarter.\n",
          "**Walk-forward (pooled, point in time):**\n", r["scores"].round(3).to_markdown(index=False), "",
          "**Full sample, standard errors clustered by quarter:**\n", fs.round(3).to_markdown(index=False), "",
          f"**Answer.** Across {int(m['firm_quarters'])} firm-quarters the channel factors do not beat each firm's own mean beat out of sample "
          f"(OOS R² {m['oos_r2_vs_firm_mean']:+.3f}; better in {m['quarters_won_share']:.0%} of quarters). Full sample: own forward DIO "
          f"t = {both.loc['z_own_fwd_dio', 't']:.1f}, industry channel t = {both.loc['z_industry', 't']:.1f}. "
          f"On the same industry factor Nordic's own slope is {s['nordic_industry_b']:+.2f} pts per sd against {s['peer_industry_b']:+.2f} for the peers "
          f"({ratio:.0f}x).\n",
          f"**External test on Nordic** (same {len(ne)} quarters as the composite): peer coefficients RMSE {rm(MAIN):.2f} pts; past-4 benchmark "
          f"{rm('benchmark_past4'):.2f}; Nordic's own firm mean {rm('benchmark_firm_mean'):.2f}"
          + (f"; Nordic-fitted composite {comp['oos_rmse_pts']:.2f}" if comp else "") + ".\n",
          "**Reading.** The mechanism the composite encodes (lean channel → beat) does not generalise across companies and cycles. Nordic's "
          "strong in-sample relation is specific to one cycle of one company — the pattern the R1/R2/R4 flags warned about, now confirmed by "
          "independent data.\n",
          "![peer panel](peer_panel.png)\n", "By firm (walk-forward, `FE + both`):\n", r["by_firm"].to_markdown(index=False), "",
          "### What is unique to Nordic? Partial pooling (hierarchical / empirical Bayes)\n",
          "Each firm's slope on the industry factor = peer mean + its own deviation. Nordic's slope is shrunk towards the peer mean in proportion "
          "to how much its own data can be trusted: weight = τ² / (τ² + se²).\n", r["hier"]["per_firm"].round(3).to_markdown(index=False), "",
          _hier_sentence(r["hier"]), "",
          "### Is Nordic different because of what it is? Nordic-like peers and meta-regression (step 6e)\n",
          "Peers chosen by a criterion fixed before any slope was seen (distribution share >= 35%, read from each 10-K and quote-checked; "
          "Nordic 42-55%). Each peer's slope is regressed on its characteristic, weights 1/(se² + τ²_resid); Nordic never enters the fit and its "
          "slope is **predicted** from its characteristic, with a 90% prediction interval that includes τ.\n",
          r["meta"]["table"].round(3).to_markdown(index=False), "",
          meta_table(r["meta"]).round(3).to_markdown(index=False), "",
          _meta_sentence(r), "",
          "### More cycles: is the slope a property of Nordic or of the cycle? (step 6f)\n",
          "Same factor on one fixed scale (1 sd of the Microchip days change over 2008-2026), firm means removed window by window. "
          "The 2008-10 window comes from the release history (Pipeline D `history`, actuals double-sourced). The factor is common to all "
          "firms, so the honest n is the number of quarters; `se_q_level_neff` also corrects for the factor's autocorrelation "
          "(Bartlett n_eff). `top3_share` = share of the slope carried by its three biggest quarters.\n",
          r["cycle"].drop(columns=["reason"]).round(3).to_markdown(index=False), "", _cycle_sentence(r["cycle"]), "",
          "### Should each cycle phase get its own model? (phase = sign of the firm's own revenue YoY at t−1, known in real time)\n",
          r["phase"].round(3).to_markdown(index=False), "", _phase_sentence(r["phase"]), ""]
    return "\n".join(md)


def _hier_sentence(h: dict) -> str:
    sn, se = h["shrink"]["naive"], h["shrink"]["effective_n"]
    return (f"Peer mean slope {h['peer_mean']:+.2f} (se {h['peer_mean_se']:.2f}); between-firm sd τ = {h['tau']:.2f} (Q = {h['Q']:.1f} on {h['df']} df). "
            f"Nordic's own slope {h['nordic_b']:+.2f} gets weight {sn['weight_on_nordic']:.2f} (naive se) to {se['weight_on_nordic']:.2f} "
            f"(se for its effective n) → shrunk slope {sn['shrunk_slope']:+.2f} to {se['shrunk_slope']:+.2f}. Nordic may differ from the peers, "
            "but its data hold too few independent observations to show by how much; firm-specific structure should come from observable "
            "characteristics (distribution share, end-market mix, lead times) rather than from a free slope.")


def _meta_sentence(r: dict) -> str:
    f = {x["sample"]: x for x in r["meta"]["fits"]}
    a, lk, hl = f.get("all peers"), f.get("Nordic-like peers"), r["hier_like"]
    cons = f.get("Nordic-like peers (exploratory)")
    out = []
    if lk:
        pm = lk["nordic_pred"]["mid"]
        out.append(f"Among {lk['n']} Nordic-like peers the slope moves {lk['gamma1']:+.2f} per unit of distribution share (se {lk['gamma1_se']:.2f}, "
                    f"t = {lk['gamma1_t']:.1f}); at Nordic's share ({pm['x']:.2f}) the predicted slope is {pm['pred']:+.2f} "
                    f"(90% PI {pm['pi90'][0]:+.2f} to {pm['pi90'][1]:+.2f}) against Nordic's own {r['hier']['nordic_b']:+.2f}.")
    if a:
        out.append(f"With all {a['n']} peers (incl. TI, share <= 20%) the coefficient is {a['gamma1']:+.2f} (t = {a['gamma1_t']:.1f}).")
    out.append(f"Shrinkage within the Nordic-like peers: peer mean {hl['peer_mean']:+.2f}, τ = {hl['tau']:.2f} (Q = {hl['Q']:.1f} on {hl['df']} df), "
               f"weight on Nordic {hl['shrink']['naive']['weight_on_nordic']:.2f} to {hl['shrink']['effective_n']['weight_on_nordic']:.2f} → "
               f"slope {hl['shrink']['naive']['shrunk_slope']:+.2f} to {hl['shrink']['effective_n']['shrunk_slope']:+.2f}.")
    if cons:
        out.append(f"Exploratory only (B30): consumer share gives {cons['gamma1']:+.2f} (t = {cons['gamma1_t']:.1f}) on {cons['n']} firms whose shares span "
                   f"{cons['x_range'][0]:.2f}-{cons['x_range'][1]:.2f}; Nordic's {cons['nordic_pred']['nordic']['x']:.2f} lies "
                   + ("outside that range, so any prediction is an extrapolation." if cons["nordic_extrapolated"] else "inside that range."))
    if lk:
        hi, sig = lk["nordic_pred"]["mid"]["pi90"][1], abs(lk["gamma1_t"]) >= 2
        out.append("**Reading.** " + (
            "Being Nordic-like on distribution share does not produce a Nordic-sized slope: Nordic's own slope lies above the 90% prediction "
            "interval of similar peers, " if r["hier"]["nordic_b"] > hi else "Nordic's own slope lies inside the prediction interval of similar peers, ")
            + ("and distribution share does explain part of the between-firm spread." if sig else
               "and distribution share does not explain the between-firm spread (|t| < 2). The characteristic cannot account for Nordic's slope; "
               "the most likely explanation remains that it is fitted to one cycle."))
    return " ".join(out)


def _cycle_sentence(t: pd.DataFrame) -> str:
    w = t.set_index(["window", "who"])
    pe, no = w.loc[("nordic_window", "peers")], w.loc[("nordic_window", "NORDIC")]
    g0, g1 = t.attrs.get("gap_naive", {}), t.attrs.get("gap_n_eff", {})
    common = set(pe["top3_quarters"].split(", ")) & set(no["top3_quarters"].split(", "))
    parts = []
    for name in ("gfc_2008_10", "normal_2011_19", "covid_2020_26"):
        if (name, "peers") in w.index:
            r = w.loc[(name, "peers")]
            parts.append(f"{name} {r['b_quarter_level']:+.2f} (se {r['se_q_level_neff']:.2f}, {int(r['quarters_q_level'])} quarters)")
    sig = lambda b, se: abs(b) >= 2 * se      # noqa: E731
    return ("Peers by cycle window: " + "; ".join(parts) + ". "
            f"Inside Nordic's own window ({no['from']}-{no['to']}) the peers' slope is {pe['b_quarter_level']:+.2f} (se {pe['se_q_level_neff']:.2f} on n_eff "
            f"{pe['n_eff']:.1f}), i.e. {t.attrs.get('cycle_share_of_nordic', float('nan')):.0%} of Nordic's {no['b_quarter_level']:+.2f}. "
            f"Nordic minus peers = {g0.get('gap', float('nan')):+.2f}: t = {g0.get('t', float('nan')):.1f} naive, {g1.get('t', float('nan')):.1f} with the "
            "factor's autocorrelation. "
            + (f"The same quarters carry both slopes ({', '.join(sorted(common))}: top-3 share {pe['top3_share']:.0%} for the peers, "
               f"{no['top3_share']:.0%} for Nordic). " if common else "")
            + "**Reading.** "
            + ("The slope is not a stable parameter: it is " + ("indistinguishable from zero" if not sig(w.loc[('normal_2011_19', 'peers'), 'b_quarter_level'], w.loc[('normal_2011_19', 'peers'), 'se_q_level_neff']) else "non-zero")
               + " in 2011-19 and " + ("not detectable" if not sig(w.loc[('gfc_2008_10', 'peers'), 'b_quarter_level'], w.loc[('gfc_2008_10', 'peers'), 'se_q_level_neff']) else "present")
               + " in the 2008-10 crash; it appears only around the 2023 destock turn. ")
            + ("Nordic's excess over the peers in the same window cannot be told apart from noise once autocorrelation is counted. "
               if abs(g1.get("t", 0)) < 2 else "Nordic's excess over the peers survives the autocorrelation correction. ")
            + "More cycles did not add independent confirmation: the evidence for the mechanism, for Nordic and for the peers, is one turn.")


def _phase_sentence(ph: pd.DataFrame) -> str:
    t = ph.set_index("model")
    best = t["oos_r2_vs_firm_mean"].idxmax()
    return (f"Across {int(t['firm_quarters'].iloc[0])} firm-quarters with {int(t['downturn_quarters'].iloc[0])} distinct downturn quarters, phase-specific slopes "
            f"give OOS R² {t.loc['phase-specific slopes', 'oos_r2_vs_firm_mean']:+.3f} (downturns {t.loc['phase-specific slopes', 'oos_r2_in_downturns']:+.3f}); "
            f"best is '{best}' at {t.loc[best, 'oos_r2_vs_firm_mean']:+.3f}. Separate models per cycle phase do not help even with several cycles; "
            "on Nordic's single cycle they would be fitted to one downturn and one upturn.")


def write_peer_panel(r: dict, comp: dict | None, d: Path) -> str:
    r["scores"].round(4).to_csv(d / "peer_panel_scores.csv", index=False)
    r["full_sample"].round(4).to_csv(d / "peer_panel_full_sample.csv", index=False)
    r["by_firm"].to_csv(d / "peer_panel_by_firm.csv", index=False)
    r["walkforward"].round(3).to_csv(d / "peer_panel_walkforward.csv", index=False)
    r["nordic_external"].round(3).to_csv(d / "peer_panel_nordic_external.csv", index=False)
    pd.DataFrame([r["slopes"]]).round(3).to_csv(d / "peer_panel_slopes.csv", index=False)
    r["hier"]["per_firm"].round(4).to_csv(d / "peer_panel_hierarchical.csv", index=False)
    r["phase"].round(4).to_csv(d / "peer_panel_phase_test.csv", index=False)
    r["cycle"].round(4).to_csv(d / "cycle_stability.csv", index=False)
    meta_table(r["meta"]).round(4).to_csv(d / "peer_panel_meta_regression.csv", index=False)
    r["hier_like"]["per_firm"].round(4).to_csv(d / "peer_panel_hierarchical_nordic_like.csv", index=False)
    _figure(r, d)
    return section(r, comp)

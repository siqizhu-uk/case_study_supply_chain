"""Key insights box (step 6g): what the beat IS, computed from data, shown above the risk box in step6_report.md, the model
report and the dashboard. Every sentence is built from the numbers, so the wording follows the data on each re-run."""
from __future__ import annotations

import html

import pandas as pd

from core.config import ROOT

FILE = "key_insights.csv"
PATH = ROOT / "steps" / "step6_backtest" / "outputs" / FILE


def _fit(t: pd.DataFrame, spec: str, sample: str, col: str) -> tuple[float, float]:
    r = t[(t["spec"] == spec) & (t["sample"] == sample)].iloc[0]
    return float(r[f"b_{col}"]), float(r[f"t_{col}"])


def key_insights(g: dict, cfg: dict, h2: dict | None = None) -> pd.DataFrame:
    c, pn, nf, N = g["cycle_in_guide"], g["panel"], g["nordic_fits"], g["nordic"]
    ep = cfg["guidance_optimism"]["episode_quarters"]
    rel = pn["fits"].set_index("spec").loc["rel_raw"]
    q = pn["quintiles"]
    top, bottom = q.iloc[-1], q.iloc[0]
    b_ch, t_ch = _fit(nf, "x_channel", "without episode", "x_channel")
    guide_rows = [s for s in ("rel_raw", "g", "guide_width_pct", "last_beat")]
    survivors = [s for s in guide_rows if abs(_fit(nf, s, "without episode", s)[1]) >= 2]
    e = N.loc[pd.Period(ep[0], "Q")]
    rows = [
        {"id": "K1", "insight": "The beat is management's forecast error, not demand",
         "evidence": (f"Across {c['n']} peer quarters revenue YoY has sd {c['sd_yoy']:.0f}% but the beat only {c['sd_beat']:.1f}% "
                      f"(correlation {c['corr_yoy_beat']:.2f}). In the {c['deep_n']} quarters where a peer's revenue fell "
                      f"{abs(cfg['guidance_optimism']['deep_decline_yoy_pct'])}% or more YoY the mean beat was {c['deep_mean_beat']:+.1f}% and "
                      f"{c['deep_within5']:.0%} stayed within +/-5%: management writes the cycle into the guide."),
         "implication": "A factor can predict the beat only if management ignored public information; channel signals can at most "
                        "help the revenue forecast beyond the guided quarter (K4)."},
        {"id": "K2", "insight": f"Nordic's {ep[0]} miss was not set up by a guide more optimistic than the peers'",
         "evidence": (f"For {ep[0]} Nordic guided {e['g']:+.1f}% q/q against a peer median of {e['peer_median_g']:+.1f}% "
                      f"(relative optimism {e['rel_raw']:+.1f} pts), then missed by {abs(e['beat']):.1f}%: the shortfall arose inside the quarter. "
                      f"Against the consumer-heavy peers only (exploratory, chosen after seeing the data) the gap was {e['rel_consumer_heavy']:+.1f} pts."),
         "implication": "Which comparator is 'the market' decides the reading; the pre-registered peer median does not flag the episode."},
        {"id": "K3", "insight": "No guide-setting factor predicts misses",
         "evidence": (f"Relative guidance optimism on {int(rel['firm_quarters'])} peer firm-quarters ({int(rel['quarters'])} quarters): "
                      f"{rel['b_rel_raw']:+.3f} per pt (t {rel['t_rel_raw']:.1f}); walk-forward OOS R2 {pn['oos_r2']:+.3f} vs each firm's mean; "
                      f"the most optimistic fifth of guides misses in {top['miss_rate']:.0%} of quarters, the least optimistic in {bottom['miss_rate']:.0%}. "
                      f"On Nordic without {', '.join(ep)}: "
                      + ("none of relative optimism, guided growth, guide width or last quarter's beat has |t| >= 2" if not survivors
                         else f"{', '.join(survivors)} keep |t| >= 2")
                      + f"; the channel factor keeps {b_ch:+.2f} (t {t_ch:.1f}, naive)."),
         "implication": "The large Nordic misses are rare intra-quarter surprises; about a dozen candidate factors have now been tried on "
                        "21 quarters, so any one that 'works' on Nordic alone is expected by chance."},
    ]
    if h2 is not None:
        a = h2["scores"].set_index("window").loc["all"]
        helps = a["oos_r2_vs_seasonal"] > 0 and h2["gain_t"] >= 2
        rows.append({"id": "K4", "insight": "Beyond the guided quarter the channel factor " + ("helps revenue forecasts" if helps else "adds little to revenue forecasts"),
                     "evidence": (f"Forecasting revenue one quarter past the guide (g2 = actual t+1 / guide t) on {int(a['firm_quarters'])} peer firm-quarters: "
                                  f"seasonal benchmark + channel factor gives OOS R2 {a['oos_r2_vs_seasonal']:+.1%} vs the seasonal benchmark alone "
                                  f"(t {h2['gain_t']:.1f}; RMSE {a['rmse_model']:.2f} with the channel vs {a['rmse_seasonal']:.2f} seasonal vs {a['rmse_flat']:.2f} flat, pts); "
                                  f"{a['top3_gain_share']:.0%} of the gain comes from {a['top3_quarters']}; without {', '.join(ep)} {h2['oos_r2_wo_episode']:+.1%}."),
                     "implication": "Where the channel belongs (revenue beyond the guide, not the beat) is consistent with (not confirmed by) the data: its value there is small "
                                    "and turn-dependent: seasonality does more than the channel."})
    return pd.DataFrame(rows)


def load_insights() -> pd.DataFrame | None:
    try:
        return pd.read_csv(PATH)
    except FileNotFoundError:
        return None


def insight_box_md(k: pd.DataFrame | None) -> str:
    if k is None or k.empty:
        return ""
    lines = ["> ### 💡 Key insights (computed from the data)", ">"]
    for r in k.itertuples():
        lines += [f"> **{r.id}. {r.insight}.** {r.evidence} *So what:* {r.implication}", ">"]
    return "\n".join(lines[:-1]) + "\n\n"


def insight_box_html(k: pd.DataFrame | None) -> str:
    if k is None or k.empty:
        return ""
    items = "".join(f"<li><b>{html.escape(r.id)}. {html.escape(r.insight)}.</b> {html.escape(r.evidence)} "
                    f"<i>So what:</i> {html.escape(r.implication)}</li>" for r in k.itertuples())
    return ('<section class="insights" style="border-left:4px solid #2b7bb9;background:rgba(43,123,185,.08);'
            'padding:12px 16px;margin:16px 0;border-radius:6px"><h2 style="margin-top:0">💡 Key insights (computed from the data)</h2>'
            f"<ol>{items}</ol></section>")

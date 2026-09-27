"""Step 6g section of step6_report.md and its output files."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from key_insights import key_insights, insight_box_md, FILE as INSIGHT_FILE

NORDIC_COLS = ["guide_mid_usdm", "g", "peer_median_g", "rel_raw", "rel_seasonal", "rel_consumer_heavy", "guide_width_pct",
               "last_beat", "x_channel", "beat"]


def section(g: dict, k: pd.DataFrame, h2: dict | None = None) -> str:
    p = g["panel"]
    sq = g["same_quarter"]
    return "\n".join([
        "## 9. What the beat is: guidance-setting factors (step 6g)\n",
        "The beat is (actual / guide mid - 1): management's forecast error. Candidates therefore describe how the guide was set and "
        "are nearly uncorrelated with the channel factors: relative guidance optimism (guided q/q minus the median of the other peers' "
        "guided q/q for the same quarter), the same net of each firm's seasonal norm (robustness; the norm is contaminated by the cycle, "
        "P55), a consumer-heavy comparator (exploratory, P56), guided growth, guide width and last quarter's beat.\n",
        insight_box_md(k),
        "**Peer panel** (the test with many firms and cycles; y = beat minus the firm's past mean, SE clustered by quarter):\n",
        p["fits"].round(3).to_markdown(index=False), "",
        f"Walk-forward OOS R² of `firm mean + b x relative optimism` vs the firm mean: {p['oos_r2']:+.3f} on {p['oos_n']} firm-quarters. "
        f"Correlation of relative optimism with the channel factor: {p['corr_rel_channel']:+.2f}.\n",
        "By quintile of relative optimism:\n", p["quintiles"].round(3).to_markdown(index=False), "",
        "**Nordic** (each fit also without the episode quarters):\n", g["nordic_fits"].round(2).to_markdown(index=False), "",
        f"Same-quarter peer mean beat vs Nordic's beat: correlation {sq['corr']:.2f} ({sq['n']} quarters), {sq['corr_wo_episode']:.2f} without "
        "the episode; not usable as a nowcast in any case, since Nordic reports before most peers.\n",
        "Nordic, quarter by quarter:\n", g["nordic"][NORDIC_COLS].round(2).to_markdown(), "",
        "Correlations (Nordic):\n", g["corr"].round(2).to_markdown(), "",
        *( [] if h2 is None else [
            "## 10. Where the channel belongs: revenue beyond the guided quarter (step 6h)\n",
            "At the end of quarter t (guide for t known, actuals to t-1, Microchip days to t-1) forecast g2 = actual(t+1) / guide(t) - 1. "
            "Benchmark: the firm's mean past g2 for the same quarter of the year. Model: benchmark + b x channel factor, b re-estimated each "
            "quarter on rows whose target has been reported. Acquisitions landing in t+1 are removed (`h2_breaks`); every |g2 - seasonal| > 30 pts "
            "is read and listed (`h2_verified`).\n",
            h2["scores"].round(3).to_markdown(index=False), "",
            f"Mean quarterly loss gain t = {h2['gain_t']:.1f}; OOS R² without the episode quarters {h2['oos_r2_wo_episode']:+.3f}; "
            f"unexplained outliers: {', '.join(h2['unexplained']) or 'none'}.\n"])])


def write_guidance_optimism(g: dict, cfg: dict, d: Path, h2: dict | None = None) -> tuple[str, pd.DataFrame]:
    k = key_insights(g, cfg, h2)
    if h2 is not None:
        h2["scores"].round(4).to_csv(d / "revenue_h2_scores.csv", index=False)
        h2["walkforward"].round(3).to_csv(d / "revenue_h2_walkforward.csv", index=False)
    k.to_csv(d / INSIGHT_FILE, index=False)
    g["nordic"][NORDIC_COLS].round(3).to_csv(d / "guidance_optimism_nordic.csv")
    g["nordic_fits"].round(4).to_csv(d / "guidance_optimism_nordic_fits.csv", index=False)
    g["panel"]["fits"].round(4).to_csv(d / "guidance_optimism_panel.csv", index=False)
    g["panel"]["quintiles"].round(4).to_csv(d / "guidance_optimism_quintiles.csv", index=False)
    return section(g, k, h2), k

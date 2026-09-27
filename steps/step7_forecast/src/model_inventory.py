"""Every model in the project in one table (config/model_inventory.csv) joined with its walk-forward performance from
step 6 -> outputs/model_inventory.csv (read by the dashboard and the results page)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from core.config import OUTPUTS, step_outputs

CONFIG = Path(__file__).resolve().parents[1] / "config" / "model_inventory.csv"


def _perf_tables() -> dict[str, pd.DataFrame]:
    d = step_outputs("step6_backtest")
    out = {}
    for key, name, idx in (("wf1", "walkforward_metrics_h1.csv", "model"), ("wf2", "walkforward_metrics_h2.csv", "model"),
                           ("comp", "composite_models.csv", "model"), ("compg", "composite_graph_models.csv", "model"),
                           ("ch", "../../step7_forecast/outputs/chain_scores.csv", "model")):
        f = d / name
        if f.exists():
            out[key] = pd.read_csv(f).set_index(idx)
    f = step_outputs("step7_forecast") / "guide_error_walkforward_nordic.csv"  # step 7e: Nordic guide-error rules (F20, F30, F31)
    if f.exists():
        out["gem"] = _gem_scores(pd.read_csv(f))
    f = step_outputs("step5_supply_graph") / "cycle_challenger_scores.csv"     # step 5g, G29
    if f.exists():
        s = pd.read_csv(f)
        bar = s[s["scope"].str.startswith("adoption bar")].set_index("model")["bar_met"]
        out["cyc"] = s[(s["scope"] == "main") & (s["vs"] == "GR")].set_index("model").assign(bar_met=bar)
    return out


def _gem_scores(w: pd.DataFrame) -> pd.DataFrame:
    """Walk-forward RMSE (pts of the guide midpoint) of each Nordic guide-error rule vs the actual error, same quarters."""
    rules = [c for c in ("model", "pooled_challenger", "previous_rule", "wording_rule") if c in w]
    rmse = {c: float(np.sqrt(((w[c] - w["actual_error"]) ** 2).mean())) for c in rules}
    return pd.DataFrame({"rmse_pts": rmse, "n": len(w), "rmse_used_pts": rmse.get("model", np.nan)})


def _perf(key: str, tabs: dict) -> str:
    """'h1: RMSE USD 20.3m (5.9x GB, n=6); h2: ...' for walk-forward models; beat RMSE and OOS R2 for the composite.
    A key part 'src:model:label' puts the label in front ('GRi h2: ...') where one row scores several models."""
    parts = []
    for k in [x for x in str(key).split("|") if x and x != "nan"]:
        src, model, *label = k.split(":", 2)
        t = tabs.get(src)
        if t is None or model not in t.index:
            continue
        r = t.loc[model]
        name = f"{label[0]} " if label else ""
        if src == "gem":
            vs = "" if model == "model" else f" vs {r['rmse_used_pts']:.2f} for the rule used (F20, F30)"
            parts.append(f"guide-error RMSE {r['rmse_pts']:.2f} pts{vs} (n={int(r['n'])})")
        elif src == "cyc":
            bar = "met" if str(r["bar_met"]).lower() == "true" else "not met"
            parts.append(f"h2: RMSE USD {r['rmse']:.1f}m vs GR {r['rmse_bench_same_quarters']:.1f}m (n={int(r['n'])}, DM t {r['dm_t']:+.1f}); adoption bar {bar}")
        elif src == "ch":
            parts.append(f"h{int(r['horizon'])}: RMSE USD {r['rmse_total_usdm']:.1f}m, {r['rmse_ratio_vs_GB']:.2f}× benchmark (n={int(r['n'])}); weight {r['weight']:.2f}")
        elif src in ("comp", "compg"):
            parts.append(f"beat RMSE {r['rmse_beat_pts']:.2f} pts vs benchmark {r['bench_rmse_same_quarters']:.2f} (OOS R² {r['oos_r2_vs_bench']:+.2f}, n={int(r['n'])})")
        else:
            ratio = r.get("rmse_ratio_vs_GB")
            rel = f", {ratio:.2f}× benchmark" if pd.notna(ratio) and model != "GB" else ""
            parts.append(f"{name}{'h1' if src == 'wf1' else 'h2'}: RMSE USD {r['rmse_total_usdm']:.1f}m{rel} (n={int(r['n'])})")
    return "; ".join(parts)


def build_inventory() -> pd.DataFrame:
    inv = pd.read_csv(CONFIG)
    tabs = _perf_tables()
    inv["walk_forward_performance"] = inv["perf_key"].map(lambda k: _perf(k, tabs))
    out = inv.drop(columns="perf_key")
    out.to_csv(OUTPUTS / "model_inventory.csv", index=False)
    return out

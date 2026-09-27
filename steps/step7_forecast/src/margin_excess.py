"""Channel-excess term for Nordic's gross margin (step 7, decision F25), pre-registered in config/model.yaml
(guidance_anchor.margins.nordic_excess) BEFORE estimation.

Hypothesis: price protection and ASP concessions flow upstream when the channel holds excess stock, i.e. the step 3b cycle
state (Microchip distributor days, common to all firms) was 'building' or 'drawdown' in the quarter before.

    dGM_it = GM_it - GM_i,t-1 (pts) = a_i + delta x excess_t-1 + e_it

delta is estimated on the 12 semiconductor peers (Pipeline D XBRL revenue and COGS; GM = 1 - COGS / revenue), firm effect by
demeaning, standard error clustered by quarter (the regressor is the same for every firm in a quarter, so firm-quarters are
not independent evidence). Quarter-on-quarter moves beyond +/- max_abs_change_pts are accounting events and dropped.

Adoption (fixed before the numbers): delta < 0 with |t| >= t_min on the full peer sample AND, walk-forward on Nordic's
one-off-adjusted GM, 'last quarter + delta_t x excess_t-1' has a lower RMSE than 'last quarter' (delta_t re-estimated at each
target on peer rows dated up to t-1 only).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from core.config import ROOT

PEER_RAW = ROOT / "pipelines" / "D_peer_panel" / "data" / "raw"
CYCLE_STATE = ROOT / "steps" / "step3_inventory_mechanism" / "outputs" / "cycle_state.csv"


def spec(cfg: dict) -> dict:
    return cfg["guidance_anchor"]["margins"]["nordic_excess"]


# ------------------------------------------------------------------ inputs
def load_peer_gm() -> pd.DataFrame:
    """company, quarter (Period), gm_pct from XBRL revenue and COGS."""
    a = pd.read_csv(PEER_RAW / "peer_actuals_xbrl.csv")[["company", "quarter", "actual_usdm"]]
    b = pd.read_csv(PEER_RAW / "peer_balance_xbrl.csv")[["company", "quarter", "cogs_usdm"]]
    m = a.merge(b, on=["company", "quarter"], how="inner").dropna(subset=["actual_usdm", "cogs_usdm"])
    m = m[m["actual_usdm"] > 0]
    return pd.DataFrame({"company": m["company"].values, "quarter": pd.PeriodIndex(m["quarter"], freq="Q"),
                         "gm_pct": (100 * (1 - m["cogs_usdm"] / m["actual_usdm"])).values})


def load_excess(cfg: dict) -> pd.Series:
    """1.0 if the step 3b state of the quarter is one of the excess states, 0.0 otherwise, NaN where no state exists."""
    c = pd.read_csv(CYCLE_STATE).dropna(subset=["state"])
    s = pd.Series(c["state"].isin(spec(cfg)["states"]).astype(float).values, index=pd.PeriodIndex(c["quarter"], freq="Q"))
    return s.sort_index()


def peer_changes(gm: pd.DataFrame, excess: pd.Series, cfg: dict) -> pd.DataFrame:
    """One row per peer firm-quarter: dGM over consecutive quarters, excess state lagged, accounting events flagged."""
    sp = spec(cfg)
    g = gm.sort_values(["company", "quarter"])
    ordinal = g["quarter"].map(lambda q: q.ordinal)
    consecutive = ordinal.groupby(g["company"]).diff().eq(1)              # no dGM across a missing quarter
    d = g.assign(d_gm=g.groupby("company")["gm_pct"].diff().where(consecutive))
    d = d.dropna(subset=["d_gm"])
    lag = sp["state_lag_quarters"]
    d = d.assign(excess_lag=[excess.get(q - lag, np.nan) for q in d["quarter"]])
    d = d.assign(accounting_event=d["d_gm"].abs() > sp["max_abs_change_pts"])
    return d.dropna(subset=["excess_lag"]).reset_index(drop=True)


# ------------------------------------------------------------------ estimation
def estimate(rows: pd.DataFrame) -> dict:
    """Within-firm OLS of dGM on excess_t-1; SE clustered by quarter (CR1: G/(G-1) x (N-1)/(N-K), K = 1 + firms)."""
    r = rows[~rows["accounting_event"]]
    if r.empty or r["excess_lag"].nunique() < 2:
        return {"delta": np.nan, "se": np.nan, "t": np.nan, "n": int(len(r)), "n_quarters": int(r["quarter"].nunique()) if len(r) else 0}
    y = r["d_gm"] - r.groupby("company")["d_gm"].transform("mean")
    x = r["excess_lag"] - r.groupby("company")["excess_lag"].transform("mean")
    sxx = float((x ** 2).sum())
    delta = float((x * y).sum() / sxx)
    e = y - delta * x
    score = (x * e).groupby(r["quarter"]).sum()
    n, g, k = len(r), len(score), 1 + r["company"].nunique()
    c = g / (g - 1) * (n - 1) / (n - k)
    se = float(np.sqrt(c * (score ** 2).sum()) / sxx)
    return {"delta": delta, "se": se, "t": delta / se if se > 0 else np.nan, "n": int(n), "n_quarters": int(g),
            "n_firms": int(r["company"].nunique()), "n_excess_quarters": int(r.loc[r["excess_lag"] == 1, "quarter"].nunique()),
            "n_dropped_accounting": int(rows["accounting_event"].sum()),
            "first_quarter": str(r["quarter"].min()), "last_quarter": str(r["quarter"].max())}


def walk_forward(nordic: pd.Series, rows: pd.DataFrame, excess: pd.Series, cfg: dict) -> pd.DataFrame:
    """Nordic targets t: base = GM_t-1; with term = GM_t-1 + delta_t x excess_t-1, delta_t from peer rows dated <= t-1."""
    sp = spec(cfg)
    s = nordic.dropna().sort_index()
    first = max(pd.Period(sp["first_target"], "Q"), s.index.min() + 1)
    out = []
    for t in s.index[s.index >= first]:
        if t - 1 not in s.index:
            continue
        est = estimate(rows[rows["quarter"] <= t - 1])
        x = excess.get(t - sp["state_lag_quarters"], np.nan)
        base = float(s[t - 1])
        term = est["delta"] * x if pd.notna(x) and pd.notna(est["delta"]) else np.nan
        out.append({"target": str(t), "actual": float(s[t]), "last_quarter": base, "excess_t_1": x, "delta_t": est["delta"],
                    "t_stat_t": est["t"], "n_peer_rows": est["n"], "term_pts": term,
                    "with_term": base + term if pd.notna(term) else np.nan})
    wf = pd.DataFrame(out)
    if len(wf):
        wf["err_last_quarter"] = wf["last_quarter"] - wf["actual"]
        wf["err_with_term"] = wf["with_term"] - wf["actual"]
    return wf


def _rmse(e: pd.Series) -> float:
    e = e.dropna()
    return float(np.sqrt((e ** 2).mean())) if len(e) else np.nan


def adoption(est: dict, wf: pd.DataFrame, cfg: dict) -> dict:
    """The pre-stated rule, nothing else: sign and |t| on the full peer sample, then Nordic's walk-forward RMSE."""
    both = wf.dropna(subset=["err_last_quarter", "err_with_term"]) if len(wf) else wf
    r_base = _rmse(both["err_last_quarter"]) if len(both) else np.nan
    r_term = _rmse(both["err_with_term"]) if len(both) else np.nan
    sign_ok = bool(pd.notna(est["t"]) and est["delta"] < 0 and abs(est["t"]) >= spec(cfg)["t_min"])
    wf_ok = bool(pd.notna(r_base) and pd.notna(r_term) and r_term < r_base)
    why = ("adopted: delta < 0 with |t| >= {tm:g} and the term lowers Nordic's walk-forward RMSE" if sign_ok and wf_ok else
           "not adopted: " + "; ".join(m for ok, m in ((sign_ok, f"peer delta {est['delta']:+.2f} pts, t {est['t']:.2f} (needs < 0 with |t| >= {spec(cfg)['t_min']:g})"),
                                                      (wf_ok, f"Nordic walk-forward RMSE {r_term:.2f} with the term vs {r_base:.2f} without")) if not ok))
    return {"adopted": sign_ok and wf_ok, "sign_t_met": sign_ok, "walk_forward_met": wf_ok, "why": why.format(tm=spec(cfg)["t_min"]),
            "rmse_last_quarter": r_base, "rmse_with_term": r_term, "n_targets": int(len(both)),
            "n_targets_excess": int((both["excess_t_1"] == 1).sum()) if len(both) else 0}


def diagnostics(rows: pd.DataFrame) -> list[dict]:
    """Labelled diagnostics next to the pre-registered estimate; none of them enters the adoption rule."""
    out = []
    for label, r in (("excluding Microchip (the state's own source)", rows[rows["company"] != "microchip"]),
                     ("building only (drawdown rows dropped)", rows[~((rows["excess_lag"] == 1) & rows["state_lag"].eq("drawdown"))]),
                     ("drawdown only (building rows dropped)", rows[~((rows["excess_lag"] == 1) & rows["state_lag"].eq("building"))]),
                     ("keeping the |dGM| > max moves", rows.assign(accounting_event=False))):
        out.append({"spec": label, "role": "diagnostic", **estimate(r)})
    return out


def run(nordic: pd.Series, cfg: dict) -> dict:
    """Everything nordic_gm() needs: full-sample delta, walk-forward, adoption decision, diagnostics."""
    excess = load_excess(cfg)
    rows = peer_changes(load_peer_gm(), excess, cfg)
    states = pd.read_csv(CYCLE_STATE).dropna(subset=["state"])
    st = pd.Series(states["state"].values, index=pd.PeriodIndex(states["quarter"], freq="Q"))
    rows = rows.assign(state_lag=[st.get(q - spec(cfg)["state_lag_quarters"], np.nan) for q in rows["quarter"]])
    est = estimate(rows)
    wf = walk_forward(nordic, rows, excess, cfg)
    adopt = adoption(est, wf, cfg)
    effect = pd.DataFrame([{"spec": "pre-registered (F25)", "role": "adoption", **est}] + diagnostics(rows))
    return {"estimate": est, "walk_forward": wf, "adoption": adopt, "effect_table": effect, "excess": excess}

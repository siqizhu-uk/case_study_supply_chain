"""Step 7e — one model of the guide error for all three forecasts (decision F16).

The beat is management's forecast error (K1), so the quantity to forecast is that error, in one unit for every company:
the % miss over the guided horizon (quarterly revenue guides: actual / guide mid - 1; GN's August full-year organic
guide: outcome - guide mid, pts of full-year revenue, since H1 is known when it is set). Two parts:

    e_it = alpha_i + gamma x building_(t-1) + eps_it

  alpha_i   the company's habit (conservative or aggressive), partially pooled: alpha_i ~ N(mu, tau^2) with mu and tau^2
            from the 12 peers' quarterly guides (DerSimonian-Laird), and each company's own errors shrunk toward mu by
            w_i = tau^2 / (tau^2 + s_i^2 / n_i). Pooling needs an exchangeable population: Nordic's and Logitech's quarterly
            revenue guides pool with the peers' quarterly guides; GN's August full-year organic guide has no comparable
            population in the data, so its habit is its own record (unpooled, own spread). One rule replaces the
            regime-dated beats (F14) and the year filters (F15): the cycle is the state variable, not a date.
  gamma     the channel state known at the forecast date (step 3b cycle_state of quarter t-1; D22): the one contrast
            with an economic prior, distributors BUILDING stock -> the next quarter's orders fall short of the guide.
            Estimated on the peers with company fixed effects, errors clustered by quarter; used only if |t| >= t_min.
            This is where the supply chain's mechanism enters the guided quarters.
Prediction sd = sqrt(s_i^2 + var(alpha_i)), with s_i^2 pooled toward the peers' residual variance (prior weight nu).

F20 (analyst decision 2026-09-27): Nordic's own habit differs from the peers' (+3.5% vs +1.9%, t ~2), so pooling it
(weight 0.20) assumes an exchangeability its data reject, and the pooled model under-predicted it by ~2 pts in every
quarter of 2025-26. Nordic therefore uses its OWN record split by the data-dated channel state (not hand-dated regimes):
habit = its mean error when the channel was not building, effect = its own building-minus-not difference. The pooled
version stays as a pre-registered challenger (challenger_prereg_log.csv), scored at the print.

F30 (analyst decision 2026-09-27, with D24): a lean channel is not one condition. In 2020Q4-2022Q3 Nordic's distributors
were lean because supply was short (order backlog 4-10 quarters of revenue), and Nordic's revenue was set by its wafer
supply, so its guides were close (+1.9% on 7 quarters); after the 2023-24 destock the channel is lean by caution (+4.2%
on 7). Nordic's habit is therefore its mean error when the channel was neither building nor in a supply shortage
(step 3b state_nordic), with its own building and shortage effects. The rule before F30 (shortage merged into lean) is
pre-registered as a second challenger.

D25 challenger (2026-09-27, rule fixed before any result was computed): the same own-record model with the state read
from Nordic's OWN words about its distributors' stock in the report of the quarter before the guide: 'excess' when
it says distributors are destocking (coded below 0), 'shortage' when the D24 supply evidence holds and it does not,
otherwise the base. Not adopted: Nordic's words are published with the guide, so they are the information the guide
is least likely to miss; the Microchip state is outside information with a peer-tested effect. Pre-registered third.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from core.config import ROOT

PEERS = [ROOT / "pipelines" / "D_peer_panel" / "data" / "raw" / f for f in ("peer_panel.csv", "peer_history_panel.csv")]
STATES = ROOT / "steps" / "step3_inventory_mechanism" / "outputs" / "cycle_state.csv"


# ------------------------------------------------------------------ data
def states(column: str = "state") -> pd.Series:
    """The industry channel state (column 'state'); column 'state_nordic' adds Nordic's supply-shortage split (D24)."""
    s = pd.read_csv(STATES)
    col = column if column in s else "state"
    return pd.Series(s[col].values, index=pd.PeriodIndex(s["quarter"], freq="Q"))


def peer_errors() -> pd.DataFrame:
    d = pd.concat([pd.read_csv(f) for f in PEERS if f.exists()], ignore_index=True)
    d = d[~d["excluded"].fillna(False).astype(bool)].dropna(subset=["beat_pct"]).drop_duplicates(["company", "quarter"])
    return pd.DataFrame({"company": d["company"].str.lower(), "q": pd.PeriodIndex(d["quarter"], freq="Q"),
                         "error": d["beat_pct"].astype(float), "group": "peer", "instrument": "quarterly revenue guide"})


def company_errors(p: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Nordic and Logitech quarterly guides; GN's August full-year organic guide, dated to Q3 of that year."""
    from guidance_record import gn_statement_errors, logitech_quarters, nordic_quarters
    n = nordic_quarters(p).dropna(subset=["revenue_usdm"])
    lq = logitech_quarters().dropna(subset=["net_sales_usdm"])
    g = gn_statement_errors(cfg.get("guidance_anchor", {}).get("gn", {}).get("statement_month", 8)).dropna(subset=["error_pts"])
    return pd.concat([
        pd.DataFrame({"company": "Nordic", "q": n.index, "error": n["error_pct"].values, "instrument": "quarterly revenue guide"}),
        pd.DataFrame({"company": "Logitech", "q": lq.index, "error": lq["error_pct"].values, "instrument": "quarterly sales guide"}),
        pd.DataFrame({"company": "GN", "q": pd.PeriodIndex([f"{int(y)}Q3" for y in g["fiscal_year"]], freq="Q"),
                      "error": g["error_pts"].values, "instrument": "August full-year organic guide (pts)"}),
    ], ignore_index=True).assign(group="target")


def wording_states(p: pd.DataFrame) -> pd.Series:
    """Nordic's state from its own words (D25 challenger): excess (destocking, coded < 0), shortage (D24 supply evidence
    and not destocking), base otherwise; NaN before the wording starts."""
    w = p["nordic_dist_state"].dropna()
    w.index = pd.PeriodIndex([str(q) for q in w.index], freq="Q")
    sn = states("state_nordic")
    lab = ["excess" if v < 0 else ("shortage" if sn.get(q) == "shortage" else "base") for q, v in w.items()]
    return pd.Series(lab, index=w.index)


def with_state(d: pd.DataFrame, st: pd.Series, lag: int) -> pd.DataFrame:
    d = d.copy()
    d["state"] = [st.get(q - lag, np.nan) for q in d["q"]]
    d["building"] = (d["state"] == "building").astype(float)
    return d


# ------------------------------------------------------------------ estimation
def state_effect(peers: pd.DataFrame) -> dict:
    """gamma from peers with company fixed effects (within transformation), SE clustered by quarter."""
    d = peers.dropna(subset=["state"]).reset_index(drop=True)
    y = d["error"] - d.groupby("company")["error"].transform("mean")
    x = d["building"] - d.groupby("company")["building"].transform("mean")
    b = float((x * y).sum() / (x * x).sum())
    e = y - b * x
    u = (x * e).groupby(d["q"].astype(str)).sum()
    g = len(u)
    se = float(np.sqrt((u ** 2).sum() * g / (g - 1)) / (x * x).sum())
    return {"gamma": b, "se": se, "t": b / se, "n": len(d), "quarters": g}


def pooling_prior(peers: pd.DataFrame, gamma: float) -> dict:
    """DerSimonian-Laird: mu and tau^2 of the peers' habits (errors net of the state effect), plus the pooled residual sd."""
    r = peers.assign(res=peers["error"] - gamma * peers["building"])
    s = r.groupby("company")["res"].agg(["mean", "var", "count"])
    s = s[s["count"] >= 4]
    v = s["var"] / s["count"]
    w = 1 / v
    mu_fe = float((w * s["mean"]).sum() / w.sum())
    q = float((w * (s["mean"] - mu_fe) ** 2).sum())
    tau2 = max(0.0, (q - (len(s) - 1)) / (w.sum() - (w ** 2).sum() / w.sum()))
    ws = 1 / (v + tau2)
    mu = float((ws * s["mean"]).sum() / ws.sum())
    pooled_var = float(((s["count"] - 1) * s["var"]).sum() / (s["count"] - 1).sum())
    return {"mu": mu, "tau2": tau2, "tau": float(np.sqrt(tau2)), "resid_sd": float(np.sqrt(pooled_var)), "n_peers": len(s)}


def company_habit(errors: pd.Series, building: pd.Series, gamma: float, prior: dict, nu: float, pooled: bool = True) -> dict:
    res = errors - gamma * building
    n = len(res)
    if not pooled:                                                                  # no exchangeable population: own record
        s2 = float(res.var(ddof=1)) if n > 1 else prior["resid_sd"] ** 2
        return {"n": n, "own_mean": float(res.mean()), "weight_own": 1.0, "alpha": float(res.mean()), "alpha_sd": float(np.sqrt(s2 / n)),
                "resid_sd": float(np.sqrt(s2)), "pred_sd": float(np.sqrt(s2 + s2 / n)), "pooled": False}
    own_var = float(res.var(ddof=1)) if n > 1 else prior["resid_sd"] ** 2
    s2 = ((n - 1) * own_var + nu * prior["resid_sd"] ** 2) / (n - 1 + nu)        # residual variance pooled toward the peers
    w = prior["tau2"] / (prior["tau2"] + s2 / n) if n else 0.0
    alpha = w * float(res.mean()) + (1 - w) * prior["mu"]
    var_alpha = 1 / (n / s2 + 1 / prior["tau2"]) if prior["tau2"] > 0 else s2 / n
    return {"n": n, "own_mean": float(res.mean()), "weight_own": w, "alpha": alpha, "alpha_sd": float(np.sqrt(var_alpha)),
            "resid_sd": float(np.sqrt(s2)), "pred_sd": float(np.sqrt(s2 + var_alpha)), "pooled": True}


def own_state_habit(errors: pd.Series, building: pd.Series, shortage: pd.Series | None = None) -> dict:
    """A company's own record split by the channel state: habit when neither building nor in a supply shortage, and its
    own building and shortage effects (F20, F30). Without a shortage series it is the rule before F30."""
    shortage = pd.Series(0.0, index=errors.index) if shortage is None else shortage.reindex(errors.index).fillna(0.0)
    if not ((building == 0) & (shortage == 0)).any():          # no quarter yet that was neither: the rule before F30
        shortage = pd.Series(0.0, index=errors.index)
    base, b, sh = errors[(building == 0) & (shortage == 0)], errors[building == 1], errors[(building == 0) & (shortage == 1)]
    alpha = float(base.mean())
    effect = float(b.mean() - alpha) if len(b) else 0.0
    sh_effect = float(sh.mean() - alpha) if len(sh) else 0.0
    groups = [g for g in (base - alpha, b - b.mean() if len(b) else None, sh - sh.mean() if len(sh) else None) if g is not None]
    res = pd.concat(groups)
    s2 = float((res ** 2).sum() / max(len(res) - len(groups), 1))
    return {"n": len(errors), "n_not_building": len(base), "n_building": len(b), "n_shortage": len(sh), "own_mean": alpha,
            "weight_own": 1.0, "alpha": alpha, "alpha_sd": float(np.sqrt(s2 / max(len(base), 1))), "resid_sd": float(np.sqrt(s2)),
            "pred_sd": float(np.sqrt(s2 + s2 / max(len(base), 1))), "pooled": False, "own_state": True, "own_building_effect": effect,
            "own_shortage_effect": sh_effect}


def fit(p: pd.DataFrame, cfg: dict, before: pd.Period | None = None, lag: int | None = None, shortage: bool = True,
        wording: bool = False) -> dict:
    """The whole model on data dated before `before` (walk-forward) or on everything. shortage=False is the rule before
    F30 (Nordic's supply-shortage quarters counted as lean); wording=True reads Nordic's state from its own words (D25)."""
    c = cfg["guide_error_model"]
    lag = c["state_lag_quarters"] if lag is None else lag
    st = states()
    peers = with_state(peer_errors(), st, lag)
    comp = with_state(company_errors(p, cfg), st, lag)
    applies = str(cfg.get("cycle_state", {}).get("shortage", {}).get("applies_to", "")).lower()
    sn = states("state_nordic")
    comp["shortage"] = [float(shortage and co.lower() == applies and sn.get(q - lag) == "shortage") for co, q in zip(comp["company"], comp["q"])]
    if wording:                                                        # D25 challenger: Nordic's state from its own words
        ws = wording_states(p)
        nd = comp["company"] == "Nordic"
        comp.loc[nd, "building"] = [float(ws.get(q - lag) == "excess") for q in comp.loc[nd, "q"]]
        comp.loc[nd, "shortage"] = [float(ws.get(q - lag) == "shortage") for q in comp.loc[nd, "q"]]
        comp = comp[~nd | comp["q"].map(lambda q: (q - lag) in ws.index)]
    if before is not None:
        peers, comp = peers[peers["q"] < before], comp[comp["q"] < before]
    se = state_effect(peers)
    gamma = se["gamma"] if abs(se["t"]) >= c["state_t_min"] else 0.0
    prior = pooling_prior(peers, gamma)
    own_state = set(c.get("own_state_effect", []))
    no_state = set(c.get("no_state_adjustment", []))        # F23: gamma is a quarterly revenue-miss effect in %; not for annual pts
    habits = {}
    for co, g in comp.groupby("company"):
        if co in own_state:
            habits[co] = own_state_habit(g["error"], g["building"], g["shortage"] if shortage else None)
        elif co in no_state:
            habits[co] = {**company_habit(g["error"], g["building"] * 0, 0.0, prior, c["variance_prior_weight"], co in c["pooled_with_peers"]),
                          "state_adjusted": False}
        else:
            habits[co] = company_habit(g["error"], g["building"], gamma, prior, c["variance_prior_weight"], co in c["pooled_with_peers"])
    challengers = {co: company_habit(g["error"], g["building"], gamma, prior, c["variance_prior_weight"], True)
                   for co, g in comp.groupby("company") if co in c.get("challenger_pooled", [])}
    return {"state_effect": se, "gamma_used": gamma, "prior": prior, "habits": habits, "challengers": challengers, "lag": lag,
            "shortage": shortage, "wording": wording_states(p) if wording else None}


def predict(model: dict, company: str, target: pd.Period, challenger: bool = False) -> dict:
    """Expected guide error and its sd for `target`, with the state known at the forecast date."""
    st = states().get(target - model["lag"], np.nan)
    sn = states("state_nordic").get(target - model["lag"], np.nan) if model.get("shortage", True) else st
    if model.get("wording") is not None and company == "Nordic":        # D25 challenger: its own words set the state
        w = model["wording"].get(target - model["lag"], np.nan)
        st, sn = ("building" if w == "excess" else w), w
    h = model["challengers"][company] if challenger else model["habits"][company]
    effect = h["own_building_effect"] if h.get("own_state") else (0.0 if h.get("state_adjusted") is False else model["gamma_used"])
    g = effect * float(st == "building")
    g += h.get("own_shortage_effect", 0.0) * float(h.get("own_state", False) and sn == "shortage")
    return {"expected_error": h["alpha"] + g, "sd": h["pred_sd"], "state": st, "state_nordic": sn, "alpha": h["alpha"],
            "gamma_applied": g, "building_effect": effect, "shortage_effect": h.get("own_shortage_effect", 0.0)}


# ------------------------------------------------------------------ walk-forward check (Nordic)
def walk_forward_nordic(p: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Each Nordic quarter from backtest.first_target, predicted with data before it; vs the past-4-quarter beat (GB)."""
    from guidance_record import nordic_quarters
    n = nordic_quarters(p).dropna(subset=["revenue_usdm"])
    first = pd.Period(cfg["backtest"]["first_target"], "Q")
    rows = []
    for t in n.index[n.index >= first]:
        m = fit(p, cfg, before=t)
        pr = predict(m, "Nordic", t)
        pv = predict(fit(p, cfg, before=t, shortage=False), "Nordic", t)
        pw = predict(fit(p, cfg, before=t, wording=True), "Nordic", t)
        ch = predict(m, "Nordic", t, challenger=True) if "Nordic" in m["challengers"] else pr
        past = n["error_pct"][n.index < t].tail(cfg["backtest"]["beat_window_quarters"])
        rows.append({"quarter": str(t), "actual_error": float(n.loc[t, "error_pct"]), "model": pr["expected_error"],
                     "pooled_challenger": ch["expected_error"], "previous_rule": pv["expected_error"],
                     "wording_rule": pw["expected_error"], "state": pr["state"],
                     "state_nordic": pr["state_nordic"],
                     "past4_beat": float(past.mean()) if len(past) else 0.0, "guide_mid": 0.0})
    w = pd.DataFrame(rows)
    return w


def scores(w: pd.DataFrame) -> dict:
    r = lambda c: float(np.sqrt(((w[c] - w["actual_error"]) ** 2).mean()))  # noqa: E731
    return {"n": len(w), "rmse_model_pts": r("model"), "rmse_pooled_challenger_pts": r("pooled_challenger"),
            "rmse_previous_rule_pts": r("previous_rule") if "previous_rule" in w else float("nan"),
            "rmse_wording_rule_pts": r("wording_rule") if "wording_rule" in w else float("nan"),
            "rmse_past4_pts": r("past4_beat"), "rmse_guide_mid_pts": r("guide_mid")}


# ------------------------------------------------------------------ record extension (F32, F33)
HISTORY = ROOT / "pipelines" / "A_company_financials" / "data" / "raw" / "nordic_guidance_history.csv"
EXT_FILE = "guide_error_record_extension.csv"


def record_extension(p: pd.DataFrame, cfg: dict, m: dict, wf: pd.DataFrame) -> dict:
    """What extending Nordic's record to 2019Q1 (F32) shows about the rule, computed each run (analyst decision F33: the
    rule stays; the two limitations it exposes are disclosed as risk flags R7-R8, not fixed by a new rule):
      1. the channel state cannot see an end-demand shock: base-group quarters whose guide was raised before the print
         (nordic_guidance_history.csv, action 'raised') carry the largest errors, and the habit with and without them;
      2. the state split has no walk-forward edge on the longer record: RMSE of the rule vs the guide midpoint and the
         pooled challenger."""
    from guidance_record import nordic_quarters
    n = nordic_quarters(p).dropna(subset=["revenue_usdm"])
    lag = m["lag"]
    sn = states("state_nordic")
    st = pd.Series([sn.get(q - lag, np.nan) for q in n.index], index=n.index)
    base = n[~st.isin(["building", "shortage"])]
    split = pd.Period("2021Q1", "Q")
    raised = {}
    if HISTORY.exists():
        h = pd.read_csv(HISTORY, dtype=str)
        h = h[(h["metric"] == "revenue_usdm") & h["period"].str.match(r"^\d{4}Q\d$")].sort_values("statement_date")
        for q, g in h.groupby("period"):
            if (g["action"] == "raised").any():
                last = g.iloc[-1]
                raised[pd.Period(q, "Q")] = (float(last["low"]) + float(last["high"])) / 2
    shocks = [q for q in base.index if q in raised]
    ex = base.drop(shocks)
    sc = scores(wf) if len(wf) else {}
    out = {"first_quarter": str(n.index.min()), "last_quarter": str(n.index.max()), "n_guides": len(n),
           "n_base": len(base), "base_mean_pct": float(base["error_pct"].mean()),
           "n_base_before_2021": int((base.index < split).sum()), "base_mean_before_2021_pct": float(base.loc[base.index < split, "error_pct"].mean()),
           "n_base_from_2021": int((base.index >= split).sum()), "base_mean_from_2021_pct": float(base.loc[base.index >= split, "error_pct"].mean()),
           "shock_quarters": ", ".join(str(q) for q in shocks),
           "shock_errors_vs_initial_pct": ", ".join(f"{base.loc[q, 'error_pct']:+.1f}" for q in shocks),
           "shock_errors_vs_last_guide_pct": ", ".join(f"{(n.loc[q, 'revenue_usdm'] / raised[q] - 1) * 100:+.1f}" for q in shocks),
           "shock_states": ", ".join(str(st.get(q)) for q in shocks),
           "base_mean_ex_shocks_pct": float(ex["error_pct"].mean()) if len(ex) else float("nan"), "n_base_ex_shocks": len(ex),
           "wf_n": int(sc.get("n", 0)), "wf_rmse_rule": sc.get("rmse_model_pts", float("nan")), "wf_rmse_guide_mid": sc.get("rmse_guide_mid_pts", float("nan")),
           "wf_rmse_pooled": sc.get("rmse_pooled_challenger_pts", float("nan")), "wf_rmse_past4": sc.get("rmse_past4_pts", float("nan"))}
    return out


# ------------------------------------------------------------------ outputs
def run_guide_error_model(p: pd.DataFrame, cfg: dict, target: str = "2026Q3", write: bool = True) -> dict:
    from core.config import step_outputs
    t = pd.Period(target, "Q")
    m = fit(p, cfg)
    m2 = fit(p, cfg, lag=cfg["guide_error_model"]["state_lag_quarters"] + 1)          # robustness: state known one quarter earlier
    preds = {co: predict(m, co, t) for co in m["habits"]}
    ch_preds = {co: predict(m, co, t, challenger=True) for co in m["challengers"]}
    prev = fit(p, cfg, shortage=False)                                                 # the rule before F30, a challenger
    prev_pred = predict(prev, "Nordic", t) if "Nordic" in prev["habits"] else None
    word = fit(p, cfg, wording=True)                                                   # D25: Nordic's own words as the state
    word_pred = predict(word, "Nordic", t) if "Nordic" in word["habits"] else None
    wf = walk_forward_nordic(p, cfg)
    out = {"model": m, "robust_lag": m2, "predictions": preds, "challenger_predictions": ch_preds, "walk_forward": wf, "scores": scores(wf),
           "previous_rule": prev, "previous_rule_prediction": prev_pred, "wording_rule": word, "wording_rule_prediction": word_pred,
           "extension": record_extension(p, cfg, m, wf)}
    if write:
        d = step_outputs("step7_forecast")
        pd.DataFrame([out["extension"]]).round(3).to_csv(d / EXT_FILE, index=False)
        rows = [{"company": co, **{k: v for k, v in h.items()}, **{f"pred_{k}": v for k, v in preds[co].items()},
                 "alpha_if_state_lag_plus_1": m2["habits"][co]["alpha"]} for co, h in m["habits"].items()]
        pd.DataFrame(rows).round(3).to_csv(d / "guide_error_model.csv", index=False)
        pd.DataFrame([{"lag": x["lag"], **x["state_effect"], "gamma_used": x["gamma_used"], **{f"prior_{k}": v for k, v in x["prior"].items()}}
                      for x in (m, m2)]).round(3).to_csv(d / "guide_error_state_effect.csv", index=False)
        wf.round(2).to_csv(d / "guide_error_walkforward_nordic.csv", index=False)
    return out


PREREG = ROOT / "steps" / "step7_forecast" / "outputs" / "challenger_prereg_log.csv"


def _hash(obj) -> str:
    import hashlib
    return hashlib.sha1(repr(obj).encode()).hexdigest()[:10]


def log_challenger(gem: dict, fn: dict, cfg: dict, target: str = "2026Q3") -> pd.DataFrame:
    """Pre-register the pooled (F16) Nordic forecast next to the main one, once per spec and data; scored after the print
    (fill actual_usdm). Spec hash = the model config + this module's source; data hash = the errors and states it read."""
    from datetime import date
    challengers = []
    if "Nordic" in gem.get("challenger_predictions", {}):
        challengers.append(("F16 pooled guide-error model", gem["challenger_predictions"]["Nordic"]))
    if gem.get("previous_rule_prediction"):
        challengers.append(("F20 before F30 (supply-shortage quarters counted as lean)", gem["previous_rule_prediction"]))
    if gem.get("wording_rule_prediction"):
        challengers.append(("D25 own record with Nordic's own words as the state", gem["wording_rule_prediction"]))
    if not challengers:
        return pd.DataFrame()
    mid = float(fn["guide_mid"])
    adj = float(sum(fn["signal_adjustments"].values()))
    spec = _hash((cfg["guide_error_model"], Path(__file__).read_text()))
    data = _hash((peer_errors()["error"].round(4).tolist(), states().astype(str).tolist(), round(float(gem["model"]["habits"]["Nordic"]["alpha"]), 6),
                  mid, round(adj, 4)))
    log = pd.read_csv(PREREG, dtype=str) if PREREG.exists() else pd.DataFrame()
    for name, ch in challengers:
        row = {"target": target, "company": "Nordic", "challenger": name, "spec_hash": spec, "data_hash": data,
               "logged_on": date.today().isoformat(), "guide_mid_usdm": mid, "challenger_error_pct": round(ch["expected_error"], 3),
               "challenger_usdm": round(mid * (1 + ch["expected_error"] / 100) + adj, 1), "main_error_pct": round(float(fn["hist_beat_pct"]), 3),
               "main_usdm": float(fn["point"]), "actual_usdm": "", "scored_on": ""}
        if log.empty:
            log = pd.DataFrame(columns=list(row))
        seen = (log["spec_hash"] == spec) & (log["data_hash"] == data) & (log["target"] == target) & (log["challenger"] == name)
        if not seen.any():
            log = pd.concat([log, pd.DataFrame([row]).astype(str)], ignore_index=True)
    log.to_csv(PREREG, index=False)
    return log

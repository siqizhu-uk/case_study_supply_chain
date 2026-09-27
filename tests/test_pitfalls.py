"""The pitfall register must stay complete: every row has evidence, cost, fix, a place in the repo and a guard."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_register_is_complete_and_points_to_real_files():
    p = pd.read_csv(ROOT / "audit" / "pitfalls.csv", dtype=str).fillna("")
    assert p["id"].is_unique
    for col in ("pitfall", "evidence", "impact_if_missed", "solution", "implemented_in", "guarded_by", "status"):
        assert (p[col].str.len() > 3).all(), col
    assert set(p["status"]) <= {"fixed", "avoided", "mitigated", "disclosed"}
    for f in p["implemented_in"]:
        path = f.split(" ")[0]
        if "/" in path:
            assert (ROOT / path).exists(), f

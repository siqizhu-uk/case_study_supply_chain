"""A fresh clone runs `./run.sh` with no network (P118): every Pipeline B processed file the steps read must be committed,
since Pipeline B rebuilds its processed tables only from the gitignored download cache."""
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pipeline_b_processed_files_read_by_the_model_are_committed():
    tracked = set(subprocess.run(["git", "ls-files", "pipelines/B_macro_industry/data/processed"], cwd=ROOT,
                                 capture_output=True, text=True, check=True).stdout.split())
    pat = re.compile(r'"B_macro_industry"\s*/\s*"data"\s*/\s*"processed"\s*/\s*"([\w.]+)"|MACRO_PROC\s*/\s*"([\w.]+)"')
    read = {m for f in [*ROOT.glob("steps/*/src/*.py"), *ROOT.glob("core/*.py")]
            for m in (a or b for a, b in pat.findall(f.read_text()))}
    assert read, "pattern found no reads - update the test"
    missing = {n for n in read if f"pipelines/B_macro_industry/data/processed/{n}" not in tracked}
    assert not missing, f"read by the model but gitignored (fresh clone fails): {missing}"

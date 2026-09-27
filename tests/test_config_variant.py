"""A --config variant reaches every module that loads the config (core.config.load_config, CASE_STUDY_CONFIG).
Run: pytest -q tests/test_config_variant.py"""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.config import CONFIG_PATH, load_config  # noqa: E402


def test_variant_config_reaches_every_loader(tmp_path, monkeypatch):
    base = yaml.safe_load(CONFIG_PATH.read_text())
    top = base["forecast"]["nordic_2026Q3"]["guide_high"]
    variant = tmp_path / "variant.yaml"
    variant.write_text(CONFIG_PATH.read_text().replace(f"    guide_high: {top}", f"    guide_high: {top + 10}", 1))
    monkeypatch.setenv("CASE_STUDY_CONFIG", str(variant))
    assert load_config()["forecast"]["nordic_2026Q3"]["guide_high"] == top + 10          # a module loading with no path
    monkeypatch.delenv("CASE_STUDY_CONFIG")
    assert load_config()["forecast"]["nordic_2026Q3"]["guide_high"] == top                # default: config/model.yaml

"""Tests for the historical-read CLI helpers."""

from importlib.util import module_from_spec, spec_from_file_location
from math import inf, nan
from pathlib import Path
from types import ModuleType


def load_script_module() -> ModuleType:
    script_path = Path(__file__).parents[1] / "scripts" / "run_historical_read.py"
    spec = spec_from_file_location("run_historical_read", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_row_value_skips_missing_and_non_finite_values() -> None:
    script = load_script_module()

    assert script._row_value({"Open": None}, "Open") is None
    assert script._row_value({"Open": nan}, "Open") is None
    assert script._row_value({"Open": inf}, "Open") is None
    assert script._row_value({"Open": "-inf"}, "Open") is None
    assert script._row_value({"Open": "123.45"}, "Open") == 123.45

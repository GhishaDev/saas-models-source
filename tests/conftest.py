"""Make the repo-root modules importable and expose the committed export."""

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def exported_models() -> dict:
    """The committed filtered_models.json, keyed by model_key."""
    with open(ROOT / "filtered_models.json", encoding="utf-8") as f:
        return json.load(f)["models"]

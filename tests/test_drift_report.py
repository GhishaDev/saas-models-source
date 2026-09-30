"""The drift classifier (drift_report.classify). Fixture dicts only, no network."""

from drift_report import classify, failing


def _model(**raw):
    return {"raw_data": raw}


def test_true_to_false_is_stale_true():
    report = classify({"m": _model(supports_vision=True)}, {"m": _model(supports_vision=False)})
    assert report["stale-true"] == [("m", "supports_vision", True, False)]
    assert report["missing-true"] == report["changed-false"] == []


def test_true_to_absent_is_stale_true():
    report = classify({"m": _model(supports_vision=True)}, {"m": _model()})
    assert report["stale-true"] == [("m", "supports_vision", True, None)]


def test_absent_to_true_is_missing_true():
    report = classify({"m": _model()}, {"m": _model(supports_reasoning=True)})
    assert report["missing-true"] == [("m", "supports_reasoning", None, True)]
    assert report["stale-true"] == []


def test_false_to_absent_is_changed_false():
    report = classify({"m": _model(supports_json_mode=False)}, {"m": _model()})
    assert report["changed-false"] == [("m", "supports_json_mode", False, None)]


def test_price_changes_and_additions_are_separated():
    committed = {"m": _model(input_cost_per_token=1e-06, output_cost_per_token=2e-06)}
    regenerated = {"m": _model(input_cost_per_token=2e-06, output_cost_per_token=2e-06, input_cost_per_token_batches=5e-07)}
    report = classify(committed, regenerated)
    assert report["price-changed"] == [("m", "input_cost_per_token", 1e-06, 2e-06)]
    assert report["price-added"] == [("m", "input_cost_per_token_batches", None, 5e-07)]


def test_removed_price_is_price_changed_not_ignored():
    report = classify({"m": _model(input_cost_per_image=1e-04)}, {"m": _model()})
    assert report["price-changed"] == [("m", "input_cost_per_image", 1e-04, None)]


def test_model_set_changes_are_reported():
    report = classify({"old": _model()}, {"new": _model()})
    assert report["model-added"] == [("new",)] and report["model-removed"] == [("old",)]


def test_identical_exports_have_no_drift():
    same = {"m": _model(supports_vision=True, input_cost_per_token=1e-06)}
    assert all(not rows for rows in classify(same, same).values())


def test_fail_on_selects_only_named_non_empty_categories():
    report = classify({"m": _model(supports_vision=True)}, {"m": _model()})
    assert failing(report, []) == []
    assert failing(report, ["missing-true"]) == []
    assert failing(report, ["stale-true"]) == ["stale-true"]
    assert failing(report, ["any"]) == ["stale-true"]

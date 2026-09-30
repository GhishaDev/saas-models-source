"""The capability-overlay policy checker (capability_check.find_violations)."""

from capability_check import find_violations


def _kinds(violations):
    return sorted((v.kind, v.key, v.flag) for v in violations)


def test_rejects_synth_flag_that_restates_upstream():
    tables = {"X_SYNTH_DATA": {"m": {"supports_vision": True}}}
    upstream = {"m": {"supports_vision": True}}
    assert _kinds(find_violations(tables, upstream, {})) == [("redundant", "m", "supports_vision")]


def test_rejects_redundant_flag_even_when_allowlisted():
    # An override upstream has caught up with must be retired, not kept.
    tables = {"X_SYNTH_DATA": {"m": {"supports_vision": True}}}
    upstream = {"m": {"supports_vision": True}}
    overrides = {("m", "supports_vision"): "https://vendor.example/docs"}
    assert _kinds(find_violations(tables, upstream, overrides)) == [("redundant", "m", "supports_vision")]


def test_accepts_differing_flag_listed_in_capability_overrides():
    tables = {"X_SYNTH_DATA": {"m": {"supports_pdf_input": False}}}
    upstream = {"m": {"supports_pdf_input": True}}
    overrides = {("m", "supports_pdf_input"): "https://vendor.example/docs"}
    assert find_violations(tables, upstream, overrides) == []


def test_rejects_differing_flag_not_in_capability_overrides():
    tables = {"X_SYNTH_DATA": {"m": {"supports_pdf_input": False}}}
    upstream = {"m": {"supports_pdf_input": True}}
    assert _kinds(find_violations(tables, upstream, {})) == [("unlisted-override", "m", "supports_pdf_input")]


def test_flag_upstream_does_not_define_counts_as_an_override():
    tables = {"X_SYNTH_DATA": {"m": {"supports_reasoning": True}}}
    upstream = {"m": {}}
    assert _kinds(find_violations(tables, upstream, {})) == [("unlisted-override", "m", "supports_reasoning")]


def test_prestaged_entry_absent_upstream_may_carry_any_flag():
    tables = {"X_SYNTH_DATA": {"new-model": {"supports_vision": True, "supports_reasoning": True}}}
    assert find_violations(tables, {}, {}) == []


def test_non_capability_fields_are_out_of_scope():
    tables = {"X_SYNTH_DATA": {"m": {"max_input_tokens": 1000000}}}
    upstream = {"m": {"max_input_tokens": 1000000}}
    assert find_violations(tables, upstream, {}) == []


def test_rejects_orphan_allowlist_entry():
    overrides = {("m", "supports_vision"): "https://vendor.example/docs"}
    assert _kinds(find_violations({}, {"m": {}}, overrides)) == [("orphan-override", "m", "supports_vision")]

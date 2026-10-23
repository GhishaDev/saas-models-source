"""Assertions on the committed export and on the policy tables themselves."""

import re

from model_sync_rules import ModelSyncRules

CLAUDE_OPUS_5_REQUIRED = (
    "supports_adaptive_thinking",
    "supports_output_config",
    "supports_xhigh_reasoning_effort",
    "supports_max_reasoning_effort",
)


def test_claude_opus_5_keeps_its_thinking_and_effort_flags(exported_models):
    # These came from a hand-written pre-staged entry until upstream caught up;
    # retiring that entry must not lose them.
    raw = exported_models["claude-opus-5"]["raw_data"]
    for flag in CLAUDE_OPUS_5_REQUIRED:
        assert raw.get(flag) is True, f"claude-opus-5 {flag} = {raw.get(flag)!r}"


def test_gpt_5_1_does_not_advertise_minimal_reasoning_effort(exported_models):
    # OpenAI: "Reasoning.effort supports: none (default), low, medium, and high."
    raw = exported_models["gpt-5.1"]["raw_data"]
    if raw.get("supports_minimal_reasoning_effort") is True:
        assert ("gpt-5.1", "supports_minimal_reasoning_effort") in ModelSyncRules.CAPABILITY_OVERRIDES


def test_every_capability_override_cites_a_vendor_url():
    for pair, source in ModelSyncRules.CAPABILITY_OVERRIDES.items():
        assert "https://" in source, f"{pair} has no vendor URL in its justification"


def test_bigmodel_capabilities_are_derived_not_written():
    for key, entry in ModelSyncRules.BIGMODEL_SYNTH_DATA.items():
        written = sorted(f for f in entry if f.startswith("supports_"))
        assert not written, f"{key} hand-writes {written}; capabilities come from CAPABILITY_MIRRORS"


def test_every_mirror_target_matches_its_source(exported_models):
    for target, source in ModelSyncRules.CAPABILITY_MIRRORS.items():
        if target not in exported_models:
            continue
        assert source in exported_models, f"{target} is exported but its mirror source {source} is not"
        caps = lambda key: {f: v for f, v in exported_models[key]["raw_data"].items() if f.startswith("supports_")}
        assert caps(target) == caps(source), f"{target} drifted from {source}"


def test_mirror_targets_hand_write_no_capabilities():
    tables = {n: getattr(ModelSyncRules, n) for n in dir(ModelSyncRules) if n.endswith("_SYNTH_DATA")}
    for target in ModelSyncRules.CAPABILITY_MIRRORS:
        for name, table in tables.items():
            written = sorted(f for f in table.get(target, {}) if f.startswith("supports_"))
            assert not written, f"{name}[{target!r}] writes {written}, which the mirror would overwrite"


def test_no_exported_model_is_a_stale_gpt_image_pdf_true(exported_models):
    # Every gpt-image model page: "Input modalities: text, image".
    for key, model in exported_models.items():
        if key.startswith("gpt-image"):
            assert model["raw_data"].get("supports_pdf_input") is not True, key


def test_every_apply_step_is_in_the_synth_pipeline():
    # A new apply_* classmethod that is never wired into SYNTH_PIPELINE is a
    # silent no-op: its overlay would simply never run.
    defined = {n for n, v in vars(ModelSyncRules).items() if n.startswith("apply_") and isinstance(v, classmethod)}
    wired = [step.__func__.__name__ for step in ModelSyncRules.SYNTH_PIPELINE]
    assert defined == set(wired), f"not wired: {sorted(defined - set(wired))}"
    assert len(wired) == len(set(wired)), "a step runs twice"


def test_known_stale_trues_stay_fixed(exported_models):
    # Each was confirmed against the vendor page and was wrong upstream.
    for key, flag in [
        ("gemini/gemini-2.5-flash-image", "supports_prompt_caching"),
        ("gemini/gemini-2.5-flash-image", "supports_pdf_input"),
        ("gpt-5.1", "supports_minimal_reasoning_effort"),
    ]:
        assert exported_models[key]["raw_data"].get(flag) is not True, f"{key} {flag}"


def test_named_gemini_families_are_title_cased():
    # The Gemini formatter assumed a version number first; "nano" in
    # gemini-nano-banana-2.1 was left lowercase as if it were the version.
    assert ModelSyncRules.format_model_name("gemini/gemini-nano-banana-2.1", "google") == "Gemini Nano Banana 2.1"
    assert ModelSyncRules.format_model_name("gemini/gemini-3.1-flash-lite", "google") == "Gemini 3.1 Flash-Lite"


def test_claude_aliases_share_capabilities_with_their_dated_snapshot(exported_models):
    # One model, two ids. Upstream's Models API-sourced flags once covered
    # only one side of five pairs; CAPABILITY_MIRRORS closes that, and this
    # catches a new pair before it ships split.
    caps = lambda key: {f: v for f, v in exported_models[key]["raw_data"].items() if f.startswith("supports_")}
    for key in exported_models:
        m = re.fullmatch(r"(claude-.+)-\d{8}", key)
        if m and m.group(1) in exported_models:
            assert caps(key) == caps(m.group(1)), f"{key} and {m.group(1)} disagree"


def test_decision_models_export_as_decision_type_on_both_routes(exported_models):
    for key in ModelSyncRules.TYPESAFE_ALLOWED_KEYS:
        entry = exported_models[key]
        assert entry["type"] == "decision", key
        # Billed per input token only; a zero output price must not drop it.
        assert entry["raw_data"]["input_cost_per_token"] > 0
        assert entry["raw_data"]["output_cost_per_token"] == 0
    for key in ModelSyncRules.GATEWAY_ENDPOINTS:
        endpoints = exported_models[key]["raw_data"]["supported_endpoints"]
        assert {"/v1/decisions", "/v1/systemone"} <= set(endpoints), key


def test_gateway_endpoints_merge_without_dropping_or_duplicating():
    models = {
        "gpt-6-luna": {"supported_endpoints": ["/v1/chat/completions", "/v1/decisions"]},
        "typesafe/jev-latest": {"mode": "evaluation"},
    }
    merged = ModelSyncRules.apply_gateway_endpoints(models)
    assert merged["gpt-6-luna"]["supported_endpoints"] == ["/v1/chat/completions", "/v1/decisions", "/v1/systemone"]
    assert merged["typesafe/jev-latest"]["supported_endpoints"] == ["/v1/decisions", "/v1/systemone"]
    assert "supported_endpoints" not in models["typesafe/jev-latest"], "input was mutated"


def test_jev_names_follow_typesafe_docs():
    assert ModelSyncRules.format_model_name("typesafe/jev-1.13.0", "typesafe") == "Jev 1.13"
    assert ModelSyncRules.format_model_name("typesafe/jev-latest", "typesafe") == "Jev Latest"

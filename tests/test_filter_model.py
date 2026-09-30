"""filter_model must hand capability flags to the export untouched.

The dashboard reads supports_* from raw_data, so any coercion, dropping or
renaming there silently changes what gets forwarded to LiteLLM.
"""

from model_sync_rules import ModelSyncRules


def test_raw_data_preserves_every_boolean_supports_flag_verbatim():
    flags = {
        "supports_vision": True,
        "supports_function_calling": True,
        "supports_reasoning": False,
        "supports_minimal_reasoning_effort": False,
        "supports_xhigh_reasoning_effort": True,
        "supports_adaptive_thinking": True,
        "supports_pdf_input": False,
        "supports_some_future_flag": True,
    }
    model_data = {
        "litellm_provider": "openai",
        "mode": "chat",
        "input_cost_per_token": 1e-06,
        "output_cost_per_token": 2e-06,
        **flags,
    }
    result = ModelSyncRules.filter_model("gpt-5", model_data)
    assert result is not None, "fixture model should pass the filters"
    raw = result["raw_data"]
    for flag, value in flags.items():
        assert flag in raw, f"{flag} dropped from raw_data"
        assert raw[flag] is value, f"{flag} changed from {value!r} to {raw[flag]!r}"

#!/usr/bin/env python3
"""
Model Sync Rules Configuration

Defines filtering and mapping rules for syncing models from LiteLLM data source
https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json
"""

from __future__ import annotations

import math
import re
from typing import Any, Callable


# CNY→USD FX policy (fixed, not live): 1 USD = 7.0 CNY. Mirrors the
# internal LiteLLM fork's VOLCENGINE_FX_POLICY.md. Change both sides
# together if the policy rate is repegged. Applies to the one remaining
# CNY-quoted vendor tariff in this file: Volcengine Seedance.
#
# Only route a vendor through here when it publishes CNY *and no USD book*.
# If the vendor publishes its own USD price, store that verbatim — vendor
# FX rates differ from our policy rate (DeepSeek's implied rate is 6.818),
# so deriving silently mis-bills. See DashScope and BytePlus, both
# USD-native, and the retired DeepSeek overlay.
_CNY_USD_FX_RATE = 7.0


def _cny_per_m_to_usd_per_token(cny_per_m: float, sig: int = 4) -> float:
    """Convert CNY per million tokens → USD per token, rounded to ``sig`` sig figs.

    Vendors billing in RMB (Volcengine Seedance) quote CNY/M. The
    raw division produces IEEE-754 float tails (46/7e6 →
    6.571428571428571e-06) that read as false precision in JSON. Rounding
    to 4 significant digits keeps the source CNY reversible
    (round(val * FX * 1e6) recovers the source CNY value) while shedding
    the noise. Matches the precision the LiteLLM upstream uses for its
    own USD prices (3–4 sig figs).
    """
    raw = cny_per_m / (_CNY_USD_FX_RATE * 1_000_000)
    if raw == 0:
        return 0.0
    digits = sig - int(math.floor(math.log10(abs(raw)))) - 1
    return round(raw, digits)


def _cny_per_image_to_usd_per_image(cny_per_image: float) -> float:
    """Convert CNY per image → USD per image at the policy FX rate, EXACTLY.

    Volcengine's Seedream image models are billed per generated image in CNY
    (元/张) rather than per token, so they need their own converter.

    Unlike the per-token helpers this one does NOT round. These values are
    compared field-by-field against the internal LiteLLM fork's own price
    table (GhishaDev/litellm-internal), which stores the unrounded quotient,
    and that table is the side that actually bills. A 4-sig-fig copy here
    would differ from the gateway in the 5th digit and turn every future
    reconciliation into a "is 0.08571 the same number as 0.085714…?"
    argument. Exact division makes the two tables byte-comparable.
    """
    return cny_per_image / _CNY_USD_FX_RATE


# Seedream record templates. Each alias/dated pair shares ONE object, so a
# price can only be written once: the 11 whitelisted Seedream keys are really
# 4 distinct tariffs, and hand-copying them 11 times is exactly how an alias
# and its dated twin drift apart.
#
# Key names mirror GhishaDev/litellm-internal, because the meaning of each key
# is defined by the gateway code that reads it
# (litellm/llms/volcengine/image_generation/cost_calculator.py).
_SEEDREAM_ENDPOINTS = ["/v1/images/generations", "/v1/images/edits"]
_SEEDREAM_SOURCE = "https://www.volcengine.com/docs/82379/1544106?lang=zh"

_SEEDREAM_PRO: dict[str, Any] = {
    "litellm_provider": "volcengine",
    "mode": "image_generation",
    "source": _SEEDREAM_SOURCE,
    "supported_endpoints": _SEEDREAM_ENDPOINTS,
    # Marginal rate: the first reference image is free, ¥0.02 from the 2nd.
    "input_cost_per_image": _cny_per_image_to_usd_per_image(0.02),
    # Fallback band, read only when no banded key matches. The gateway's own
    # table puts the <=1.5K single-image price here; this must agree with it.
    "output_cost_per_image": _cny_per_image_to_usd_per_image(0.30),
    "output_cost_per_image_1_5k_and_below": _cny_per_image_to_usd_per_image(0.30),
    "output_cost_per_image_above_1_5k": _cny_per_image_to_usd_per_image(0.60),
    "output_cost_per_image_layer_decomposition_1_5k_and_below": _cny_per_image_to_usd_per_image(0.15),
    "output_cost_per_image_layer_decomposition_above_1_5k": _cny_per_image_to_usd_per_image(0.30),
    "supports_vision": True,
}


def _seedream_flat(cny_per_image: float) -> dict[str, Any]:
    """A single-price Seedream SKU: one output rate, no bands, no input fee.

    These SKUs do not bill reference images, so they carry NO
    input_cost_per_image key at all — a 0.0 would be pushed to the gateway as
    a deployment-level override of a field the gateway does not define.
    """
    return {
        "litellm_provider": "volcengine",
        "mode": "image_generation",
        "source": _SEEDREAM_SOURCE,
        "supported_endpoints": _SEEDREAM_ENDPOINTS,
        "output_cost_per_image": _cny_per_image_to_usd_per_image(cny_per_image),
        "supports_vision": True,
    }


_SEEDREAM_FLAT_022 = _seedream_flat(0.22)   # 5-0 and 5-0-lite
_SEEDREAM_FLAT_025 = _seedream_flat(0.25)   # 4-5
_SEEDREAM_FLAT_020 = _seedream_flat(0.20)   # 4-0


def _usd_per_m_to_usd_per_token(usd_per_m: float, sig: int = 4) -> float:
    """Convert USD per million tokens → USD per token, rounded to ``sig`` sig figs.

    For vendors that publish USD natively (BytePlus ModelArk) — no FX step, so
    this is a pure /1e6. Kept as a helper anyway so the tariff tables below can
    carry the vendor's own USD/M figure verbatim (10.70, 4.30) instead of
    hand-converted exponents, which are easy to typo and hard to diff against
    the pricing page. Rounding matches _cny_per_m_to_usd_per_token.
    """
    raw = usd_per_m / 1_000_000
    if raw == 0:
        return 0.0
    digits = sig - int(math.floor(math.log10(abs(raw)))) - 1
    return round(raw, digits)


class ModelSyncRules:
    """Model sync rules configuration and utilities."""

    # Supported providers list
    PROVIDERS = [
        "openai",
        "anthropic",
        "gemini",
        "zai",
        "bigmodel",
        "deepseek",
        "moonshot",
        "dashscope",
        "volcengine",
        "byteplus",
        "new-api",
        "ecloud_aicc",
    ]

    # Provider name mapping (lowercase for DB consistency)
    PROVIDER_MAPPING = {
        "openai": "openai",
        "anthropic": "anthropic",
        "gemini": "google",
        "zai": "zai",
        "bigmodel": "bigmodel",
        "deepseek": "deepseek",
        "moonshot": "moonshot",
        "dashscope": "dashscope",
        "volcengine": "volcengine",
        "byteplus": "byteplus",
        "new-api": "new-api",
        "ecloud_aicc": "ecloud_aicc",
    }

    # zai/glm whitelist — only these keys are allowed through provider filter.
    # Includes models present on the LiteLLM source today, plus pre-staged SKUs
    # that exist on z.ai's official pricing page but are not yet synced upstream.
    # Pre-staged keys activate automatically once LiteLLM publishes them.
    ZAI_ALLOWED_KEYS = frozenset({
        # Currently on LiteLLM source
        "zai/glm-5",
        "zai/glm-4.7",
        "zai/glm-4.6",
        "zai/glm-4.5",
        "zai/glm-4.5v",
        "zai/glm-4.5-x",
        "zai/glm-4.5-air",
        "zai/glm-4.5-airx",
        "zai/glm-4.5-flash",
        "zai/glm-4-32b-0414-128k",
        "zai/glm-5.1",
        "zai/glm-5.2",
        "zai/glm-5.3",
        "zai/glm-5.3-flash",
        # Pre-staged: on docs.z.ai but missing from LiteLLM source
        # (verified against the pinned snapshot, 2026-09-30)
        "zai/glm-5.3-flashx",
        "zai/glm-5-turbo",
        "zai/glm-4.7-flashx",
        "zai/glm-5v-turbo",
        "zai/glm-4.6v",
        "zai/glm-4.6v-flashx",
        "zai/glm-ocr",
    })

    # Segment-level casing overrides for GLM friendly-name formatting.
    # Shared between zai/ and bigmodel/ providers (both expose GLM family SKUs).
    # str.title() handles the common cases; this map only patches branded suffixes
    # that Title-Case would mangle (FlashX, AirX, OCR, etc.).
    ZAI_NAME_SEGMENT_OVERRIDES = {
        "flashx": "FlashX",
        "airx": "AirX",
        "ocr": "OCR",
    }

    # Authoritative z.ai data overlay. Source: docs.z.ai (pricing, overview,
    # per-model guides, capability guides).
    #
    # Two roles:
    #   1. Pre-staged SKUs absent from upstream — complete records, and the
    #      only source for their capability flags.
    #   2. Overlays on upstream SKUs — ONLY fields upstream lacks or gets
    #      wrong. Capability flags here must be allowlisted in
    #      CAPABILITY_OVERRIDES (capability_check.py enforces it).
    #
    # ── How GLM capability flags are derived (2026-09-30) ─────────────────
    # z.ai documents capabilities per model GUIDE, and its overview table
    # maps each variant to its parent's guide — that mapping is the vendor's
    # own statement of family membership, so a variant inherits its parent
    # guide's capabilities:
    #     GLM-4.5-X / -Air / -AirX → glm-4.5      GLM-4.7-FlashX  → glm-4.7
    #     GLM-4.6V-FlashX          → glm-4.6v     GLM-5.3-FlashX  → glm-5.3-flash
    # Feature names map to LiteLLM flags as follows; nothing is set that the
    # vendor does not name:
    #     "Thinking" / "Deep Thinking"      → supports_reasoning
    #     "Function Call"                   → supports_function_calling, and
    #                                         supports_tool_choice (the
    #                                         function-calling guide documents
    #                                         `tool_choice`, "only supports
    #                                         `auto`")
    #     "Context Caching", or a published
    #     cached-input price                → supports_prompt_caching
    #     reasoning_effort levels           → supports_{max,low}_reasoning_effort
    #                                         ("only supported by GLM-5.2 and
    #                                         above"; values max / high, plus
    #                                         low on GLM-5.3 and 5.3-FLASH only)
    #
    # ⚠️ supports_response_schema is deliberately ABSENT on every GLM model.
    # z.ai's structured-output guide offers only {"type": "json_object"}; its
    # "Schema Validation" example validates client-side with the `jsonschema`
    # library. Setting the flag would make LiteLLM send a native json_schema
    # response_format z.ai does not implement, instead of falling back to
    # json_object. Upstream agrees (sets it on no zai/* key).
    #
    # GLM-5-Turbo and GLM-5V-Turbo are no longer on the z.ai overview or
    # pricing pages. They are kept by decision (2026-09-04) but NOT audited:
    # their existing flags are left as-is and no new ones are added, since
    # there is no current vendor page to derive them from.
    ZAI_SYNTH_DATA: dict[str, dict[str, Any]] = {
        # ── Pre-staged SKUs (absent upstream) ─────────────────────────────
        "zai/glm-5.3-flashx": {
            # Higher-throughput tier of GLM-5.3-Flash; overview maps it to the
            # glm-5.3-flash guide, which also documents 1M context and 128K
            # max output. List price per docs.z.ai pricing (2026-09-18):
            # $0.37 in / $0.075 cached / $1.25 out per M — three bare cells,
            # not the list+live pair z.ai uses for a discount.
            #
            # max_reasoning_effort: "GLM-5.2 and above" includes 5.3-FlashX.
            # low_reasoning_effort is NOT set — the thinking guide names only
            # "GLM-5.3 and GLM-5.3-FLASH" for `low`.
            "litellm_provider": "zai",
            "mode": "chat",
            "max_input_tokens": 1000000,
            "max_output_tokens": 128000,
            "input_cost_per_token": 3.7e-07,
            "output_cost_per_token": 1.25e-06,
            "cache_read_input_token_cost": 7.5e-08,
            "supports_reasoning": True,
            "supports_function_calling": True,
            "supports_tool_choice": True,
            "supports_prompt_caching": True,
            "supports_vision": True,
            "supports_max_reasoning_effort": True,
        },
        "zai/glm-5-turbo": {
            # Not audited — see the GLM-5-Turbo note above.
            "litellm_provider": "zai",
            "mode": "chat",
            "max_input_tokens": 200000,
            "max_output_tokens": 128000,
            "input_cost_per_token": 1.2e-06,
            "output_cost_per_token": 4.0e-06,
            "cache_read_input_token_cost": 0.24e-06,
            "supports_function_calling": True,
            "supports_vision": False,
        },
        "zai/glm-4.7-flashx": {
            # Inherits the glm-4.7 guide: Thinking, Function Call, Structured
            # Output (json_object only), Context Caching. Text-only.
            "litellm_provider": "zai",
            "mode": "chat",
            "max_input_tokens": 200000,
            "max_output_tokens": 128000,
            "input_cost_per_token": 0.07e-06,
            "output_cost_per_token": 0.4e-06,
            "cache_read_input_token_cost": 0.01e-06,
            "supports_reasoning": True,
            "supports_function_calling": True,
            "supports_tool_choice": True,
            "supports_prompt_caching": True,
            "supports_vision": False,
        },
        "zai/glm-5v-turbo": {
            # Not audited — see the GLM-5-Turbo note above.
            "litellm_provider": "zai",
            "mode": "chat",
            "max_input_tokens": 200000,
            "max_output_tokens": 128000,
            "input_cost_per_token": 1.2e-06,
            "output_cost_per_token": 4.0e-06,
            "cache_read_input_token_cost": 0.24e-06,
            "supports_function_calling": True,
            "supports_vision": True,
        },
        "zai/glm-4.6v": {
            # glm-4.6v guide: "native Function Calling"; overview: "Thinking
            # Mode Switch Support". Cached input is priced ($0.05).
            "litellm_provider": "zai",
            "mode": "chat",
            "max_input_tokens": 128000,
            "max_output_tokens": 32000,
            "input_cost_per_token": 0.3e-06,
            "output_cost_per_token": 0.9e-06,
            "cache_read_input_token_cost": 0.05e-06,
            "supports_reasoning": True,
            "supports_function_calling": True,
            "supports_tool_choice": True,
            "supports_prompt_caching": True,
            "supports_vision": True,
        },
        "zai/glm-4.6v-flashx": {
            # Inherits the glm-4.6v guide. Cached input is priced ($0.004).
            "litellm_provider": "zai",
            "mode": "chat",
            "max_input_tokens": 128000,
            "max_output_tokens": 32000,
            "input_cost_per_token": 0.04e-06,
            "output_cost_per_token": 0.4e-06,
            "cache_read_input_token_cost": 0.004e-06,
            "supports_reasoning": True,
            "supports_function_calling": True,
            "supports_tool_choice": True,
            "supports_prompt_caching": True,
            "supports_vision": True,
        },
        "zai/glm-ocr": {
            # A layout-parsing tool (overview links /api-reference/tools/
            # layout-parsing), not a chat model: no thinking, tools or cache.
            "litellm_provider": "zai",
            "mode": "chat",
            "max_input_tokens": None,
            "max_output_tokens": None,
            "input_cost_per_token": 0.03e-06,
            "output_cost_per_token": 0.03e-06,
            "supports_function_calling": False,
            "supports_vision": True,
        },
        # ── Overlays on upstream SKUs ─────────────────────────────────────
        # Price/context fields upstream lacks or gets wrong, plus capability
        # overrides — every supports_* below is listed in CAPABILITY_OVERRIDES.
        #
        # Retired 2026-09-30, upstream now carrying them identically:
        # zai/glm-5.1, zai/glm-5.2 and zai/glm-5.3 pre-staged records (prices,
        # context, function calling). Their placeholder supports_vision=False
        # and supports_json_mode=False were dropped rather than allowlisted:
        # upstream leaves both undefined, and false/absent are equivalent to
        # every reader (the dashboard forwards only true).
        "zai/glm-5.3-flash": {
            # 1M context is one million, not 1024². docs.z.ai says "context
            # lengths of up to one million tokens"; upstream stores 1048576,
            # while its own glm-5.2 / glm-5.3 say 1000000. (v1.16.29)
            "max_input_tokens": 1000000,
            "supports_max_reasoning_effort": True,
            "supports_low_reasoning_effort": True,
        },
        "zai/glm-5.3": {
            "supports_max_reasoning_effort": True,
            "supports_low_reasoning_effort": True,
        },
        "zai/glm-5.2": {
            "supports_max_reasoning_effort": True,
        },
        "zai/glm-4.5v": {
            # z.ai overview lists 64K context; upstream says 128K.
            "max_input_tokens": 64000,
            "cache_read_input_token_cost": 0.11e-06,
            "supports_reasoning": True,
            "supports_prompt_caching": True,
        },
        "zai/glm-4.5": {
            "cache_read_input_token_cost": 0.11e-06,
            "supports_reasoning": True,
            "supports_prompt_caching": True,
        },
        "zai/glm-4.5-x": {
            "cache_read_input_token_cost": 0.45e-06,
            "supports_reasoning": True,
            "supports_prompt_caching": True,
        },
        "zai/glm-4.5-air": {
            "cache_read_input_token_cost": 0.03e-06,
            "supports_reasoning": True,
            "supports_prompt_caching": True,
        },
        "zai/glm-4.5-airx": {
            "cache_read_input_token_cost": 0.22e-06,
            "supports_reasoning": True,
            "supports_prompt_caching": True,
        },
        # zai/glm-4-32b-0414-128k: no cached-input price on z.ai pricing ("-")
        # and not in the thinking guide's model list — nothing to add.
    }

    # ── Bigmodel (智谱开放平台 / bigmodel.cn) ──────────────────────────────
    # China-domestic counterpart to z.ai international. Same GLM models,
    # exposed under a distinct provider namespace so downstream consumers can
    # pick the gateway they actually call.
    #
    # Pricing policy: bigmodel/* mirrors z.ai international (USD) verbatim.
    # bigmodel.cn's domestic RMB tariff is intentionally NOT reflected here.
    # See apply_bigmodel_synth for the mirroring mechanic.

    # Reverse-whitelist for bigmodel/glm-* SKUs. Only models with a sibling
    # zai/* entry providing input/output/cache prices are included.
    # Excluded (no public API pricing on bigmodel.cn, only private-instance
    # GPU-day rates): glm-4.6, glm-4.5, glm-4.5-x, glm-4.5-airx,
    # glm-4-32b-0414-128k, glm-ocr. glm-4.5-flash / glm-4.6v-flash are
    # free-tier and filtered separately via the Zero Price rule.
    BIGMODEL_ALLOWED_KEYS = frozenset({
        "bigmodel/glm-5.2",
        "bigmodel/glm-5.3",
        "bigmodel/glm-5.3-flash",
        "bigmodel/glm-5.3-flashx",
        "bigmodel/glm-5",
        "bigmodel/glm-4.7",
        "bigmodel/glm-4.5v",
        "bigmodel/glm-4.5-air",
        "bigmodel/glm-5.1",
        "bigmodel/glm-5-turbo",
        "bigmodel/glm-4.7-flashx",
        "bigmodel/glm-5v-turbo",
        "bigmodel/glm-4.6v",
        "bigmodel/glm-4.6v-flashx",
    })

    # Bigmodel SKU metadata. Neither prices nor capability flags are stored
    # here — both are derived from the sibling zai/<sku>, so the two
    # namespaces cannot disagree:
    #   • prices: apply_bigmodel_synth mirrors _BIGMODEL_MIRRORED_PRICE_FIELDS;
    #   • supports_*: CAPABILITY_MIRRORS maps every bigmodel/<sku> to
    #     zai/<sku>, applied by apply_capability_mirrors.
    # Each entry only carries the context window and the provider label.
    #
    # Source for context: docs.z.ai/guides/overview/overview (same models).
    #
    # Every bigmodel/* SKU is pre-staged (LiteLLM upstream does not carry
    # bigmodel/* keys), so apply_bigmodel_synth injects them wholesale.
    BIGMODEL_SYNTH_DATA: dict[str, dict[str, Any]] = {
        # Text models
        "bigmodel/glm-5.2": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 1000000,
            "max_output_tokens": 128000,
        },
        "bigmodel/glm-5.3": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 1000000,
            "max_output_tokens": 128000,
        },
        "bigmodel/glm-5.3-flashx": {
            # Domestic bigmodel quotes CNY (2 / 7 / 0.57 元 per M), but this
            # catalogue mirrors the z.ai USD book for bigmodel/*, as it has
            # since v1.9.0.
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 1000000,
            "max_output_tokens": 128000,
        },
        "bigmodel/glm-5.3-flash": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 1000000,
            "max_output_tokens": 128000,
        },
        "bigmodel/glm-5": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 200000,
            "max_output_tokens": 128000,
        },
        "bigmodel/glm-4.7": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 200000,
            "max_output_tokens": 128000,
        },
        "bigmodel/glm-4.5-air": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 128000,
            "max_output_tokens": 32000,
        },
        "bigmodel/glm-5.1": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 200000,
            "max_output_tokens": 128000,
        },
        "bigmodel/glm-5-turbo": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 200000,
            "max_output_tokens": 128000,
        },
        "bigmodel/glm-4.7-flashx": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 200000,
            "max_output_tokens": 128000,
        },
        # Vision models
        "bigmodel/glm-5v-turbo": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 200000,
            "max_output_tokens": 128000,
        },
        "bigmodel/glm-4.6v": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 128000,
            "max_output_tokens": 32000,
        },
        "bigmodel/glm-4.6v-flashx": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 128000,
            "max_output_tokens": 32000,
        },
        "bigmodel/glm-4.5v": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 64000,
            "max_output_tokens": 32000,
        },
    }

    # Price fields mirrored from zai/<sku> onto bigmodel/<sku>.
    # Only these three propagate; everything else is bigmodel-owned metadata.
    _BIGMODEL_MIRRORED_PRICE_FIELDS = (
        "input_cost_per_token",
        "output_cost_per_token",
        "cache_read_input_token_cost",
    )

    # ── DeepSeek (api.deepseek.com) ───────────────────────────────────────
    # Reverse-whitelist for deepseek/* SKUs. The official pricing page
    # (api-docs.deepseek.com/quick_start/pricing, snapshot 2026-09-16) lists
    # exactly TWO models, and these are they:
    #
    #   deepseek-flash    DeepSeek-V4.1-Flash   $0.30 / $1.20, cache $0.006
    #                     1M ctx, 384K out, VISION, FIM (non-thinking only)
    #   deepseek-v4-pro   DeepSeek-V4-Pro-0813  $1.32 / $3.96, cache $0.044
    #                     1M ctx, 384K out, no vision
    #   (peak rates; off-peak is exactly half — see the note below)
    #
    # deepseek-v4-flash is carried as a THIRD key: a legacy alias, not a
    # third model. DeepSeek consolidated the Flash line into V4.1-Flash
    # (vision built in) and renamed the SKU to plain "deepseek-flash", with
    # this footnote:
    #
    #   "The legacy names deepseek-v4-flash and deepseek-v4-flash-vision-exp
    #    are still accepted, but the corresponding models have been retired,
    #    their requests are served by the DeepSeek-V4.1-Flash model and
    #    billed at the Flash price."
    #
    # So unlike the shut-down OpenAI/Gemini keys retired in v1.16.31/32, the
    # legacy names still RESOLVE. deepseek-v4-flash is kept so callers that
    # already reference it keep working; upstream carries it byte-identical
    # to deepseek-flash (verified 2026-09-16), so it picks up the V4.1 price
    # automatically and cannot drift from the canonical entry.
    #
    # ⚠️ Its friendly name renders "DeepSeek-V4-Flash", but the model behind
    # it is V4.1-Flash. The name comes from the key, and the key is the
    # legacy one. Prefer deepseek-flash for anything new.
    #
    # deepseek-v4-flash-vision-exp stays OUT (retired v1.16.33): it names an
    # experimental vision variant that no longer exists as a distinct model,
    # and V4.1-Flash has vision natively, so the key is actively misleading
    # rather than merely redundant.
    #
    # Excluded for being deprecated / no longer listed officially:
    #   - deepseek-chat, deepseek-reasoner: scheduled deprecation 2026-07-24
    #   - deepseek-v3, deepseek-v3.2, deepseek-r1, deepseek-coder:
    #     superseded by V4, not on official pricing page
    DEEPSEEK_ALLOWED_KEYS = frozenset({
        "deepseek/deepseek-flash",
        "deepseek/deepseek-v4-flash",
        "deepseek/deepseek-v4.1-flash",
        "deepseek/deepseek-v4-pro",
    })

    # DeepSeek alias mirrors: <alias key> -> <canonical source key>.
    #
    # ⚠️ deepseek-v4.1-flash IS NOT A DEEPSEEK API NAME. On
    # api-docs.deepseek.com "DeepSeek-V4.1-Flash" appears only in the MODEL
    # VERSION row; the callable names are exactly deepseek-flash,
    # deepseek-v4-flash, deepseek-v4-flash-vision-exp and deepseek-v4-pro.
    # Upstream carries no deepseek/deepseek-v4.1-flash either — only
    # third-party rehosts use the v4.1 spelling
    # (openrouter/deepseek/deepseek-v4.1-flash,
    # fireworks_ai/.../deepseek-v4p1-flash).
    #
    # It is carried as a PROJECT alias by request, for gateways that expose
    # the version-style name to their own callers. A request sent straight
    # to api.deepseek.com under this name is expected to fail; route it to
    # deepseek-flash.
    #
    # MIRRORED, NOT HAND-WRITTEN. Copying the canonical entry at build time
    # is what keeps the alias from drifting. Six overlays in this file have
    # rotted from a hand-copied price (v1.16.18 / 20 / 23 / 24 / 29 / 30),
    # and an alias whose price is a literal is that same failure waiting to
    # happen. Same mechanic as NEWAPI_MIRROR_SOURCES, minus the
    # litellm_provider rewrite since the namespace is unchanged.
    DEEPSEEK_ALIAS_SOURCES: dict[str, str] = {
        "deepseek/deepseek-v4.1-flash": "deepseek/deepseek-flash",
    }

    # Moonshot (Kimi) whitelist — reverse-whitelist for moonshot/* keys.
    # Scope is exactly the "Multi-modal Model" table of platform.kimi.ai's
    # official Model List (snapshot 2026-09-04): the four SKUs below and
    # nothing else. Upstream still carries the whole deprecated back
    # catalogue (kimi-k2.5, the moonshot-v1 family, kimi-latest, the kimi-k2
    # previews — all retired by 2026-08-31 and now returning 404), which is
    # what the whitelist keeps out.
    #
    # kimi-k3 / kimi-k2.7-code / kimi-k2.7-code-highspeed are pre-staged and
    # injected via MOONSHOT_SYNTH_DATA (absent upstream). kimi-k2.6 is NOT —
    # upstream carries it complete and correct, so it is whitelisted only.
    MOONSHOT_ALLOWED_KEYS = frozenset({
        "moonshot/kimi-k3",
        "moonshot/kimi-k2.7-code",
        "moonshot/kimi-k2.7-code-highspeed",
        "moonshot/kimi-k2.6",
    })

    # Moonshot / Kimi. kimi-k3 and kimi-k2.7-code were pre-staged and are now
    # carried upstream, so their entries hold only what upstream lacks;
    # kimi-k2.7-code-highspeed is still absent upstream and stays a complete
    # record. Prices from platform.kimi.ai/docs/pricing.
    #
    # Retired 2026-09-30, upstream now carrying them identically: prices,
    # context and the core capability flags of kimi-k3 / kimi-k2.7-code. Also
    # dropped: supports_system_messages / _native_streaming /
    # _parallel_function_calling. Upstream never set them, they are not in
    # the catalogue's minimum flag set, and the LiteLLM fork reads them only
    # in the OpenAI o-series / Azure / Vertex transformations — never for
    # moonshot — so they were forwarded with no effect.
    #
    # ⚠️ KNOWN GAP, not addressed here: platform.kimi.ai now bills kimi-k3
    # cache WRITES — $3.00 (5-min TTL) and $6.00 (1-hour TTL) per M — and
    # neither upstream nor this file carries cache_creation_input_token_cost.
    # Whether that under-bills depends on how Kimi reports write tokens in
    # `usage`; to be investigated separately (seen 2026-09-30).
    MOONSHOT_SYNTH_DATA: dict[str, dict[str, Any]] = {
        "moonshot/kimi-k3": {
            "input_cost_per_token_cache_hit": 3e-07,
            "supported_endpoints": ["/v1/chat/completions"],
            # CAPABILITY_OVERRIDES: upstream leaves it undefined; Kimi documents
            # automatic prefix caching with a published cached-input price.
            "supports_prompt_caching": True,
            # CAPABILITY_OVERRIDES: `max` is K3's documented DEFAULT effort.
            "supports_max_reasoning_effort": True,
        },
        "moonshot/kimi-k2.7-code": {
            "input_cost_per_token_cache_hit": 1.9e-07,
            "source": "https://platform.kimi.ai/docs/pricing/chat-k2.7-code",
            "supported_endpoints": ["/v1/chat/completions"],
        },
        # Kimi K2.7 Code HighSpeed — "the same model as Kimi K2.7 Code, but
        # with an output speed of approximately 180 Tokens/s" (vendor). $1.90
        # in / $8.00 out per M, cache-hit $0.38; 256K context. Capability flags
        # are NOT written here: CAPABILITY_MIRRORS copies them from
        # kimi-k2.7-code, so "same model" stays true by construction.
        "moonshot/kimi-k2.7-code-highspeed": {
            "litellm_provider": "moonshot",
            "mode": "chat",
            "input_cost_per_token": 1.9e-06,
            "output_cost_per_token": 8e-06,
            "cache_read_input_token_cost": 3.8e-07,
            "input_cost_per_token_cache_hit": 3.8e-07,
            "max_input_tokens": 262144,
            "max_output_tokens": 262144,
            "max_tokens": 262144,
            "source": "https://platform.kimi.ai/docs/pricing/chat-k2.7-code",
            "supported_endpoints": ["/v1/chat/completions"],
        },
    }

    # ── DashScope (Alibaba Cloud Model Studio / 阿里云百炼) ───────────────
    # "DashScope" is the API/SDK name (dashscope.aliyuncs.com,
    # DASHSCOPE_API_KEY); "Model Studio" / 百炼 is the product brand for the
    # same service. LiteLLM upstream names the provider after the technical
    # identifier — verified 2026-08-29: 45 upstream keys carry
    # litellm_provider "dashscope" and the "dashscope/" prefix, and there is
    # no competing bailian / alibaba / aliyun / modelscope label. Using the
    # same namespace means an upstream key of the same name merges cleanly
    # instead of colliding with an invented one.
    #
    # NOT related to ModelScope (魔搭): that is Alibaba's open-weights
    # community hub, a different product with no upstream provider label.
    DASHSCOPE_ALLOWED_KEYS = frozenset({
        # Qwen 3.8 generation. All three are single-tier on the official
        # tariff (no 阶梯计价 / input-size bands), which is what lets them fit
        # the flat input/output/cache_read schema this catalogue uses. The
        # 3.7 and older generations are mostly tiered and stay out until
        # tiered pricing is modelled — see the README for the gap.
        "dashscope/qwen3.8-flash",
        "dashscope/qwen3.8-max",
        "dashscope/qwen3.8-2.4t-a95b",
        # Qwen 3.7 generation. qwen3.7-plus and qwen3.7-flash are TIERED by
        # request input size; see the tiered_pricing note in
        # DASHSCOPE_SYNTH_DATA for how that is represented.
        "dashscope/qwen3.7-max",
        "dashscope/qwen3.7-plus",
        "dashscope/qwen3.7-flash",
    })

    # DashScope overlays. Upstream now carries qwen3.8-flash, qwen3.8-max,
    # qwen3.7-max and qwen3.7-plus; qwen3.8-2.4t-a95b and qwen3.7-flash are
    # still absent and stay complete pre-staged records.
    #
    # Currency: USD-native. Alibaba publishes two separate tariffs — domestic
    # 百炼 in CNY and International in USD. Upstream's dashscope prices are
    # the International USD figures (dashscope/qwen3.8-max is $2 / $6 while
    # 百炼 lists 12 / 36 CNY, which is NOT 12/7), so store USD directly. Do
    # NOT route these through _cny_per_m_to_usd_per_token.
    #
    # Capability flags follow Alibaba's own per-feature model lists:
    #   supports_response_schema — the structured-output guide's JSON Schema
    #     tab (2026-09-30): "Qwen3.7-Plus series, Qwen3.7-Flash series,
    #     Qwen3.7-Max series, Qwen3.8-Max series, and Qwen3.8-Flash series
    #     models." The open-source Qwen3.8 build (qwen3.8-2.4t-a95b) appears
    #     only on the JSON Object tab, so it does NOT get the flag.
    #   supports_vision — help.aliyun.com/zh/model-studio/vision image-count
    #     tiers: Qwen3.8-Max, Qwen3.8-Flash, Qwen3.7-Plus at 2,048 images;
    #     Qwen3.7-Flash and older at 256. qwen3.7-max is in neither tier.
    #
    # Retired 2026-09-30: dashscope/qwen3.8-flash. Pre-staged on 2026-08-29;
    # upstream now carries it with every price, context and capability field
    # identical. Two lessons from that entry, kept because they still apply:
    #   • Read cache prices off the published table; never derive them from a
    #     ratio. The ratio varies per model AND per currency (qwen3.8-flash
    #     $0.016 against $0.15 = 10.7%; qwen3.8-max $0.25 against $2 = 12.5%;
    #     the CNY book differs again). The flag is wrong three times over if
    #     you use the Context Cache doc's "typically 10% / 20%" rule of thumb.
    #   • Do not infer capabilities from absence on the "选择模型 / Recommended
    #     models" page: each category there is a curated shortlist ending in
    #     查看更多. qwen3.8-flash IS multimodal (model card: "Text & Code |
    #     Image | Video"; vision docs: top 2,048-image tier).
    DASHSCOPE_SYNTH_DATA: dict[str, dict[str, Any]] = {
        # Qwen3.8-2.4T-A95B — per its qwencloud.com/models card, "the
        # open-source release of Qwen's latest flagship", 2.4T total
        # parameters with ~95B activated. Same tariff as qwen3.8-max
        # ($2 / $6 / $0.25 per M) and the same published spec chips
        # ("1 M Context", "131.1 K Max Out"). Not on LiteLLM upstream, so
        # injected.
        #
        # supports_vision: the card does not carry an explicit modality tag
        # row, but it is the open-source build of the same flagship as
        # qwen3.8-max (tagged "Text & Code | Image | Video") and its own
        # benchmark list is multimodal — BabyVision 82.0, OSWorld 86.1.
        # Weaker evidence than flash/max; revisit if Alibaba publishes a
        # modality table for it.
        "dashscope/qwen3.8-2.4t-a95b": {
            "litellm_provider": "dashscope",
            "mode": "chat",
            "max_input_tokens": 991808,
            "max_output_tokens": 131072,
            "max_tokens": 131072,
            "source": "https://www.qwencloud.com/pricing/api",
            "input_cost_per_token": _usd_per_m_to_usd_per_token(2.0),
            "output_cost_per_token": _usd_per_m_to_usd_per_token(6.0),
            "cache_read_input_token_cost": _usd_per_m_to_usd_per_token(0.25),
            "supports_function_calling": True,
            "supports_tool_choice": True,
            "supports_reasoning": True,
            "supports_prompt_caching": True,
            "supports_vision": True,
        },
        # ── Qwen 3.7 ─────────────────────────────────────────────────────
        # PRICES ARE THE EFFECTIVE (DISCOUNTED) ONES, per request: store what
        # callers are actually billed today. qwencloud shows the promotions
        # as strikethrough list + live price, with no published end date —
        # so unlike the GLM-5.3-Flash overlay (which carries a 2026-09-09
        # deadline) there is no date to schedule a revert against. Each entry
        # therefore records its list price inline so restoring it is a
        # copy-paste once the promotion lapses.
        #
        # HOW TO TELL A PROMOTION HAS LAPSED. qwencloud's price cells are
        # machine-readable: a discounted cell renders three spans —
        # `originalPrice`, `discountedPrice`, `discountTag` ("20% off") —
        # while an undiscounted cell is a bare price string. Check the cell
        # markup, not the rendered number; a promotion ending looks exactly
        # like a price rise if you only read the text. qwen3.7-max lapsed
        # this way on 2026-09-04 (see the retirement note below).
        #
        # TIERED PRICING. qwen3.7-plus and qwen3.7-flash bill at a unit price
        # that depends on the request's total input size (阶梯计价). Both the
        # full ladder and flat fields are written:
        #   * tiered_pricing — the whole ladder, matching the upstream shape
        #     (range + per-tier costs), extended with a per-tier
        #     cache_read_input_token_cost since qwencloud publishes one.
        #     Tier-aware consumers should read this.
        #   * input/output/cache_read_cost — set to the HIGHEST tier. A
        #     consumer that ignores the ladder then over-bills (visible, and
        #     the customer complains) instead of under-billing (silent
        #     revenue loss). Same never-under-bill rule used for the DeepSeek
        #     peak tariff and the BytePlus list price.
        # dashscope/qwen3.7-max ENTRY RETIRED 2026-09-04.
        #
        # It existed for one reason: to overlay the 50%-off effective price
        # ($1.25 / $3.75 / $0.25) onto upstream, which carried the list price.
        # The promotion has ended — verified in the DOM, not by eyeballing the
        # number: the qwen3.7-max row is now three bare price cells with no
        # `discountTag`, while qwen3.7-plus in the same table still renders the
        # full originalPrice/discountedPrice/discountTag triple. Effective now
        # equals list ($2.5 / $7.5 / $0.5), which is exactly what upstream has,
        # so keeping the entry would under-bill by 50% on every token.
        #
        # Nothing else in the entry was load-bearing: upstream already carries
        # max_input_tokens 991808, max_output_tokens 65536, function_calling,
        # tool_choice, reasoning and prompt_caching identically. The two
        # negative flags were no-ops — upstream leaves supports_vision unset,
        # and supports_json_output reads supports_json_mode with a False
        # default. qwen3.7-max is still text-only: it appears in NEITHER
        # image-count tier of help.aliyun.com/zh/model-studio/vision (which
        # lists 3.8-Max / 3.8-Flash / 3.7-Plus at 2,048 images, and 3.7-Flash
        # and older at 256).
        "dashscope/qwen3.7-plus": {
            # Two tiers, currently 20% off. List: <=256K $0.4 / $1.6 / $0.08;
            # 256K-1M $1.2 / $4.8 / $0.24.
            "source": "https://www.qwencloud.com/pricing/api",
            "tiered_pricing": [
                {
                    "range": [0, 256000.0],
                    "input_cost_per_token": _usd_per_m_to_usd_per_token(0.32),
                    "output_cost_per_token": _usd_per_m_to_usd_per_token(1.28),
                    "cache_read_input_token_cost": _usd_per_m_to_usd_per_token(0.064),
                },
                {
                    "range": [256000.0, 1000000.0],
                    "input_cost_per_token": _usd_per_m_to_usd_per_token(0.96),
                    "output_cost_per_token": _usd_per_m_to_usd_per_token(3.84),
                    "cache_read_input_token_cost": _usd_per_m_to_usd_per_token(0.192),
                },
            ],
            # Flat fields = highest tier (256K-1M).
            "input_cost_per_token": _usd_per_m_to_usd_per_token(0.96),
            "output_cost_per_token": _usd_per_m_to_usd_per_token(3.84),
            "cache_read_input_token_cost": _usd_per_m_to_usd_per_token(0.192),
            # supports_vision comes from upstream (top 2,048-image tier per
            # the vision docs); nothing to override.
        },
        "dashscope/qwen3.7-flash": {
            # Three tiers, no promotion — these are list prices.
            # Not on LiteLLM upstream at all.
            "litellm_provider": "dashscope",
            "mode": "chat",
            "max_input_tokens": 991808,
            # max_output_tokens INFERRED from the 3.7 siblings upstream
            # (qwen3.7-max / qwen3.7-plus both 65,536); qwencloud publishes
            # spec chips only for the 3.8 cards. Correct if Alibaba states
            # a different figure.
            "max_output_tokens": 65536,
            "max_tokens": 65536,
            "source": "https://www.qwencloud.com/pricing/api",
            "tiered_pricing": [
                {
                    "range": [0, 32000.0],
                    "input_cost_per_token": _usd_per_m_to_usd_per_token(0.03),
                    "output_cost_per_token": _usd_per_m_to_usd_per_token(0.13),
                    "cache_read_input_token_cost": _usd_per_m_to_usd_per_token(0.006),
                },
                {
                    "range": [32000.0, 256000.0],
                    "input_cost_per_token": _usd_per_m_to_usd_per_token(0.1),
                    "output_cost_per_token": _usd_per_m_to_usd_per_token(0.4),
                    "cache_read_input_token_cost": _usd_per_m_to_usd_per_token(0.02),
                },
                {
                    "range": [256000.0, 1000000.0],
                    "input_cost_per_token": _usd_per_m_to_usd_per_token(0.2),
                    "output_cost_per_token": _usd_per_m_to_usd_per_token(0.8),
                    "cache_read_input_token_cost": _usd_per_m_to_usd_per_token(0.04),
                },
            ],
            # Flat fields = highest tier (256K-1M).
            "input_cost_per_token": _usd_per_m_to_usd_per_token(0.2),
            "output_cost_per_token": _usd_per_m_to_usd_per_token(0.8),
            "cache_read_input_token_cost": _usd_per_m_to_usd_per_token(0.04),
            "supports_function_calling": True,
            "supports_tool_choice": True,
            "supports_reasoning": True,
            "supports_prompt_caching": True,
            "supports_response_schema": True,
            # 256-image tier per the vision docs.
            "supports_vision": True,
        },
        # NOTE: dashscope/qwen3.8-max is deliberately absent from this dict.
        # Upstream already carries it, and its prices were checked field by
        # field against qwencloud.com/pricing/api on 2026-08-29 ($2 / $6 /
        # $0.25) — they match exactly, so whitelisting alone is enough and a
        # synth entry would only create a second place to keep in sync.
    }

    # ── Volcengine (ByteDance Ark — Doubao Seedance video) ────────────────
    # Reverse-whitelist for volcengine/* video SKUs. Source:
    #   https://www.volcengine.com/docs/82379/1544106 (Seedance 2.0 spec)
    #   https://www.volcengine.com/pricing (CNY/M-token tiers)
    # Both the dated official model ID (used by the Volcengine SDK by
    # default) and the date-less alias (carried by the LiteLLM source as
    # a long-lived shortcut) are whitelisted so deployments can pick
    # either form without falling outside this filter.
    VOLCENGINE_ALLOWED_KEYS = frozenset({
        # Dated official IDs
        "volcengine/doubao-seedance-2-0-260128",
        "volcengine/doubao-seedance-2-0-fast-260128",
        "volcengine/doubao-seedance-2-0-mini-260615",
        # Date-less aliases
        "volcengine/doubao-seedance-2-0",
        "volcengine/doubao-seedance-2-0-fast",
        "volcengine/doubao-seedance-2-0-mini",
        # Seedance 2.5 (date-less alias + dated snapshot)
        "volcengine/doubao-seedance-2-5",
        "volcengine/doubao-seedance-2-5-260628",
        # Seedream image models — the NON-video volcengine SKUs (scope was
        # Seedance video only until 2026-09-17). All 11 keys the internal
        # LiteLLM fork supports, so an operator sees every one of them in the
        # Add Model dropdown with its price pre-filled instead of having to
        # type a model id by hand.
        "volcengine/doubao-seedream-5-0-pro",
        "volcengine/doubao-seedream-5-0-pro-260628",
        "volcengine/doubao-seedream-5-0-lite",
        "volcengine/doubao-seedream-5-0-lite-260128",
        "volcengine/doubao-seedream-5-0",
        "volcengine/doubao-seedream-5-0-260128",
        "volcengine/doubao-seedream-4-5",
        "volcengine/doubao-seedream-4-5-251128",
        "volcengine/doubao-seedream-4-0",
        "volcengine/doubao-seedream-4-0-250828",
        "volcengine/doubao-seedream-4-0-20260415",
    })

    # Volcengine Seedance pre-stage. Upstream BerriAI/litellm/main does
    # not yet carry Seedance video entries (verified 2026-06-30: only
    # chat / embedding doubao SKUs are upstream). We synthesise the 6
    # video SKUs from the official Volcengine pricing page so the SaaS
    # catalogue can list them today; when upstream eventually publishes
    # these keys, the overlay merges on top with no shape change.
    #
    # Currency: USD/token. Volcengine officially bills per million
    # OUTPUT tokens in CNY (tiered by resolution and v2v); our internal
    # LiteLLM fork stores the USD/token equivalent at a fixed
    # 1 USD = 7.0 CNY policy rate (see
    # litellm/proxy/spend_tracking/VOLCENGINE_FX_POLICY.md in the fork
    # repo). The values below mirror that policy so saas-models-source
    # and the LiteLLM billing manager always agree on the per-token
    # USD figure they show / charge.
    VOLCENGINE_SYNTH_DATA: dict[str, dict[str, Any]] = {
        # Seedance 2.0 (standard) — all three resolution tiers active.
        # Price arg is the source CNY per million tokens; the helper
        # converts at the fixed 7.0 FX and rounds to 4 sig figs.
        "volcengine/doubao-seedance-2-0-260128": {
            "litellm_provider": "volcengine",
            "mode": "video_generation",
            "max_input_tokens": 1024,
            "max_output_tokens": 1024,
            "source": "https://www.volcengine.com/docs/82379/1544106",
            "output_cost_per_token": _cny_per_m_to_usd_per_token(46),
            "output_cost_per_token_with_input_video": _cny_per_m_to_usd_per_token(28),
            "output_cost_per_token_1080p": _cny_per_m_to_usd_per_token(51),
            "output_cost_per_token_1080p_with_input_video": _cny_per_m_to_usd_per_token(31),
            "output_cost_per_token_4k": _cny_per_m_to_usd_per_token(26),
            "output_cost_per_token_4k_with_input_video": _cny_per_m_to_usd_per_token(16),
        },
        "volcengine/doubao-seedance-2-0": {
            "litellm_provider": "volcengine",
            "mode": "video_generation",
            "max_input_tokens": 1024,
            "max_output_tokens": 1024,
            "source": "https://www.volcengine.com/docs/82379/1544106",
            "output_cost_per_token": _cny_per_m_to_usd_per_token(46),
            "output_cost_per_token_with_input_video": _cny_per_m_to_usd_per_token(28),
            "output_cost_per_token_1080p": _cny_per_m_to_usd_per_token(51),
            "output_cost_per_token_1080p_with_input_video": _cny_per_m_to_usd_per_token(31),
            "output_cost_per_token_4k": _cny_per_m_to_usd_per_token(26),
            "output_cost_per_token_4k_with_input_video": _cny_per_m_to_usd_per_token(16),
        },
        # Seedance 2.0 Fast — 720p only
        "volcengine/doubao-seedance-2-0-fast-260128": {
            "litellm_provider": "volcengine",
            "mode": "video_generation",
            "max_input_tokens": 1024,
            "max_output_tokens": 1024,
            "source": "https://www.volcengine.com/docs/82379/1544106",
            "output_cost_per_token": _cny_per_m_to_usd_per_token(37),
            "output_cost_per_token_with_input_video": _cny_per_m_to_usd_per_token(22),
        },
        "volcengine/doubao-seedance-2-0-fast": {
            "litellm_provider": "volcengine",
            "mode": "video_generation",
            "max_input_tokens": 1024,
            "max_output_tokens": 1024,
            "source": "https://www.volcengine.com/docs/82379/1544106",
            "output_cost_per_token": _cny_per_m_to_usd_per_token(37),
            "output_cost_per_token_with_input_video": _cny_per_m_to_usd_per_token(22),
        },
        # Seedance 2.0 Mini — 720p only
        "volcengine/doubao-seedance-2-0-mini-260615": {
            "litellm_provider": "volcengine",
            "mode": "video_generation",
            "max_input_tokens": 1024,
            "max_output_tokens": 1024,
            "source": "https://www.volcengine.com/docs/82379/1544106",
            "output_cost_per_token": _cny_per_m_to_usd_per_token(23),
            "output_cost_per_token_with_input_video": _cny_per_m_to_usd_per_token(14),
        },
        "volcengine/doubao-seedance-2-0-mini": {
            "litellm_provider": "volcengine",
            "mode": "video_generation",
            "max_input_tokens": 1024,
            "max_output_tokens": 1024,
            "source": "https://www.volcengine.com/docs/82379/1544106",
            "output_cost_per_token": _cny_per_m_to_usd_per_token(23),
            "output_cost_per_token_with_input_video": _cny_per_m_to_usd_per_token(14),
        },
        # Seedance 2.5 — 480P/720P + 1080P tiers (no 4k). Source
        # docs.volcengine.com/docs/82379/2191775 (Tokens 抵扣规则 table):
        #   480P/720P: 无视频输入 0.070 元/千 = 70 CNY/M; 含视频输入 0.042 = 42.
        #   1080P:     无视频输入 0.077 元/千 = 77 CNY/M; 含视频输入 0.046 = 46.
        "volcengine/doubao-seedance-2-5": {
            "litellm_provider": "volcengine",
            "mode": "video_generation",
            "max_input_tokens": 1024,
            "max_output_tokens": 1024,
            "source": "https://docs.volcengine.com/docs/82379/2191775",
            "output_cost_per_token": _cny_per_m_to_usd_per_token(70),
            "output_cost_per_token_with_input_video": _cny_per_m_to_usd_per_token(42),
            "output_cost_per_token_1080p": _cny_per_m_to_usd_per_token(77),
            "output_cost_per_token_1080p_with_input_video": _cny_per_m_to_usd_per_token(46),
            # 4K: ESTIMATED — the official 2.5 table has no 4K row. Scaled from
            # 2.5's 1080P by the 2.0 4K:1080P ratio (~0.51×): 无视频 77×26/51≈39,
            # 含视频 46×16/31≈24 CNY/M. Replace with the official rate once
            # Volcengine publishes a 2.5 4K tier.
            "output_cost_per_token_4k": _cny_per_m_to_usd_per_token(39),
            "output_cost_per_token_4k_with_input_video": _cny_per_m_to_usd_per_token(24),
        },
        "volcengine/doubao-seedance-2-5-260628": {
            "litellm_provider": "volcengine",
            "mode": "video_generation",
            "max_input_tokens": 1024,
            "max_output_tokens": 1024,
            "source": "https://docs.volcengine.com/docs/82379/2191775",
            "output_cost_per_token": _cny_per_m_to_usd_per_token(70),
            "output_cost_per_token_with_input_video": _cny_per_m_to_usd_per_token(42),
            "output_cost_per_token_1080p": _cny_per_m_to_usd_per_token(77),
            "output_cost_per_token_1080p_with_input_video": _cny_per_m_to_usd_per_token(46),
            # 4K: ESTIMATED — the official 2.5 table has no 4K row. Scaled from
            # 2.5's 1080P by the 2.0 4K:1080P ratio (~0.51×): 无视频 77×26/51≈39,
            # 含视频 46×16/31≈24 CNY/M. Replace with the official rate once
            # Volcengine publishes a 2.5 4K tier.
            "output_cost_per_token_4k": _cny_per_m_to_usd_per_token(39),
            "output_cost_per_token_4k_with_input_video": _cny_per_m_to_usd_per_token(24),
        },
        # ── Seedream image generation ────────────────────────────────────
        # Billed PER IMAGE in CNY (元/张), not per token — a different shape
        # from every other volcengine SKU here, hence
        # _cny_per_image_to_usd_per_image rather than the per-token helper.
        # Same 7.0 policy FX, but EXACT division with no rounding: these
        # values are reconciled field-by-field against the internal LiteLLM
        # fork's own table, which stores the unrounded quotient and is the
        # side that actually bills.
        #
        # Source: the 图片生成模型 table on
        # volcengine.com/docs/82379/1544106?lang=zh (read 2026-09-17), with
        # key NAMES taken from GhishaDev/litellm-internal because the meaning
        # of each key is defined by the gateway code that reads it
        # (litellm/llms/volcengine/image_generation/cost_calculator.py).
        #
        # ⚠️ output_cost_per_image IS THE FALLBACK, NOT THE HEADLINE PRICE.
        # The gateway reads it only when no banded key matches. For the
        # single-price SKUs (4-0, 4-5, 5-0, 5-0-lite) that makes it the one
        # and only price; for 5-0-pro the gateway's own table puts the
        # ≤1.5K band there. An earlier version of this file put the >1.5K
        # band in it under a locally-invented name — the gateway saw one
        # unrecognised flat override plus three keys it had never heard of,
        # took the branch that discards its own band table, and billed
        # 1024x1024 at 2x and ≤1.5K layer decomposition at 4x. Key names here
        # are not cosmetic; they are the contract.
        #
        # ⚠️ input_cost_per_image (5-0-pro only) is the MARGINAL rate:
        # Volcengine gives the first reference image free and charges ¥0.02
        # from the 2nd. The schema has no volume axis, so a single-image
        # request is over-billed by ¥0.02 (~$0.003). The other SKUs do not
        # bill reference images at all and deliberately carry NO
        # input_cost_per_image key — a 0.0 would be pushed to the gateway as
        # a deployment-level override of a field it does not define.
        #
        # ⚠️ doubao-seedream-5-0 is priced identically to 5-0-lite. That is
        # the gateway's definition, not an oversight: 5-0 is an alias of the
        # lite family, and a request to -lite-260128 echoes back 5-0-260128.
        #
        # CNY source values: 5-0-pro 0.60 / 0.30 / 0.30 / 0.15 output and
        # 0.02 input; 5-0 + 5-0-lite 0.22; 4-5 0.25; 4-0 0.20.
        "volcengine/doubao-seedream-5-0-pro-260628": _SEEDREAM_PRO,
        "volcengine/doubao-seedream-5-0-pro": _SEEDREAM_PRO,
        "volcengine/doubao-seedream-5-0-lite-260128": _SEEDREAM_FLAT_022,
        "volcengine/doubao-seedream-5-0-lite": _SEEDREAM_FLAT_022,
        "volcengine/doubao-seedream-5-0-260128": _SEEDREAM_FLAT_022,
        "volcengine/doubao-seedream-5-0": _SEEDREAM_FLAT_022,
        "volcengine/doubao-seedream-4-5-251128": _SEEDREAM_FLAT_025,
        "volcengine/doubao-seedream-4-5": _SEEDREAM_FLAT_025,
        "volcengine/doubao-seedream-4-0-250828": _SEEDREAM_FLAT_020,
        "volcengine/doubao-seedream-4-0-20260415": _SEEDREAM_FLAT_020,
        "volcengine/doubao-seedream-4-0": _SEEDREAM_FLAT_020,
    }

    # ── BytePlus ModelArk (ByteDance Ark overseas — Dreamina Seedance) ────
    # Reverse-whitelist for byteplus/* video SKUs. BytePlus is the overseas
    # sibling of Volcengine: same underlying Ark platform, same model
    # generations, same YYMMDD version stamps — but a different brand
    # (Dreamina, not Doubao) and, crucially, a different tariff quoted in
    # USD natively. These are NOT the domestic volcengine/* prices run
    # through an FX rate; BytePlus list prices sit ~6-8% above the
    # CNY-derived domestic equivalents. Independent SKUs, no mirroring.
    #
    # Both the dated official ID and the date-less alias are whitelisted,
    # matching the VOLCENGINE_ALLOWED_KEYS convention so deployments can
    # address either form. Caveat: neither BytePlus's Model list
    # (docs.byteplus.com/en/docs/ModelArk/1330310) nor Volcengine's
    # domestic equivalent publishes the date-less aliases — they are a
    # catalogue convention of this project, not vendor-registered IDs.
    BYTEPLUS_ALLOWED_KEYS = frozenset({
        # Dated official IDs
        "byteplus/dreamina-seedance-2-5-260628",
        "byteplus/dreamina-seedance-2-0-260128",
        "byteplus/dreamina-seedance-2-0-fast-260128",
        "byteplus/dreamina-seedance-2-0-mini-260615",
        # Date-less aliases
        "byteplus/dreamina-seedance-2-5",
        "byteplus/dreamina-seedance-2-0",
        "byteplus/dreamina-seedance-2-0-fast",
        "byteplus/dreamina-seedance-2-0-mini",
    })

    # BytePlus Dreamina Seedance pre-stage. Upstream BerriAI/litellm/main
    # carries no Seedance entries at all (verified 2026-08-21: zero keys
    # matching /seedance/i), so these 8 SKUs are injected wholesale — same
    # mechanic as VOLCENGINE_SYNTH_DATA. When upstream eventually publishes
    # them the overlay merges on top with no shape change.
    #
    # Currency: USD/token, converted from the vendor's own USD/M figures by
    # _usd_per_m_to_usd_per_token. No FX step — do NOT route these through
    # _cny_per_m_to_usd_per_token.
    #
    # Source: docs.byteplus.com/en/docs/ModelArk/1544106 (online inference;
    # offline/flex inference is "Not supported yet" for the whole family).
    # Snapshot 2026-08-21. LIST prices, USD/M tokens:
    #
    #   SKU                   480p/720p      1080p         4K
    #   2.5                   10.70 / 6.40   11.70 / 7.00  -
    #   2.0                    7.00 / 4.30    7.70 / 4.70  4.00 / 2.40
    #   2.0 fast               5.60 / 3.30    -            -
    #   2.0 mini               3.50 / 2.10    -            -
    #   (left = without video input, right = with video input)
    #
    # Deliberately LIST price, not the currently-discounted price. BytePlus
    # runs limited-time campaigns (docs.byteplus.com/en/docs/ModelArk/2630943)
    # where "N% of the list price" means pay N%: 2.5 1080p at 72% until
    # 2026-09-17, 2.0 fast at 75% and 2.0 mini at 40% until 2026-09-07. Those
    # discounts are conditional — pay-as-you-go only, prepaid resource packs
    # excluded, and they require an account balance or AI Savings Plan at the
    # USD 30 tier — so they are not a universal price. Storing list never
    # under-bills and needs no revert when a campaign lapses. (Contrast
    # ANTHROPIC_SYNTH_DATA, which does carry effective introductory prices —
    # that discount is unconditional and applies to every customer.)
    BYTEPLUS_SYNTH_DATA: dict[str, dict[str, Any]] = {
        # Dreamina Seedance 2.5 — 480p/720p + 1080p (no 4K tier officially
        # priced, consistent with the domestic 2.5 table).
        "byteplus/dreamina-seedance-2-5-260628": {
            "litellm_provider": "byteplus",
            "mode": "video_generation",
            "max_input_tokens": 1024,
            "max_output_tokens": 1024,
            "source": "https://docs.byteplus.com/en/docs/ModelArk/1544106",
            "output_cost_per_token": _usd_per_m_to_usd_per_token(10.70),
            "output_cost_per_token_with_input_video": _usd_per_m_to_usd_per_token(6.40),
            "output_cost_per_token_1080p": _usd_per_m_to_usd_per_token(11.70),
            "output_cost_per_token_1080p_with_input_video": _usd_per_m_to_usd_per_token(7.00),
            # 4K: ESTIMATED — the official BytePlus 2.5 table has no 4K row
            # (neither does the domestic one). Same derivation as the domestic
            # estimate in VOLCENGINE_SYNTH_DATA: scale 2.5's 1080P by the 2.0
            # 4K:1080P ratio, computed entirely inside the overseas USD price
            # set so no FX or cross-catalogue mixing enters.
            #   no video:   11.70 x (4.00 / 7.70) = 6.078 -> 6.08
            #   with video:  7.00 x (2.40 / 4.70) = 3.574 -> 3.57
            # Sanity check: the overseas/domestic premium on every officially
            # priced 2.5 tier sits in 1.064-1.070; these estimates imply 1.091
            # and 1.041, the spread coming from the domestic 4K estimate being
            # rounded to whole CNY (39 / 24). Replace with the official rate
            # once BytePlus publishes a 2.5 4K tier.
            "output_cost_per_token_4k": _usd_per_m_to_usd_per_token(6.08),
            "output_cost_per_token_4k_with_input_video": _usd_per_m_to_usd_per_token(3.57),
        },
        "byteplus/dreamina-seedance-2-5": {
            "litellm_provider": "byteplus",
            "mode": "video_generation",
            "max_input_tokens": 1024,
            "max_output_tokens": 1024,
            "source": "https://docs.byteplus.com/en/docs/ModelArk/1544106",
            "output_cost_per_token": _usd_per_m_to_usd_per_token(10.70),
            "output_cost_per_token_with_input_video": _usd_per_m_to_usd_per_token(6.40),
            "output_cost_per_token_1080p": _usd_per_m_to_usd_per_token(11.70),
            "output_cost_per_token_1080p_with_input_video": _usd_per_m_to_usd_per_token(7.00),
            # 4K: ESTIMATED — the official BytePlus 2.5 table has no 4K row
            # (neither does the domestic one). Same derivation as the domestic
            # estimate in VOLCENGINE_SYNTH_DATA: scale 2.5's 1080P by the 2.0
            # 4K:1080P ratio, computed entirely inside the overseas USD price
            # set so no FX or cross-catalogue mixing enters.
            #   no video:   11.70 x (4.00 / 7.70) = 6.078 -> 6.08
            #   with video:  7.00 x (2.40 / 4.70) = 3.574 -> 3.57
            # Sanity check: the overseas/domestic premium on every officially
            # priced 2.5 tier sits in 1.064-1.070; these estimates imply 1.091
            # and 1.041, the spread coming from the domestic 4K estimate being
            # rounded to whole CNY (39 / 24). Replace with the official rate
            # once BytePlus publishes a 2.5 4K tier.
            "output_cost_per_token_4k": _usd_per_m_to_usd_per_token(6.08),
            "output_cost_per_token_4k_with_input_video": _usd_per_m_to_usd_per_token(3.57),
        },
        # Dreamina Seedance 2.0 (standard) — all three resolution tiers,
        # 4K officially priced (unlike 2.5).
        "byteplus/dreamina-seedance-2-0-260128": {
            "litellm_provider": "byteplus",
            "mode": "video_generation",
            "max_input_tokens": 1024,
            "max_output_tokens": 1024,
            "source": "https://docs.byteplus.com/en/docs/ModelArk/1544106",
            "output_cost_per_token": _usd_per_m_to_usd_per_token(7.00),
            "output_cost_per_token_with_input_video": _usd_per_m_to_usd_per_token(4.30),
            "output_cost_per_token_1080p": _usd_per_m_to_usd_per_token(7.70),
            "output_cost_per_token_1080p_with_input_video": _usd_per_m_to_usd_per_token(4.70),
            "output_cost_per_token_4k": _usd_per_m_to_usd_per_token(4.00),
            "output_cost_per_token_4k_with_input_video": _usd_per_m_to_usd_per_token(2.40),
        },
        "byteplus/dreamina-seedance-2-0": {
            "litellm_provider": "byteplus",
            "mode": "video_generation",
            "max_input_tokens": 1024,
            "max_output_tokens": 1024,
            "source": "https://docs.byteplus.com/en/docs/ModelArk/1544106",
            "output_cost_per_token": _usd_per_m_to_usd_per_token(7.00),
            "output_cost_per_token_with_input_video": _usd_per_m_to_usd_per_token(4.30),
            "output_cost_per_token_1080p": _usd_per_m_to_usd_per_token(7.70),
            "output_cost_per_token_1080p_with_input_video": _usd_per_m_to_usd_per_token(4.70),
            "output_cost_per_token_4k": _usd_per_m_to_usd_per_token(4.00),
            "output_cost_per_token_4k_with_input_video": _usd_per_m_to_usd_per_token(2.40),
        },
        # Dreamina Seedance 2.0 Fast — 480p/720p only.
        "byteplus/dreamina-seedance-2-0-fast-260128": {
            "litellm_provider": "byteplus",
            "mode": "video_generation",
            "max_input_tokens": 1024,
            "max_output_tokens": 1024,
            "source": "https://docs.byteplus.com/en/docs/ModelArk/1544106",
            "output_cost_per_token": _usd_per_m_to_usd_per_token(5.60),
            "output_cost_per_token_with_input_video": _usd_per_m_to_usd_per_token(3.30),
        },
        "byteplus/dreamina-seedance-2-0-fast": {
            "litellm_provider": "byteplus",
            "mode": "video_generation",
            "max_input_tokens": 1024,
            "max_output_tokens": 1024,
            "source": "https://docs.byteplus.com/en/docs/ModelArk/1544106",
            "output_cost_per_token": _usd_per_m_to_usd_per_token(5.60),
            "output_cost_per_token_with_input_video": _usd_per_m_to_usd_per_token(3.30),
        },
        # Dreamina Seedance 2.0 Mini — 480p/720p only.
        "byteplus/dreamina-seedance-2-0-mini-260615": {
            "litellm_provider": "byteplus",
            "mode": "video_generation",
            "max_input_tokens": 1024,
            "max_output_tokens": 1024,
            "source": "https://docs.byteplus.com/en/docs/ModelArk/1544106",
            "output_cost_per_token": _usd_per_m_to_usd_per_token(3.50),
            "output_cost_per_token_with_input_video": _usd_per_m_to_usd_per_token(2.10),
        },
        "byteplus/dreamina-seedance-2-0-mini": {
            "litellm_provider": "byteplus",
            "mode": "video_generation",
            "max_input_tokens": 1024,
            "max_output_tokens": 1024,
            "source": "https://docs.byteplus.com/en/docs/ModelArk/1544106",
            "output_cost_per_token": _usd_per_m_to_usd_per_token(3.50),
            "output_cost_per_token_with_input_video": _usd_per_m_to_usd_per_token(2.10),
        },
    }

    # ── new-api (aggregator gateway) ──────────────────────────────────────
    # new-api is a routing-layer aggregator: it exposes third-party models
    # under a unified surface. As a *provider* here it acts as a mirror
    # library — every new-api/<sku> entry is a duplicate of some already-
    # populated <vendor>/<sku> record, kept on a separate provider namespace
    # so downstream consumers can pick the gateway they call.
    #
    # Prices, context windows, capabilities, and modes are all copied at
    # synth time via apply_newapi_synth (which runs *after* every other
    # vendor synth), so the mirrored SKUs stay in lock-step with their
    # authoritative source without duplicated tariff bookkeeping.
    #
    # Extending: add both a new-api/<sku> whitelist entry AND a matching
    # NEWAPI_MIRROR_SOURCES row pointing at the source key.
    NEWAPI_ALLOWED_KEYS = frozenset({
        # Seedance video (mirrors volcengine/doubao-seedance-*)
        "new-api/doubao-seedance-2-0",
        "new-api/doubao-seedance-2-0-fast",
        "new-api/doubao-seedance-2-0-mini",
        "new-api/doubao-seedance-2-0-260128",
        "new-api/doubao-seedance-2-0-fast-260128",
        "new-api/doubao-seedance-2-0-mini-260615",
        "new-api/doubao-seedance-2-5",
        "new-api/doubao-seedance-2-5-260628",
    })

    # Map new-api/<sku> → authoritative source key (after all other synths run).
    # Every whitelisted new-api key MUST appear here; unmapped keys drop out.
    NEWAPI_MIRROR_SOURCES: dict[str, str] = {
        "new-api/doubao-seedance-2-0":              "volcengine/doubao-seedance-2-0",
        "new-api/doubao-seedance-2-0-fast":         "volcengine/doubao-seedance-2-0-fast",
        "new-api/doubao-seedance-2-0-mini":         "volcengine/doubao-seedance-2-0-mini",
        "new-api/doubao-seedance-2-0-260128":       "volcengine/doubao-seedance-2-0-260128",
        "new-api/doubao-seedance-2-0-fast-260128":  "volcengine/doubao-seedance-2-0-fast-260128",
        "new-api/doubao-seedance-2-0-mini-260615":  "volcengine/doubao-seedance-2-0-mini-260615",
        "new-api/doubao-seedance-2-5":              "volcengine/doubao-seedance-2-5",
        "new-api/doubao-seedance-2-5-260628":       "volcengine/doubao-seedance-2-5-260628",
    }

    # ── ecloud_aicc (aggregator gateway) ──────────────────────────────────
    # Same mirror-provider model as new-api: each ecloud_aicc/<sku> record
    # is a full copy of an authoritative <vendor>/<sku> with only
    # litellm_provider re-labelled. See apply_ecloud_aicc_synth for the
    # mechanic; NEWAPI's docstring above covers the shared rationale.
    #
    # Extending: append a whitelist entry AND a matching
    # ECLOUD_AICC_MIRROR_SOURCES row pointing at the source key.
    ECLOUD_AICC_ALLOWED_KEYS = frozenset({
        # Seedance video (mirrors volcengine/doubao-seedance-*)
        "ecloud_aicc/doubao-seedance-2-0",
        "ecloud_aicc/doubao-seedance-2-0-fast",
        "ecloud_aicc/doubao-seedance-2-0-mini",
        "ecloud_aicc/doubao-seedance-2-0-260128",
        "ecloud_aicc/doubao-seedance-2-0-fast-260128",
        "ecloud_aicc/doubao-seedance-2-0-mini-260615",
        "ecloud_aicc/doubao-seedance-2-5",
        "ecloud_aicc/doubao-seedance-2-5-260628",
    })

    # Map ecloud_aicc/<sku> → authoritative source key.
    ECLOUD_AICC_MIRROR_SOURCES: dict[str, str] = {
        "ecloud_aicc/doubao-seedance-2-0":              "volcengine/doubao-seedance-2-0",
        "ecloud_aicc/doubao-seedance-2-0-fast":         "volcengine/doubao-seedance-2-0-fast",
        "ecloud_aicc/doubao-seedance-2-0-mini":         "volcengine/doubao-seedance-2-0-mini",
        "ecloud_aicc/doubao-seedance-2-0-260128":       "volcengine/doubao-seedance-2-0-260128",
        "ecloud_aicc/doubao-seedance-2-0-fast-260128":  "volcengine/doubao-seedance-2-0-fast-260128",
        "ecloud_aicc/doubao-seedance-2-0-mini-260615":  "volcengine/doubao-seedance-2-0-mini-260615",
        "ecloud_aicc/doubao-seedance-2-5":              "volcengine/doubao-seedance-2-5",
        "ecloud_aicc/doubao-seedance-2-5-260628":       "volcengine/doubao-seedance-2-5-260628",
    }

    # DEEPSEEK_SYNTH_DATA / apply_deepseek_synth RETIRED 2026-09-04.
    #
    # The overlay existed because upstream trailed the 2026-08 V4 tariff and
    # pinned max_output_tokens at 8192. Both gaps are closed: upstream now
    # carries every field of api-docs.deepseek.com/quick_start/pricing
    # verbatim (re-read live 2026-09-04), so the overlay was not merely
    # redundant — it was WRONG in two directions:
    #
    #   1. Under-billing. The official page is now denominated in USD, not
    #      CNY. Our CNY→USD derivation at the 7.0 policy rate produced
    #      $0.4286/M input where DeepSeek publishes $0.44 — DeepSeek's own
    #      implied rate is 6.818, not 7.0. Every V4 input/output token was
    #      billed ~2.7% light. Read the vendor's published USD value; do not
    #      derive it from a CNY figure through our FX policy.
    #   2. Wrong context. The overlay pinned max_output_tokens=384000, a
    #      decimal reading of the page's "384K". Upstream has 393216
    #      (384 x 1024), which is what the API actually accepts.
    #
    # This is the third overlay to rot this way (see the gpt-5.6 flex and
    # claude-sonnet-5 introductory entries). Delete overlays once upstream
    # catches up.
    #
    # Peak vs off-peak still holds and still needs no overlay: DeepSeek
    # halves every rate outside 01:00-04:00 / 06:00-10:00 UTC Mon-Fri, and
    # upstream carries the PEAK tariff — the ceiling, so we never under-bill.
    # Off-peak is exactly 0.5x if a time-of-day axis is ever added.

    # ── Anthropic overlays ────────────────────────────────────────────────
    # Two entry kinds may live here (see apply_anthropic_synth): a partial
    # overlay patching an upstream entry, or a complete pre-staged record
    # (carries `litellm_provider`) for a model not yet on BerriAI upstream.
    #
    # Retired, because upstream caught up (the rule for every overlay here):
    #
    #   claude-sonnet-5 introductory price — retired 2026-09-01. Anthropic made
    #     the $2 / $10 rate permanent and upstream carries it verbatim.
    #   claude-opus-5, claude-mythos-5, claude-mythos-5-1 — retired 2026-09-30.
    #     Pre-staged while absent upstream; upstream now carries all three and
    #     matched every one of their 25-26 fields exactly, prices and
    #     capability flags alike (checked against BerriAI/litellm@d098b02).
    #     Keeping them would have pinned those capability flags at their
    #     2026-06/09 state — the silent drift capability_check.py now blocks.
    #
    # Anthropic prices still worth knowing, all flowing from upstream: Mythos
    # 5.1 and Fable 5.1 cache-read at 0.025x base input ($0.25), Opus 5.5 at
    # 0.05x ($0.20), everything else 0.1x — per the pricing-page footnote.
    ANTHROPIC_SYNTH_DATA: dict[str, dict[str, Any]] = {
        # Upstream regressed Sonnet 4.5 to a 1M context (2026-09, likely from
        # the retired context-1m beta). platform.claude.com/docs/en/
        # build-with-claude/context-windows (2026-09-30): "Other Claude models,
        # including Claude Sonnet 4.5, have a 200k-token context window."
        "claude-sonnet-4-5": {"max_input_tokens": 200000},
        "claude-sonnet-4-5-20250929": {"max_input_tokens": 200000},
    }

    # Google / Gemini overlays. Two kinds, same as the other providers:
    # complete pre-staged records for models newly on ai.google.dev but not
    # yet upstream (injected wholesale), and partial overlays patching a
    # field upstream gets wrong. Prices from ai.google.dev/gemini-api/docs/
    # pricing.
    #
    # RETIRED 2026-09-14 after a full audit of all 20 gemini/* entries
    # against the official pricing page:
    #
    #   gemini/gemini-3.6-flash — DELETED. It pinned $1.50 in / $7.50 out /
    #     $0.15 cache, DOUBLE the real rate, and had been OVER-billing ever
    #     since upstream picked the model up. The page reads "$0.75 through
    #     December 31, 2026. $1.50 starting January 1, 2027" — the overlay
    #     captured the second sentence. Upstream carries $0.75 / $3.75 /
    #     $0.075, matching 3.7-flash and 3.8-flash, which share the same
    #     time-boxed tariff. (It also had max_output_tokens 65535 for
    #     upstream's 65536.)
    #
    #   gemini/gemini-3.5-flash-lite — DELETED. Byte-identical to upstream
    #     on every field; pure redundancy.
    #
    # ⚠️ WHEN A VENDOR PUBLISHES A DATED PRICE CHANGE, STORE THE RATE IN
    # EFFECT TODAY AND SCHEDULE A RE-CHECK — never pre-load the future one.
    # An overlay cannot know what day it is, so a future price written today
    # is simply a wrong price until the switchover. gemini-3.7-flash and
    # gemini-3.8-flash carry the same 2027-01-01 increase and deliberately
    # have no overlay at all: upstream already tracks the effective rate.
    #
    #   gemini/gemini-3.1-flash-lite-image — overlay retired 2026-09-30. It
    #     had shrunk to one flag, supports_function_calling=False, because
    #     upstream said True against the model page's "Not supported".
    #     Upstream has since corrected it to False, so the override became
    #     redundant and was removed.
    GOOGLE_SYNTH_DATA: dict[str, dict[str, Any]] = {
        # Both flags are wrong upstream AND were wrong in the export before —
        # identical on both sides, so the drift report could not see them.
        # Found by re-reading the capability table, not by diffing.
        "gemini/gemini-2.5-flash-image": {
            "supports_prompt_caching": False,  # "Caching: Not supported"
            "supports_pdf_input": False,  # "Inputs: Image and Text"
        },
        # The model page documents "Thinking: Supported (minimal and high)";
        # upstream leaves the minimal flag undefined, so LiteLLM would reject
        # reasoning_effort="minimal" for a model that accepts it. Allowlisted.
        "gemini/gemini-3.1-flash-lite-image": {
            "supports_minimal_reasoning_effort": True,
        },
    }

    # ── OpenAI overlays ───────────────────────────────────────────────────
    # Source: developers.openai.com/api/docs/pricing and the per-model pages.
    # Merged on top of upstream via {**existing, **synth}. Every entry below
    # is a field upstream lacks or gets wrong; anything upstream already
    # carries identically has been removed, because a redundant overlay pins
    # stale state the moment the vendor moves (v1.16.18, v1.16.20).
    #
    # Retired 2026-09-30, upstream having caught up exactly:
    #   • gpt-5.4-mini / gpt-5.4-nano short-context max_input and batch
    #     cached-read, gpt-5.5 priority tier, gpt-4o-mini-tts $0.60 text input.
    #   • cache_read_input_image_token_cost on gpt-image-1 / -1-mini / -1.5 /
    #     -2 and on the 2.5 pair. This field started life here as a
    #     PROJECT-INVENTED key (v1.16.28: every OpenAI image SKU publishes a
    #     separate, higher cached-IMAGE rate that cache_read_input_token_cost
    #     cannot hold). Upstream has since adopted the same key with the same
    #     values, so it now flows from there — and is far more likely to be
    #     read by the gateway's billing code than a local-only field was.
    #   • supports_service_tier on gpt-5 / 5-mini / 5.1 / 5.2 / 5.4 /
    #     5.4-mini / 5.4-nano / 5.5. Upstream never set it, no code in the
    #     LiteLLM fork reads it (schema-only), and it was never
    #     vendor-verified per model — a forwarded flag with no effect and no
    #     source. Removed rather than allowlisted.
    OPENAI_SYNTH_DATA: dict[str, dict[str, Any]] = {
        # Data-residency uplift (10%) — absent upstream for these three.
        "gpt-5": {
            "regional_processing_uplift_multiplier_eu": 1.1,
            "regional_processing_uplift_multiplier_us": 1.1,
        },
        "gpt-5-mini": {
            "regional_processing_uplift_multiplier_eu": 1.1,
            "regional_processing_uplift_multiplier_us": 1.1,
        },
        "gpt-5-nano": {
            "regional_processing_uplift_multiplier_eu": 1.1,
            "regional_processing_uplift_multiplier_us": 1.1,
        },
        # ── Context window ───────────────────────────────────────────────
        # OpenAI publishes BOTH numbers on each model page, and both are
        # correct for different questions:
        #     1,050,000 context window
        #     Maximum input tokens: 922,000   (= 1,050,000 - 128,000 output)
        # Upstream stores 922,000. This catalogue stores the CONTEXT WINDOW in
        # max_input_tokens, which is how the field is used for every other
        # provider here (Claude 1M, Gemini 1,048,576, DeepSeek 1,000,000). The
        # nine entries below keep the family internally consistent. Worth
        # revisiting deliberately some day — as one decision across all nine.
        #
        # Prices for all nine come from upstream unchanged; each was checked
        # against the pricing page when added (short context and >272k, incl.
        # flex / priority / batch). The *_above_272k_tokens_flex overlays that
        # once lived on the gpt-5.6 family were removed on 2026-08-26: kept,
        # they would have billed flex long-context output at $22.50/M against
        # a real $15/M after OpenAI cut the 5.6 Sol tariff.
        "gpt-6-astra": {"max_input_tokens": 1050000},
        "gpt-6.1-sol": {"max_input_tokens": 1050000},  # supersedes gpt-6-sol; cached input halved ($0.10)
        "gpt-6-sol": {"max_input_tokens": 1050000},
        "gpt-6-luna": {"max_input_tokens": 1050000},
        "gpt-5.6": {"max_input_tokens": 1050000},
        "gpt-5.6-sol": {"max_input_tokens": 1050000},
        "gpt-5.6-terra": {"max_input_tokens": 1050000},
        "gpt-5.6-luna": {"max_input_tokens": 1050000},
        # Standalone TTS — billed per CHARACTER, a field upstream lacks.
        # Source openai.com: tts-1 $15 / 1M characters, tts-1-hd $30.
        "tts-1": {
            "output_cost_per_character": 1.5e-05,
            "supported_modalities": ["text"],
            "supported_output_modalities": ["audio"],
        },
        "tts-1-hd": {
            "output_cost_per_character": 3e-05,
            "supported_modalities": ["text"],
            "supported_output_modalities": ["audio"],
        },
        # GPT Image 2.5 — there is NO bare `gpt-image-2.5`; OpenAI ships the
        # generation as two named variants (sunburst: editing precision;
        # flare: speed). Identical tariff, which the model pages state
        # outright: "Token rates match GPT Image 2." Upstream now carries both
        # with every price; only the modality metadata it lacks is added.
        "gpt-image-2.5-sunburst": {
            "supported_modalities": ["text", "image"],
            "supported_output_modalities": ["image"],
            "supports_pdf_input": False,  # CAPABILITY_OVERRIDES: "text, image" only
        },
        "gpt-image-2.5-flare": {
            "supported_modalities": ["text", "image"],
            "supported_output_modalities": ["image"],
            "supports_pdf_input": False,  # CAPABILITY_OVERRIDES: "text, image" only
        },
        # Upstream marks these two PDF-capable; their model pages say "Input
        # modalities: text, image". See _SRC_GPT_IMAGE_NO_PDF.
        "gpt-image-2": {"supports_pdf_input": False},
        "gpt-image-1.5": {"supports_pdf_input": False},
    }

    # Supported model modes
    SUPPORTED_MODES = [
        "chat",
        "embedding",
        "image_generation",
        "video_generation",
        "audio_speech",
        "audio_transcription",
        "responses",
        # LiteLLM re-classified the /v1/realtime SKUs from mode "chat" to a
        # dedicated "realtime" mode (observed 2026-08-21). Without this entry
        # the curated realtime allow-list (gpt-realtime,
        # gpt-4o-realtime-preview-2024-12-17 — see INCLUDE_PATTERNS) silently
        # drops out of the export as unsupported_mode.
        "realtime",
    ]

    # Mode to model type mapping
    MODE_MAPPING = {
        "chat": "language",
        "completion": "language",
        "embedding": "embedding",
        "image_generation": "image",
        "video_generation": "video",
        "audio_transcription": "audio",
        "audio_speech": "audio",
        # OpenAI's /v1/responses endpoint (codex family, gpt-*-pro, deep-research)
        # is still an LLM interaction. Downstream schema treats it as language.
        "responses": "language",
        # /v1/realtime is a bidirectional speech+text session — an LLM
        # interaction, same reasoning as "responses" above. Mapping to
        # "language" also preserves the downstream contract: these SKUs
        # exported as type "language" while upstream still called them "chat".
        "realtime": "language",
    }

    # Provider-specific exclusion rules
    PROVIDER_EXCLUSION_RULES: dict[str, dict[str, Any]] = {
        "openai": {
            # Exclude legacy GPT-4 (gpt-4, gpt-4-turbo, gpt-4-32k, gpt-4-YYYY-MM-DD)
            # but *keep* the GPT-4o family (gpt-4o, gpt-4o-mini, gpt-4o-realtime-*,
            # gpt-4o-mini-transcribe, gpt-4o-mini-tts, etc.) — filtered per-SKU
            # via INCLUDE_PATTERNS + global excludes.
            # Exclude o1 series (keep o3, o4 series).
            # Exclude gpt-*-chat without -latest suffix (keep gpt-*-chat-latest).
            # Exclude ada embedding models (keep text-embedding-*-large/small only).
            # Exclude search-api models.
            # Image: keep gpt-image-* only; exclude dall-e-* and chatgpt-image-*.
            "patterns": [
                # Exclude legacy GPT-4 (gpt-4, gpt-4-turbo, gpt-4-32k,
                # gpt-4-YYYY-MM-DD) — but keep the "4o" family (gpt-4o, gpt-4o-*)
                # AND the "4.x" lineage (gpt-4.1{,-mini,-nano}). Both are filtered
                # downstream via INCLUDE_PATTERNS + global excludes / date_pattern.
                re.compile(r"^gpt-4(?:$|-turbo|-32k|-\d)", re.IGNORECASE),
                re.compile(r"^o1", re.IGNORECASE),
                re.compile(r"^gpt-.*-chat$", re.IGNORECASE),
                re.compile(r"^text-embedding-ada", re.IGNORECASE),
                re.compile(r"-search-api$", re.IGNORECASE),
                re.compile(r"^dall-e", re.IGNORECASE),
                re.compile(r"^chatgpt-image", re.IGNORECASE),
            ],
            "custom_check": None,
            "description": "Exclude legacy gpt-4 (not 4o family), o1, gpt-*-chat w/o -latest, ada, search-api, dall-e, chatgpt-image",
        },
        "anthropic": {
            # Only allow models starting with 'claude-'
            # Exclude Claude 4.1 versions
            "patterns": [re.compile(r"claude-\w+-4-1$", re.IGNORECASE)],
            "custom_check": lambda key: not key.startswith("claude-"),
            "description": "Only allow claude-* prefix, exclude regional variants and Claude 4.1",
        },
        "google": {
            # Exclude gemini versions below 2.5 (keep 2.5, 3.x, and above)
            # Image: exclude imagen-* and experimental flash-exp-image models
            "patterns": [
                re.compile(r"^gemini/gemini-1\.", re.IGNORECASE),
                re.compile(r"^gemini/gemini-2\.[0-4]", re.IGNORECASE),
                re.compile(r"^gemini/imagen", re.IGNORECASE),
                re.compile(r"flash-exp-image", re.IGNORECASE),
            ],
            "custom_check": None,
            "description": "Exclude gemini <2.5, imagen-*, flash-exp-image",
        },
        "gemini": {
            # Same as google - for when litellm_provider is 'gemini' instead of 'google'
            "patterns": [
                re.compile(r"^gemini/gemini-1\.", re.IGNORECASE),
                re.compile(r"^gemini/gemini-2\.[0-4]", re.IGNORECASE),
                re.compile(r"^gemini/imagen", re.IGNORECASE),
                re.compile(r"flash-exp-image", re.IGNORECASE),
            ],
            "custom_check": None,
            "description": "Exclude gemini <2.5, imagen-*, flash-exp-image",
        },
        "zai": {
            # Reverse-whitelist: only ZAI_ALLOWED_KEYS pass through.
            "patterns": [],
            "custom_check": lambda key: key.lower() not in ModelSyncRules.ZAI_ALLOWED_KEYS,
            "description": "Allow only whitelisted zai/glm-* keys (see ZAI_ALLOWED_KEYS)",
        },
        "bigmodel": {
            # Reverse-whitelist: only BIGMODEL_ALLOWED_KEYS pass through.
            "patterns": [],
            "custom_check": lambda key: key.lower() not in ModelSyncRules.BIGMODEL_ALLOWED_KEYS,
            "description": "Allow only whitelisted bigmodel/glm-* keys (see BIGMODEL_ALLOWED_KEYS)",
        },
        "deepseek": {
            # Reverse-whitelist: only DEEPSEEK_ALLOWED_KEYS pass through.
            "patterns": [],
            "custom_check": lambda key: key.lower() not in ModelSyncRules.DEEPSEEK_ALLOWED_KEYS,
            "description": "Allow only whitelisted deepseek/* keys (see DEEPSEEK_ALLOWED_KEYS)",
        },
        "moonshot": {
            # Reverse-whitelist: only MOONSHOT_ALLOWED_KEYS pass through.
            "patterns": [],
            "custom_check": lambda key: key.lower() not in ModelSyncRules.MOONSHOT_ALLOWED_KEYS,
            "description": "Allow only whitelisted moonshot/* keys (see MOONSHOT_ALLOWED_KEYS)",
        },
        "dashscope": {
            # Reverse-whitelist: only DASHSCOPE_ALLOWED_KEYS pass through.
            # Upstream carries 45 dashscope/* keys (qwen, plus third-party
            # models resold through Model Studio); everything outside the
            # whitelist stays filtered out.
            "patterns": [],
            "custom_check": lambda key: key.lower() not in ModelSyncRules.DASHSCOPE_ALLOWED_KEYS,
            "description": "Allow only whitelisted dashscope/* keys (see DASHSCOPE_ALLOWED_KEYS)",
        },
        "volcengine": {
            # Reverse-whitelist: only VOLCENGINE_ALLOWED_KEYS pass through.
            # Today this is Seedance 2.0 video models; chat/embedding SKUs
            # carried by upstream under the same provider stay filtered out.
            "patterns": [],
            "custom_check": lambda key: key.lower() not in ModelSyncRules.VOLCENGINE_ALLOWED_KEYS,
            "description": "Allow only whitelisted volcengine/doubao-seedance-* keys (see VOLCENGINE_ALLOWED_KEYS)",
        },
        "byteplus": {
            # Reverse-whitelist: only BYTEPLUS_ALLOWED_KEYS pass through.
            # Overseas (BytePlus ModelArk) Dreamina Seedance video SKUs;
            # any other byteplus/* key upstream may carry stays filtered out.
            "patterns": [],
            "custom_check": lambda key: key.lower() not in ModelSyncRules.BYTEPLUS_ALLOWED_KEYS,
            "description": "Allow only whitelisted byteplus/dreamina-seedance-* keys (see BYTEPLUS_ALLOWED_KEYS)",
        },
        "new-api": {
            # Reverse-whitelist: only NEWAPI_ALLOWED_KEYS pass through.
            # new-api mirrors third-party SKUs on a separate provider
            # namespace; see NEWAPI_MIRROR_SOURCES for the source mapping.
            "patterns": [],
            "custom_check": lambda key: key.lower() not in ModelSyncRules.NEWAPI_ALLOWED_KEYS,
            "description": "Allow only whitelisted new-api/* keys (see NEWAPI_ALLOWED_KEYS)",
        },
        "ecloud_aicc": {
            # Reverse-whitelist: only ECLOUD_AICC_ALLOWED_KEYS pass through.
            # Same mirror-provider mechanism as new-api; see
            # ECLOUD_AICC_MIRROR_SOURCES for the source mapping.
            "patterns": [],
            "custom_check": lambda key: key.lower() not in ModelSyncRules.ECLOUD_AICC_ALLOWED_KEYS,
            "description": "Allow only whitelisted ecloud_aicc/* keys (see ECLOUD_AICC_ALLOWED_KEYS)",
        },
    }

    # Global exclude patterns
    EXCLUDE_PATTERNS = [
        re.compile(r"^openai/"),  # Exclude models with openai/ prefix
        re.compile(r"^ft:"),  # Exclude fine-tuned models
        re.compile(r"-latest$"),  # Exclude models ending with -latest
        re.compile(r"/latest$"),  # Exclude models ending with /latest
        re.compile(r"-preview$"),  # Exclude models ending with -preview
        re.compile(r"-preview-"),  # Exclude models containing -preview-
        re.compile(r"^latest$"),  # Exclude models named exactly 'latest'
        re.compile(r"-old$"),  # Exclude old versions
        re.compile(r"-deprecated$"),  # Exclude deprecated models
        re.compile(r"-legacy$"),  # Exclude legacy models
        re.compile(r"^azure/.*"),  # Exclude Azure specific models
        re.compile(r"^sagemaker/.*"),  # Exclude Sagemaker models
        re.compile(r"^bedrock/.*"),  # Exclude Bedrock models
        re.compile(r"^palm/.*"),  # Exclude PaLM models (deprecated)
        re.compile(r"^gemini/gemini-.*-\d{3}$"),  # Exclude Gemini versioned models
        re.compile(r"^gpt-realtime", re.IGNORECASE),  # Exclude gpt-realtime-* models
        re.compile(r"^gpt-audio", re.IGNORECASE),  # Exclude gpt-audio-* models
        # Image generation size/quality variants (e.g. low/1024-x-1024/gpt-image-1.5)
        re.compile(r"^(low|medium|high|standard|hd|auto)/", re.IGNORECASE),
        re.compile(r"^\d+-x-\d+/", re.IGNORECASE),
    ]

    # Exclude specific model keys (exact match)
    EXCLUDE_MODEL_KEYS = [
        # OpenAI legacy/older models
        "gpt-3.5-turbo",
        "gpt-3.5-turbo-16k",
        "gpt-4",
        "gpt-4-32k",
        "gpt-4-turbo",
        # OpenAI audio-transcription scope WIDENED to full-fat ASR 2026-09-04.
        # gpt-4o-transcribe, gpt-transcribe and gpt-live-transcribe used to
        # sit here on a "mini SKU only" product scope, with a note saying to
        # promote them if the scope ever widened. It has — they are now in
        # the INCLUDE_PATTERNS allow-list alongside the realtime SKUs.
        #
        # gpt-4o-transcribe-diarize stays out: unlike the other three it is
        # absent from the pricing page's Transcription table, so there is no
        # authoritative rate to carry.
        "gpt-4o-transcribe-diarize",
        # SHUT DOWN by OpenAI — retired from the export 2026-09-14. Calls to
        # these fail; they are not merely superseded. Verified against
        # developers.openai.com/api/docs/deprecations, whose tables are
        # labelled "Shutdown date" and whose own definition is explicit: "At
        # the time of the shut down, the model or endpoint will no longer be
        # accessible."
        #
        #   key                   shutdown       replacement
        #   gpt-5-chat-latest     2026-07-23     gpt-5.6-sol
        #   gpt-5.1-chat-latest   2026-07-23     gpt-5.6-sol
        #   gpt-5.2-chat-latest   2026-08-10     gpt-5.6-sol
        #   gpt-5.3-chat-latest   2026-08-10     gpt-5.6-sol
        #
        # That is EVERY *-chat-latest SKU the catalogue carried. They reached
        # the export through the ^gpt-.*-chat-latest$ INCLUDE_PATTERN, which
        # admits the family wholesale and has no notion of lifecycle. The
        # pattern is kept so a future chat-latest is still picked up, which
        # also means it will be admitted with no decision made — check the
        # deprecations page when one appears.
        "gpt-5-chat-latest",
        "gpt-5.1-chat-latest",
        "gpt-5.2-chat-latest",
        "gpt-5.3-chat-latest",
        # OpenAI responses-mode variants outside the approved whitelist.
        # (gpt-5.3-codex is the sanctioned responses SKU; the wider codex /
        # pro / deep-research families are intentionally kept out — same
        # narrow-scope policy as audio.)
        "gpt-5-codex",
        "gpt-5-pro",
        "gpt-5.1-codex",
        "gpt-5.1-codex-max",
        "gpt-5.1-codex-mini",
        "gpt-5.2-codex",
        "gpt-5.2-pro",
        "gpt-5.4-pro",
        "gpt-5.5-pro",
        "o3-deep-research",
        "o3-pro",
        "o4-mini-deep-research",
        # Same policy, 2026-09 arrivals. Neither is on the official pricing
        # page and neither has a model page on developers.openai.com — they
        # entered the export on their own the first time upstream published
        # them, which is now the THIRD time this has happened (gpt-live-1 in
        # v1.16.30, these two here). OpenAI has no reverse-whitelist, so its
        # scope is enforced only by exclusion patterns that new keys can
        # simply fail to match.
        #
        #   gpt-5.5-cyber — superseded Daybreak cyber model. The pricing
        #     page's "Cyber models" table lists only gpt-5.6-sol and
        #     gpt-5.6-cyber, and the deprecations page already retires
        #     gpt-5.4-cyber (2026-10-01) in favour of gpt-5.6-cyber. Its
        #     upstream prices are identical to gpt-5.6-cyber's short-context
        #     tier, but it lacks the >272k tier that entry carries.
        #   gpt-rosalind-research — a research variant, same family as the
        #     *-deep-research keys already excluded above.
        #
        # Promote either one if it appears on the official pricing page.
        "gpt-5.5-cyber",
        "gpt-rosalind-research",
        # Note: gpt-audio-* and gpt-realtime-* are excluded via EXCLUDE_PATTERNS
        # Gemini non-standard models
        "gemini/gemini-gemma-2-27b-it",
        "gemini/gemini-gemma-2-9b-it",
        "gemini/gemini-pro",
        "gemini/gemini-pro-vision",
        # Gemini special-purpose models
        "gemini/gemini-3.1-pro-preview-customtools",
        "gemini/gemini-3.1-flash-live-preview",
        # SHUT DOWN by Google — retired from the export 2026-09-14. These are
        # not "old but usable"; calls to them fail. Verified against
        # ai.google.dev/gemini-api/docs/deprecations plus the models page,
        # which labels the first two "(Shut down)" and has dropped the last
        # two entirely. Every replacement is already in the catalogue, so
        # nothing is left uncovered.
        #
        #   key                             shutdown      replacement
        #   gemini-3-pro-preview            2026-03-09    gemini-3.1-pro-preview
        #   gemini-3.1-flash-lite-preview   2026-05-25    gemini-3.1-flash-lite
        #   gemini-3-pro-image-preview      2026-06-25    gemini-3-pro-image
        #   gemini-3.1-flash-image-preview  2026-06-25    gemini-3.1-flash-image
        #
        # They reached the export through the ^gemini/gemini-[3-9].*-preview$
        # INCLUDE_PATTERN, which admits 3.x previews wholesale and has no
        # notion of lifecycle. Nothing in the pipeline reads a shutdown date,
        # so a retired model stays in the catalogue until someone checks the
        # deprecations page by hand. That is the actual gap here.
        "gemini/gemini-3-pro-preview",
        "gemini/gemini-3.1-flash-lite-preview",
        "gemini/gemini-3-pro-image-preview",
        "gemini/gemini-3.1-flash-image-preview",
        # Same policy, 2026-08 arrivals: non-conversational Gemini modalities.
        # The Google scope is Gemini 2.5+ chat (Flash / Flash-Lite / Pro),
        # Gemini Embedding, and the gemini-*-image* series — audio is not in
        # it. These two reach the filter only because the
        # ^gemini/gemini-[3-9].*-preview$ INCLUDE_PATTERN (written to admit
        # 3.x *chat* previews) is broader than its intent, so excluding them
        # is a scope decision, not a data problem. Mirrors the narrow-scope
        # policy applied to OpenAI audio above. Remove an entry here if the
        # product scope widens to Gemini speech.
        "gemini/gemini-3.1-flash-tts-preview",
        "gemini/gemini-3.5-live-translate-preview",
        # Same scope rule, 2026-09 arrivals. These carry no "-preview" suffix,
        # so unlike the two above nothing else keeps them out — without these
        # entries they enter the export on the next regeneration.
        #
        # Speech-to-text, i.e. the audio modality the Google scope excludes
        # (Gemini 2.5+ chat + Gemini Embedding + gemini-*-image*).
        "gemini/gemini-3.5-transcribe",
        "gemini/gemini-3.5-transcribe-live",
        # Same scope rule, 2026-09 arrivals: the Gemini Live API pair. Both
        # are mode "realtime" with audio in and out — the modality the Google
        # scope excludes — and they join gemini-3.1-flash-live-preview and
        # gemini-3.5-live-translate-preview, already excluded on the same
        # basis. Like the transcribe pair they carry no "-preview" suffix, so
        # nothing else keeps them out.
        #
        # Listed in BOTH forms: upstream publishes a bare key alongside the
        # gemini/ one for these, and both reach the filter.
        "gemini/gemini-3.8-live",
        "gemini/gemini-3.8-live-extended-thinking",
        # Same scope rule, 2026-09 arrivals: the Gemini 3.8 TTS pair, both
        # mode "audio_speech". They join gemini-3.1-flash-tts-preview and
        # gemini-2.5-flash-preview-tts, already excluded on the same basis.
        # Like the transcribe and live pairs before them they carry no
        # "-preview" suffix, so nothing else keeps them out.
        "gemini/gemini-3.8-flash-tts",
        "gemini/gemini-3.8-flash-lite-tts",
        "gemini-3.8-live",
        "gemini-3.8-live-extended-thinking",
        # DEFERRED, not rejected: ai.google.dev calls gemini-omni-1.1-flash
        # "our next-generation video generation and editing model", but
        # upstream classifies it as mode "chat" and carries only the $1.50 in
        # / $9.00 out text rates. The published tariff also has a SECOND
        # output tier — $17.50 per M for video output (5,792 tokens per
        # second of 720p, ~$0.10/s) — which that shape cannot express, so
        # importing it as chat would under-bill video output by roughly half.
        # Admit it once the mode and the video output tier are modelled.
        "gemini/gemini-omni-1.1-flash",
    ]

    # Date patterns for validation
    DATE_PATTERNS = {
        "yyyymmdd_dash": re.compile(r"-(\d{4})-(\d{2})-(\d{2})$"),
        "yyyymmdd": re.compile(r"(\d{4})(\d{2})(\d{2})$"),
        "mmdd": re.compile(r"-(\d{2})(\d{2})$"),
    }

    # Claude dated snapshot pattern: claude-{variant}-{major}-{minor}-{YYYYMMDD}
    # Example: claude-sonnet-4-5-20250929, claude-opus-4-7-20260416
    CLAUDE_DATED_PATTERN = re.compile(
        r"^claude-([a-z]+)-(\d+)-(\d+)-(\d{4})(\d{2})(\d{2})$",
        re.IGNORECASE,
    )

    # Minimum claude version allowed for dated snapshots
    CLAUDE_DATED_MIN_VERSION = (4, 5)

    # Core claude variants that follow the "Claude {ver} {Variant}" naming
    # pattern (e.g. Claude 4.5 Sonnet, Claude 5 Sonnet). Non-core variants
    # (fable, mythos, ...) keep their fallback capitalized form.
    _CORE_CLAUDE_VARIANTS = frozenset({"opus", "sonnet", "haiku"})

    # Include patterns (exceptions to exclude rules)
    # NOTE: INCLUDE_PATTERNS shortcuts date_pattern and EXCLUDE_PATTERNS only.
    # It does NOT override PROVIDER_EXCLUSION_RULES or EXCLUDE_MODEL_KEYS —
    # both are checked BEFORE the include patterns in
    # should_exclude_with_reason, so an exact-match exclusion always wins.
    # (This note used to claim EXCLUDE_MODEL_KEYS was shortcut too; it never
    # was. Corrected 2026-09-14 after checking the actual evaluation order.)
    # Provider-level exclusions must still be narrowed at their own site.
    INCLUDE_PATTERNS: list[re.Pattern] = [
        re.compile(r"^gpt-.*-chat-latest$", re.IGNORECASE),  # Allow gpt-*-chat-latest despite -latest rule
        re.compile(r"^gemini/gemini-[3-9].*-preview$", re.IGNORECASE),  # Allow Gemini 3.x+ preview models
        # OpenAI audio / realtime allow-list (exact match). Needed to
        # bypass -preview- / date_pattern / ^gpt-realtime global excludes
        # on the dated realtime preview and the gpt-realtime-* keys.
        #
        # Scope = the "Realtime and audio generation models" and
        # "Transcription models" tables of developers.openai.com/api/docs/pricing
        # (snapshot 2026-09-04), plus the older SKUs below that are no longer
        # on the pricing page but still have live model pages.
        # Volcengine Seedream version stamps. contains_date_pattern() fires on
        # the 8-digit YYYYMMDD form (doubao-seedream-4-0-20260415) but not on
        # the 6-digit YYMMDD one, so without this the catalogue would carry an
        # arbitrary subset of the dated Seedream SKUs. Which keys are admitted
        # is decided by VOLCENGINE_ALLOWED_KEYS, checked earlier; this only
        # stops the generic date rule from second-guessing that decision.
        re.compile(r"^volcengine/doubao-seedream-", re.IGNORECASE),
        re.compile(r"^gpt-4o$", re.IGNORECASE),
        re.compile(r"^gpt-4o-mini$", re.IGNORECASE),
        # Current realtime generation. gpt-realtime-2 / -1.5 / -mini are
        # deliberately NOT here: they are superseded snapshots that the
        # pricing page no longer lists (upstream prices gpt-realtime-2
        # identically to 2.1, which is the tell).
        re.compile(r"^gpt-realtime-2\.1$", re.IGNORECASE),
        re.compile(r"^gpt-realtime-2\.1-mini$", re.IGNORECASE),
        re.compile(r"^gpt-realtime-translate$", re.IGNORECASE),
        re.compile(r"^gpt-realtime-whisper$", re.IGNORECASE),
        # gpt-live-1 — full-duplex voice, $0.05/minute billed per second
        # (upstream input_cost_per_second 8.333e-04 x 60 = $0.05). It has NO
        # token pricing at all, so its top-level input/output_cost_per_token
        # export as 0; the real rate is input_cost_per_second in raw_data.
        #
        # Listed here for the record, not because it is load-bearing: nothing
        # excludes it. "^gpt-realtime" and "^gpt-audio" do not match
        # "gpt-live-1", so it entered the export on its own the first time
        # upstream published it. That is worth knowing — the OpenAI audio
        # "allow-list" is a set of exceptions to EXCLUDE_PATTERNS, not a
        # whitelist, so any future OpenAI key that dodges those patterns is
        # admitted automatically rather than by decision.
        re.compile(r"^gpt-live-1$", re.IGNORECASE),
        # Previous realtime generation — off the pricing page but the model
        # pages are still live, so they stay until OpenAI retires them.
        # gpt-realtime itself is now scheduled: shutdown 2027-01-20,
        # replacement gpt-realtime-2.1 (already carried).
        re.compile(r"^gpt-realtime$", re.IGNORECASE),
        # gpt-4o-realtime-preview-2024-12-17 had an include line here. REMOVED
        # 2026-09-14: OpenAI shut the whole gpt-4o-realtime-preview family
        # down on 2026-05-07 (replacement gpt-realtime-1.5, itself superseded
        # by gpt-realtime-2.1, which we carry). With the include gone the
        # generic "-preview-" and date-pattern rules exclude it again, so no
        # EXCLUDE_MODEL_KEYS entry is needed — the model only ever reached
        # the export because this line let it past them.
        re.compile(r"^gpt-4o-mini-transcribe$", re.IGNORECASE),
        re.compile(r"^gpt-4o-mini-tts$", re.IGNORECASE),
        re.compile(r"^whisper-1$", re.IGNORECASE),
        re.compile(r"^tts-1$", re.IGNORECASE),
        re.compile(r"^tts-1-hd$", re.IGNORECASE),
    ]

    # Live upstream (moving target). Used for the export's `source` metadata
    # and by drift_report.py's default, which asks "what would change if we
    # synced today?".
    DATA_SOURCE_URL = (
        "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
    )

    # Pinned upstream snapshot — the input filtered_models.json is generated
    # from. A raw URL at a commit SHA is immutable, so regeneration is
    # reproducible: `python filter_models.py` against this snapshot must
    # reproduce the committed export exactly, and CI enforces that.
    #
    # Bumping the pin IS the upstream sync. Change the SHA, regenerate, and
    # review `python drift_report.py --pinned` before committing — every
    # capability and price change the bump brings in lands in one reviewed
    # diff instead of leaking into unrelated PRs.
    UPSTREAM_PIN = "d098b02ed956977834c542d3995382e361d6d41c"  # BerriAI/litellm main, 2026-09-30
    UPSTREAM_SNAPSHOT_URL = (
        "https://raw.githubusercontent.com/BerriAI/litellm/"
        f"{UPSTREAM_PIN}/model_prices_and_context_window.json"
    )

    # Sync configuration
    SYNC_CONFIG = {
        "max_retries": 3,
        "retry_delay": 5000,
        "timeout": 30000,
        "batch_size": 50,
        "price_change_threshold": 0.0001,
    }

    @classmethod
    def is_valid_date_pattern(cls, year: int, month: int, day: int) -> bool:
        """Check if a string is a valid date in the expected range."""
        if year < 2020 or year > 2030:
            return False
        if month < 1 or month > 12:
            return False
        if day < 1 or day > 31:
            return False
        return True

    @classmethod
    def is_claude_dated_snapshot(cls, model_key: str) -> bool:
        """
        Check if model_key is a claude dated snapshot with version >= CLAUDE_DATED_MIN_VERSION.

        Matches: claude-{variant}-{major}-{minor}-{YYYYMMDD}
        Allows only versions >= 4.5 (configurable via CLAUDE_DATED_MIN_VERSION).
        Rejects 3.x snapshots and 4.0/4.1 snapshots.
        """
        match = cls.CLAUDE_DATED_PATTERN.match(model_key)
        if not match:
            return False

        year = int(match.group(4))
        month = int(match.group(5))
        day = int(match.group(6))
        if not cls.is_valid_date_pattern(year, month, day):
            return False

        major = int(match.group(2))
        minor = int(match.group(3))
        return (major, minor) >= cls.CLAUDE_DATED_MIN_VERSION

    @classmethod
    def contains_date_pattern(cls, model_key: str) -> bool:
        """Check if a model key contains a date pattern."""
        # Check YYYY-MM-DD pattern
        dash_match = cls.DATE_PATTERNS["yyyymmdd_dash"].search(model_key)
        if dash_match:
            year, month, day = int(dash_match.group(1)), int(dash_match.group(2)), int(dash_match.group(3))
            if cls.is_valid_date_pattern(year, month, day):
                return True

        # Check YYYYMMDD pattern
        yyyymmdd_match = cls.DATE_PATTERNS["yyyymmdd"].search(model_key)
        if yyyymmdd_match:
            year, month, day = int(yyyymmdd_match.group(1)), int(yyyymmdd_match.group(2)), int(yyyymmdd_match.group(3))
            if cls.is_valid_date_pattern(year, month, day):
                return True

        # Check MMDD pattern
        mmdd_match = cls.DATE_PATTERNS["mmdd"].search(model_key)
        if mmdd_match:
            month, day = int(mmdd_match.group(1)), int(mmdd_match.group(2))
            if 1 <= month <= 12 and 1 <= day <= 31:
                return True

        return False

    @classmethod
    def should_exclude_by_provider(cls, model_key: str, provider: str) -> bool:
        """Check if a model key should be excluded based on provider-specific rules."""
        rules = cls.PROVIDER_EXCLUSION_RULES.get(provider.lower())
        if not rules:
            return False

        # Check patterns
        patterns = rules.get("patterns", [])
        for pattern in patterns:
            if pattern.search(model_key):
                return True

        # Check custom function
        custom_check = rules.get("custom_check")
        if custom_check and callable(custom_check):
            return custom_check(model_key)

        return False

    @classmethod
    def should_exclude_with_reason(
        cls, model_key: str, provider: str | None = None
    ) -> tuple[bool, str | None]:
        """
        Check exclusion and return the rule that triggered it.

        Returns:
            (True, reason) if excluded, where reason is one of:
                'provider_exclusion', 'exact_match', 'date_pattern', 'global_exclusion'
            (False, None) if not excluded
        """
        # Provider-specific exclusion rules have highest priority
        if provider and cls.should_exclude_by_provider(model_key, provider):
            return True, "provider_exclusion"

        # Check exact match exclude list
        if model_key in cls.EXCLUDE_MODEL_KEYS:
            return True, "exact_match"

        # Check include patterns (exceptions to global rules)
        for pattern in cls.INCLUDE_PATTERNS:
            if pattern.search(model_key):
                return False, None

        # Allow claude dated snapshots with version >= CLAUDE_DATED_MIN_VERSION
        if cls.is_claude_dated_snapshot(model_key):
            return False, None

        # Check for date patterns
        if cls.contains_date_pattern(model_key):
            return True, "date_pattern"

        # Check global exclude patterns
        for pattern in cls.EXCLUDE_PATTERNS:
            if pattern.search(model_key):
                return True, "global_exclusion"

        return False, None

    @classmethod
    def should_exclude(cls, model_key: str, provider: str | None = None) -> bool:
        """Check if a model key should be excluded."""
        excluded, _ = cls.should_exclude_with_reason(model_key, provider)
        return excluded

    # Per-mode pricing fields used for "non-zero price" validation
    PRICE_FIELDS_BY_MODE = {
        # Image generation. OUTPUT fields are listed too, and they matter:
        # a model billed purely on generated images with free input — e.g.
        # volcengine/doubao-seedream-5-0-lite, whose input is 免费 — has no
        # non-zero input field at all and was invisible to this check before
        # 2026-09-17. Third instance of the same defect class, after
        # tiered_pricing (v1.16.19) and realtime input_cost_per_second
        # (v1.16.26): a priced model vanishing because the vendor bills on
        # an axis this tuple did not enumerate.
        "image_generation": (
            "input_cost_per_token",
            "input_cost_per_image_token",
            "input_cost_per_image",
            "output_cost_per_token",
            "output_cost_per_image_token",
            "output_cost_per_image",
        ),
        # Volcengine Seedance: USD/token via the standard
        # output_cost_per_token family, tiered by resolution (base 720p
        # / 1080p / 4K) and v2v marker. Any one non-zero tier is
        # sufficient to consider the SKU priced. CNY-source values are
        # converted at the policy FX rate inside the LiteLLM fork (see
        # the fork's VOLCENGINE_FX_POLICY.md); saas-models-source
        # consumes USD directly.
        "video_generation": (
            "output_cost_per_token",
            "output_cost_per_token_with_input_video",
            "output_cost_per_token_1080p",
            "output_cost_per_token_1080p_with_input_video",
            "output_cost_per_token_4k",
            "output_cost_per_token_4k_with_input_video",
        ),
        # Audio speech (TTS): billed on text input + audio output. Different
        # families bill differently — gpt-4o-*-tts uses per-token + per-audio-
        # token; tts-1 / tts-1-hd bill per character. Any one non-zero field
        # means priced.
        "audio_speech": (
            "input_cost_per_token",
            "output_cost_per_token",
            "output_cost_per_audio_token",
            "output_cost_per_second",
            "input_cost_per_character",
            "output_cost_per_character",
        ),
        # Audio transcription (ASR): billed on audio input. whisper-1 uses
        # per-second, gpt-4o-*-transcribe uses per-token + per-audio-token
        # (with a text output cost too). Any one non-zero field means priced.
        "audio_transcription": (
            "input_cost_per_second",
            "input_cost_per_audio_token",
            "input_cost_per_token",
        ),
        # Realtime (/v1/realtime): a bidirectional session billed on four
        # axes — text in/out plus audio in/out — and some SKUs add
        # input_cost_per_image for vision turns. Any one non-zero field
        # means priced, same tolerance as the audio modes.
        #
        # input_cost_per_second is here because not every realtime SKU is
        # token-billed: gpt-realtime-translate is quoted purely per minute
        # ($0.034/min → input_cost_per_second upstream) and carries no token
        # price at all, so without this field it reads as unpriced and gets
        # dropped. Same class of bug as should_exclude_due_to_price not
        # reading tiered_pricing — a priced model silently vanishing because
        # the vendor bills it on an axis this table did not list.
        "realtime": (
            "input_cost_per_token",
            "output_cost_per_token",
            "input_cost_per_audio_token",
            "output_cost_per_audio_token",
            "input_cost_per_image",
            "input_cost_per_second",
        ),
    }

    @staticmethod
    def _has_tiered_price(model_data: dict[str, Any]) -> bool:
        """True if ``tiered_pricing`` carries at least one non-zero input price.

        Shape (LiteLLM upstream):
            "tiered_pricing": [
                {"range": [0, 256000], "input_cost_per_token": 4e-07,
                 "output_cost_per_token": 1.6e-06},
                ...
            ]
        """
        tiers = model_data.get("tiered_pricing")
        if not isinstance(tiers, list):
            return False
        for tier in tiers:
            if not isinstance(tier, dict):
                continue
            value = tier.get("input_cost_per_token")
            if value is not None and value > 0:
                return True
        return False

    @classmethod
    def should_exclude_due_to_price(cls, model_data: dict[str, Any]) -> bool:
        """Check if a model should be excluded due to zero/missing price."""
        mode = model_data.get("mode")

        # Image generation: accept any non-zero input pricing field
        # (some models bill per token, others per image)
        if mode == "image_generation":
            for field in cls.PRICE_FIELDS_BY_MODE["image_generation"]:
                value = model_data.get(field)
                if value is not None and value > 0:
                    return False
            return True

        # Video generation: provider-specific keyed pricing (Volcengine
        # uses volcengine_video_output_cost_per_million_tokens_*); a SKU
        # is considered priced if any one resolution-tier field is set.
        if mode == "video_generation":
            for field in cls.PRICE_FIELDS_BY_MODE["video_generation"]:
                value = model_data.get(field)
                if value is not None and value > 0:
                    return False
            return True

        # Audio speech / transcription / realtime: schema-heterogeneous
        # (per-second vs per-token vs per-audio-token). Any one non-zero
        # field is enough.
        if mode in ("audio_speech", "audio_transcription", "realtime"):
            for field in cls.PRICE_FIELDS_BY_MODE.get(mode, ()):
                value = model_data.get(field)
                if value is not None and value > 0:
                    return False
            return True

        input_cost = model_data.get("input_cost_per_token")
        output_cost = model_data.get("output_cost_per_token")

        # Tiered pricing (阶梯计价): some vendors — Alibaba's Qwen family in
        # particular — bill at a unit price that depends on the total input
        # size of the request, and LiteLLM upstream expresses that as a
        # `tiered_pricing` array INSTEAD of the flat cost fields. Such a SKU
        # is priced even though input_cost_per_token is absent, so treat a
        # tier array carrying any non-zero input price as priced.
        #
        # This repo still populates the flat fields for the SKUs it curates
        # (see the note in DASHSCOPE_SYNTH_DATA on which tier is used and
        # why); the branch exists so an upstream-only tiered entry is not
        # silently dropped as "zero price" the way dashscope/qwen-flash was.
        if cls._has_tiered_price(model_data):
            return False

        if input_cost is None or input_cost == 0:
            return True

        # Embedding models only have input cost, skip output cost check
        if mode != "embedding":
            if output_cost is None or output_cost == 0:
                return True

        return False

    @classmethod
    def is_provider_supported(cls, provider: str | None) -> bool:
        """Check if a provider is supported."""
        if provider is None:
            return False
        return provider.lower() in cls.PROVIDERS

    @classmethod
    def is_mode_supported(cls, mode: str | None) -> bool:
        """Check if mode is supported (only 'chat' mode)."""
        if mode is None:
            return False
        return mode in cls.SUPPORTED_MODES

    @classmethod
    def map_provider_name(cls, provider: str | None) -> str:
        """Map provider name to standardized name."""
        if provider is None:
            return ""
        normalized = provider.lower()
        return cls.PROVIDER_MAPPING.get(normalized, normalized)

    @classmethod
    def map_mode_to_type(cls, mode: str | None) -> str:
        """Map mode to model type."""
        if mode is None:
            return "language"
        return cls.MODE_MAPPING.get(mode, "language")

    @classmethod
    def format_model_name(cls, model_key: str, provider: str) -> str:
        """
        Format model key to friendly display name.

        Examples:
            claude-opus-4-1 → Claude Opus 4.1
            gpt-5-mini → GPT-5 Mini
            o3-mini → o3 Mini
            gemini-2.5-flash → Gemini 2.5 Flash
        """
        key = model_key.lower()

        # Anthropic: claude-opus-4-1 → Claude Opus 4.1
        # Official naming (Claude 4.x / 5 generation) is variant-first:
        # "Claude Opus 4.7", "Claude Sonnet 5", "Claude Haiku 4.5"
        # — matching platform.claude.com. (Claude 3 used version-first,
        # e.g. "Claude 3.5 Sonnet"; Anthropic switched the order at Claude 4.)
        if provider == "anthropic" or key.startswith("claude-"):
            # Dated snapshot: claude-sonnet-4-5-20250929 → Claude Sonnet 4.5
            # Official display names carry NO date suffix — a dated snapshot
            # shares its base model's display name (platform.claude.com); the
            # date lives only in model_key, which still disambiguates the entry.
            dated = cls.CLAUDE_DATED_PATTERN.match(key)
            if dated:
                variant = dated.group(1).capitalize()
                major_version = dated.group(2)
                minor_version = dated.group(3)
                return f"Claude {variant} {major_version}.{minor_version}"

            parts = key.replace("claude-", "").split("-")
            # Expected format: opus-4-1, sonnet-4-5, haiku-4-5
            if len(parts) >= 3:
                variant = parts[0].capitalize()  # Opus, Sonnet, Haiku
                major_version = parts[1]  # 4
                minor_version = parts[2]  # 1, 5
                return f"Claude {variant} {major_version}.{minor_version}"
            # Major-only for core variants, e.g. claude-sonnet-5 → "Claude Sonnet 5".
            # Restricted to the standard Opus/Sonnet/Haiku family so that
            # non-core variants (fable, mythos, ...) keep their fallback form.
            if len(parts) == 2 and parts[0] in cls._CORE_CLAUDE_VARIANTS:
                variant = parts[0].capitalize()
                major_version = parts[1]
                return f"Claude {variant} {major_version}"
            # Fallback: capitalize words (e.g. claude-fable-5 → "Claude Fable 5")
            return " ".join(w.capitalize() for w in key.split("-"))

        # OpenAI — each family per OpenAI's own house style (openai.com):
        #   gpt-5-mini → GPT-5 mini, gpt-5.4-nano → GPT-5.4 nano (mini/nano
        #   lowercase); o3-mini → o3-mini, o4-mini → o4-mini (lowercase and
        #   hyphenated, shown as the id); text-embedding-3-large kept as the
        #   lowercase id; gpt-5.3-codex → GPT-5.3-Codex (hyphenated Codex);
        #   gpt-4o-realtime-preview-<date> → GPT-4o Realtime (drop the snapshot).
        if provider == "openai":
            # Embedding and standalone TTS models are presented as their
            # lowercase id (openai.com utility-model style): text-embedding-3-*,
            # tts-1, tts-1-hd.
            if key.startswith(("text-embedding-", "tts-")):
                return key

            # Image: gpt-image-1 → GPT Image 1, gpt-image-1.5 → GPT Image 1.5
            if key.startswith("gpt-image-"):
                suffix = key.replace("gpt-image-", "")
                suffix_formatted = " ".join(w.capitalize() for w in suffix.split("-"))
                return f"GPT Image {suffix_formatted}"

            # o series: shown exactly as the lowercase id — o3, o3-mini, o4-mini.
            if re.match(r"^o\d+", key):
                return key

            # GPT series: gpt-5-mini → GPT-5 mini
            if key.startswith("gpt-"):
                # Dated realtime preview: gpt-4o-realtime-preview-2024-12-17
                # → GPT-4o Realtime (drop the -preview-<date> snapshot tail).
                gpt_key = re.sub(r"-preview-\d{4}-\d{2}-\d{2}$", "", key)
                parts = gpt_key.replace("gpt-", "").split("-")
                head = parts[0]
                # Codex is hyphenated in OpenAI's naming (GPT-5.3-Codex).
                if parts[1:] == ["codex"]:
                    return f"GPT-{head.upper()}-Codex"
                # str.title() mangles branded abbreviations (Tts → TTS) and would
                # uppercase the size suffixes; patch both so mini / nano stay
                # lowercase per OpenAI's house style.
                overrides = {"tts": "TTS", "asr": "ASR", "mini": "mini", "nano": "nano"}
                fmt = lambda w: overrides.get(w.lower(), w.capitalize())
                # Non-numeric head (e.g. gpt-realtime, gpt-audio) → "GPT Realtime"
                # (space, no dash — OpenAI's brand style for named products).
                if not re.match(r"^\d", head):
                    return "GPT " + " ".join(fmt(w) for w in parts)
                # Numeric head with the branded "4o" lowercase-o family:
                # keep the "o" lowercase per OpenAI's official spelling
                # (GPT-4o, GPT-4o Mini). Guarded by a strict \d+o$ match so
                # generic versions (5, 5.5, 4.1) still uppercase normally.
                if re.match(r"^\d+o$", head, re.IGNORECASE):
                    version = head.lower()
                else:
                    version = head.upper()
                suffix = " ".join(fmt(w) for w in parts[1:])
                return f"GPT-{version} {suffix}" if suffix else f"GPT-{version}"

            # Fallback
            return " ".join(w.capitalize() for w in key.split("-"))

        # GLM family (zai / bigmodel):
        #   zai/glm-4.7 → GLM-4.7, zai/glm-4.5-air → GLM-4.5-Air,
        #   zai/glm-4.5v → GLM-4.5V, zai/glm-4-32b-0414-128k → GLM-4-32B-0414-128K,
        #   bigmodel/glm-4.7 → GLM-4.7 (same rule, region differs via `provider`).
        if provider in ("zai", "bigmodel") or key.startswith(("zai/", "bigmodel/")):
            suffix = re.sub(r"^(zai|bigmodel)/(glm-)?", "", key, flags=re.IGNORECASE)
            overrides = cls.ZAI_NAME_SEGMENT_OVERRIDES
            # str.title() uppercases each letter-run head, naturally producing
            # 32B / 128K / 4.5V; overrides patch branded suffixes (FlashX, AirX, OCR).
            return "GLM-" + "-".join(
                overrides.get(p.lower(), p.title()) for p in suffix.split("-")
            )

        # Volcengine / new-api / ecloud_aicc Doubao families:
        #   volcengine/doubao-seedance-2-0-260128       → Doubao-Seedance 2.0
        #   volcengine/doubao-seedance-2-0-fast-260128  → Doubao-Seedance 2.0 Fast
        #   volcengine/doubao-seedance-2-0-mini-260615  → Doubao-Seedance 2.0 Mini
        #   volcengine/doubao-seedance-2-0              → Doubao-Seedance 2.0
        #   volcengine/doubao-seedream-5-0-pro-260628   → Doubao-Seedream 5.0 Pro
        #   volcengine/doubao-seedream-5-0-lite         → Doubao-Seedream 5.0 Lite
        #   new-api/doubao-seedance-2-0-fast            → Doubao-Seedance 2.0 Fast
        #   ecloud_aicc/doubao-seedance-2-0-mini        → Doubao-Seedance 2.0 Mini
        # Dated suffixes (-260128, -260615) are the official Volcengine
        # model-version stamps (YYMMDD); strip them for the friendly name.
        # new-api and ecloud_aicc are catalogue-layer mirror providers that
        # reuse Volcengine's naming; the branch covers all three prefixes.
        #
        # The family (seedance video / seedream image) is CAPTURED rather
        # than hard-coded. It used to be literal "Doubao-Seedance" with a
        # regex that only stripped the seedance prefix, so the first
        # non-Seedance volcengine SKU rendered as
        # "Doubao-Seedance volcengine/doubao.seedream 5 0 Pro" — the prefix
        # survived the failed substitution and was then split on "-".
        # The match is now a guard: a key that fits neither family falls
        # through to the generic formatter instead of producing that.
        seedx = re.match(
            r"^(?:volcengine|new-api|ecloud_aicc)/doubao-(seedance|seedream)-(.+)$",
            key,
            flags=re.IGNORECASE,
        )
        if seedx and (
            provider in ("volcengine", "new-api", "ecloud_aicc")
            or key.startswith(("volcengine/", "new-api/", "ecloud_aicc/"))
        ):
            family = seedx.group(1).capitalize()
            # Drop the trailing version stamp. Volcengine uses YYMMDD for most
            # SKUs but shipped at least one 8-digit YYYYMMDD
            # (doubao-seedream-4-0-20260415), so both widths are handled.
            suffix = re.sub(r"-(?:\d{8}|\d{6})$", "", seedx.group(2))
            parts = suffix.split("-")
            version = (
                f"{parts[0]}.{parts[1]}" if len(parts) >= 2 else suffix
            )
            variant = (
                " ".join(p.capitalize() for p in parts[2:])
                if len(parts) > 2
                else ""
            )
            return f"Doubao-{family} {version} {variant}".rstrip()

        # BytePlus (overseas Ark) Dreamina Seedance video:
        #   byteplus/dreamina-seedance-2-5-260628       → Dreamina Seedance 2.5
        #   byteplus/dreamina-seedance-2-0-fast-260128  → Dreamina Seedance 2.0 Fast
        #   byteplus/dreamina-seedance-2-0-mini         → Dreamina Seedance 2.0 Mini
        # Same YYMMDD-stripping shape as the Volcengine branch above, but the
        # brand renders as "Dreamina Seedance" with a SPACE — that is how
        # docs.byteplus.com writes it, whereas Volcengine writes the
        # hyphenated "Doubao-Seedance". Per-vendor official naming, as of
        # v1.16.2; do not "normalise" the two to match each other.
        if provider == "byteplus" or key.startswith("byteplus/"):
            suffix = re.sub(
                r"^byteplus/dreamina-seedance-", "", key, flags=re.IGNORECASE
            )
            suffix = re.sub(r"-\d{6}$", "", suffix)  # drop -YYMMDD
            parts = suffix.split("-")
            version = f"{parts[0]}.{parts[1]}" if len(parts) >= 2 else suffix
            variant = (
                " ".join(p.capitalize() for p in parts[2:])
                if len(parts) > 2
                else ""
            )
            return f"Dreamina Seedance {version} {variant}".rstrip()

        # DashScope (Alibaba Model Studio):
        #   dashscope/qwen3.8-flash → Qwen3.8-Flash
        # Alibaba writes model IDs lowercase in the API but renders the brand
        # as "Qwen3.8-Flash" in prose and in the vision docs' capability
        # tables; hyphenated title-case matches how this catalogue already
        # renders GLM-5.3-Flash and DeepSeek-V4-Flash.
        if provider == "dashscope" or key.startswith("dashscope/"):
            suffix = re.sub(r"^dashscope/", "", key, flags=re.IGNORECASE)
            # Parameter-count segments are upper-cased the way Alibaba writes
            # them: qwen3.8-2.4t-a95b → Qwen3.8-2.4T-A95B, not "2.4t-A95b".
            # Matches a size token — optional letter, digits/dot, unit letter
            # (2.4t, a95b, 30b) — and leaves ordinary words to capitalize().
            def _seg(part: str) -> str:
                if re.fullmatch(r"[a-z]?[\d.]+[a-z]", part, flags=re.IGNORECASE):
                    return part.upper()
                return part.capitalize()

            return "-".join(_seg(p) for p in suffix.split("-"))

        # DeepSeek:
        #   deepseek/deepseek-v4-flash → DeepSeek-V4-Flash
        #   deepseek/deepseek-v4-pro   → DeepSeek-V4-Pro
        # Branded camel-case (DeepSeek) deliberately differs from str.title().
        if provider == "deepseek" or key.startswith("deepseek/"):
            suffix = re.sub(r"^deepseek/(deepseek-)?", "", key, flags=re.IGNORECASE)
            # str.title() naturally produces V4 / R1 etc. — no overrides needed today.
            return "DeepSeek-" + "-".join(p.title() for p in suffix.split("-"))

        # Moonshot (Kimi): moonshot/kimi-k3 → Kimi K3,
        #   moonshot/kimi-k2.7-code → Kimi K2.7 Code. Space-separated per
        #   Kimi's official brand; version tokens (k3, k2.7) upcase.
        if provider == "moonshot" or key.startswith("moonshot/"):
            suffix = re.sub(r"^moonshot/(kimi-)?", "", key, flags=re.IGNORECASE)
            # Branded segment casing (Kimi's official spelling).
            overrides = {"highspeed": "HighSpeed"}
            parts = []
            for p in suffix.split("-"):
                if p.lower() in overrides:
                    parts.append(overrides[p.lower()])
                elif re.match(r"^k\d", p, re.IGNORECASE):  # version token: k3, k2.7
                    parts.append(p.upper())
                else:
                    parts.append(p.capitalize())
            return "Kimi " + " ".join(parts)

        # Google: gemini-2.5-flash → Gemini 2.5 Flash
        # gemini/gemini-2.5-flash → Gemini 2.5 Flash
        if provider == "google" or key.startswith("gemini"):
            # Remove gemini/ prefix if present
            clean_key = key
            if clean_key.startswith("gemini/"):
                clean_key = clean_key[7:]  # Remove 'gemini/'
            # Remove gemini- prefix
            clean_key = clean_key.replace("gemini-", "")

            # Embedding models: gemini-embedding-2 → Gemini Embedding 2
            # ("Embedding" capitalized, per Google's "Gemini Embedding" brand).
            if clean_key.startswith("embedding"):
                rest = clean_key[len("embedding"):].lstrip("-")
                return f"Gemini Embedding {rest}".rstrip()

            parts = clean_key.split("-")
            if len(parts) >= 2:
                version = parts[0]  # 2.5, 1.5
                variant = " ".join(w.capitalize() for w in parts[1:])  # Flash, Flash Lite, Pro
                # Flash-Lite is hyphenated in Google's official naming.
                variant = variant.replace("Flash Lite", "Flash-Lite")
                return f"Gemini {version} {variant}"
            return " ".join(w.capitalize() for w in clean_key.split("-"))

        # Fallback: capitalize each word
        return " ".join(w.capitalize() for w in key.split("-"))

    @classmethod
    def is_default_available(cls, model_key: str, provider: str, model_type: str = "language") -> bool:
        """
        Check if a model is default available for users.

        Rules:
        - Default: true for all models
        - Image models (model_type == "image"): false
        - OpenAI o series (o3, o4, etc.): false
        - OpenAI chat series (gpt-*-chat-*): false

        Args:
            model_key: Model identifier
            provider: Provider name (mapped, lowercase)
            model_type: Mapped model type (language, embedding, image, audio)

        Returns:
            True if model is default available, False otherwise
        """
        # Image / video models require special access by default
        if model_type in ("image", "video"):
            return False

        # Default is true
        is_available = True

        # OpenAI specific rules
        if provider == "openai":
            # o series: o3, o3-mini, o4, o4-mini, etc.
            if re.match(r"^o\d", model_key.lower()):
                is_available = False
            # chat series: gpt-*-chat-*
            elif re.search(r"-chat-", model_key.lower()):
                is_available = False

        return is_available

    # Vision detection for GLM-family vision SKUs (zai/ and bigmodel/).
    # LiteLLM source often omits supports_vision; we infer it from the key.
    _GLM_VISION_KEY = re.compile(
        r"^(?:zai|bigmodel)/glm-(?:[\d.]+v(?:-|$)|ocr$|ocr-)", re.IGNORECASE
    )

    @classmethod
    def resolve_supports_vision(
        cls, model_key: str, provider: str, raw_value: bool
    ) -> bool:
        """Return supports_vision, inferring True for GLM vision SKUs when upstream omits it."""
        if raw_value:
            return True
        if provider in ("zai", "bigmodel") and cls._GLM_VISION_KEY.match(model_key):
            return True
        return False

    @classmethod
    def filter_model(cls, model_key: str, model_data: dict[str, Any]) -> dict[str, Any] | None:
        """
        Filter a single model and return transformed data if it passes all rules.

        Returns:
            dict with transformed model data if model passes filters, None otherwise
        """
        provider = model_data.get("litellm_provider")
        mode = model_data.get("mode")

        # Check provider support
        if not cls.is_provider_supported(provider):
            return None

        # Check mode support
        if not cls.is_mode_supported(mode):
            return None

        # Check exclusion rules
        if cls.should_exclude(model_key, provider):
            return None

        # Check price
        if cls.should_exclude_due_to_price(model_data):
            return None

        # Transform and return model data
        mapped_provider = cls.map_provider_name(provider)
        model_type = cls.map_mode_to_type(mode)
        friendly_name = cls.format_model_name(model_key, mapped_provider)
        default_available = cls.is_default_available(model_key, mapped_provider, model_type)

        return {
            "model_key": model_key,
            "provider": mapped_provider,
            "type": model_type,
            "friendly_name": friendly_name,
            "is_default_available": default_available,
            "input_cost_per_token": model_data.get("input_cost_per_token"),
            "output_cost_per_token": model_data.get("output_cost_per_token"),
            "cache_read_input_token_cost": model_data.get("cache_read_input_token_cost"),
            "max_input_tokens": model_data.get("max_input_tokens"),
            "max_output_tokens": model_data.get("max_output_tokens"),
            "supports_vision": cls.resolve_supports_vision(
                model_key, mapped_provider, bool(model_data.get("supports_vision", False))
            ),
            "supports_function_calling": model_data.get("supports_function_calling", False),
            "supports_json_output": model_data.get("supports_json_mode", False),
            "raw_data": model_data,
        }

    @classmethod
    def apply_zai_synth(cls, models: dict[str, Any]) -> dict[str, Any]:
        """
        Inject z.ai-authoritative data into the upstream model dict.

        - Pre-staged SKUs (not present upstream) are added wholesale.
        - SKUs present upstream get the overlay merged on top (synth wins for
          any field z.ai considers authoritative, e.g. zai/glm-4.5v context).

        Does not mutate the input.
        """
        merged: dict[str, Any] = dict(models)
        for key, synth in cls.ZAI_SYNTH_DATA.items():
            existing = merged.get(key)
            if existing is None:
                merged[key] = dict(synth)
            else:
                merged[key] = {**existing, **synth}
        return merged

    @classmethod
    def apply_anthropic_synth(cls, models: dict[str, Any]) -> dict[str, Any]:
        """
        Apply ANTHROPIC_SYNTH_DATA to the upstream dict.

        Two behaviours, keyed on whether upstream already carries the SKU:
          • Present upstream → overlay (``{**existing, **synth}``), for fields
            upstream gets wrong (currently the claude-sonnet-4-5 context
            window) or time-boxed price patches. Remove each once upstream
            catches up.
          • Absent upstream → inject the synth entry wholesale, for complete
            pre-staged models. A partial overlay entry whose SKU is missing
            upstream would inject a broken record, so only pre-stage entries
            that are complete (carry ``litellm_provider``).

        Does not mutate the input.
        """
        merged: dict[str, Any] = dict(models)
        for key, synth in cls.ANTHROPIC_SYNTH_DATA.items():
            existing = merged.get(key)
            merged[key] = dict(synth) if existing is None else {**existing, **synth}
        return merged

    @classmethod
    def apply_google_synth(cls, models: dict[str, Any]) -> dict[str, Any]:
        """
        Inject Google / Gemini SKUs newly published on ai.google.dev but not
        yet carried by BerriAI upstream (GOOGLE_SYNTH_DATA). Entries are
        complete litellm-style records; a present upstream key is overlaid,
        an absent one is injected wholesale. Remove an entry once upstream
        carries the same model.

        Does not mutate the input.
        """
        merged: dict[str, Any] = dict(models)
        for key, synth in cls.GOOGLE_SYNTH_DATA.items():
            existing = merged.get(key)
            merged[key] = dict(synth) if existing is None else {**existing, **synth}
        return merged

    @classmethod
    def apply_deepseek_alias(cls, models: dict[str, Any]) -> dict[str, Any]:
        """
        Mirror canonical deepseek/* entries onto project alias keys.

        For each row in ``DEEPSEEK_ALIAS_SOURCES`` the source entry is copied
        verbatim. The namespace does not change, so unlike
        ``apply_newapi_synth`` nothing is overridden — the alias is a copy of
        its source and therefore cannot carry a different price.

        A missing source means the alias is skipped rather than injected
        half-formed, so a vanished source surfaces as a missing model instead
        of a stale duplicate.

        Does not mutate the input.
        """
        merged: dict[str, Any] = dict(models)
        for alias_key, source_key in cls.DEEPSEEK_ALIAS_SOURCES.items():
            source = merged.get(source_key)
            if source is None:
                continue
            merged[alias_key] = dict(source)
        return merged

    @classmethod
    def apply_capability_mirrors(cls, models: dict[str, Any]) -> dict[str, Any]:
        """
        Replace each mirror target's supports_* flags with its source's.

        Runs after every vendor synth so sources are fully resolved (upstream
        + overlays + allowlisted overrides). The target's own supports_* are
        dropped first, so a flag the source lacks cannot survive on the target.
        A missing target or source is skipped rather than half-built.

        Does not mutate the input.
        """
        merged: dict[str, Any] = dict(models)
        for target_key, source_key in cls.CAPABILITY_MIRRORS.items():
            target, source = merged.get(target_key), merged.get(source_key)
            if target is None or source is None:
                continue
            merged[target_key] = {
                **{f: v for f, v in target.items() if not f.startswith("supports_")},
                **{f: v for f, v in source.items() if f.startswith("supports_")},
            }
        return merged

    @classmethod
    def apply_moonshot_synth(cls, models: dict[str, Any]) -> dict[str, Any]:
        """
        Inject Moonshot / Kimi SKUs published on platform.kimi.ai but not yet
        carried by BerriAI upstream (MOONSHOT_SYNTH_DATA). Complete litellm-style
        entries; injected wholesale when absent, overlaid when present. Remove an
        entry once upstream carries the same model.

        Does not mutate the input.
        """
        merged: dict[str, Any] = dict(models)
        for key, synth in cls.MOONSHOT_SYNTH_DATA.items():
            existing = merged.get(key)
            merged[key] = dict(synth) if existing is None else {**existing, **synth}
        return merged

    @classmethod
    def apply_bigmodel_synth(cls, models: dict[str, Any]) -> dict[str, Any]:
        """
        Inject bigmodel/* SKUs and mirror pricing from their sibling zai/* entry.

        Prerequisite: must run after ``apply_zai_synth`` so the ``zai/*``
        entries in ``models`` already reflect z.ai's authoritative prices.
        ``filter_all_models`` / ``get_filter_stats`` enforce this ordering.

        For each ``bigmodel/<sku>``:
          1. Merge BIGMODEL_SYNTH_DATA metadata (context, capabilities).
          2. Mirror ``input_cost_per_token`` / ``output_cost_per_token`` /
             ``cache_read_input_token_cost`` from the matching ``zai/<sku>``.

        Mirroring runs last so it always wins over any stale upstream values.
        If the sibling zai SKU lacks a price field, that field is simply not
        set on the bigmodel SKU — the model then fails the zero-price filter
        downstream, surfacing the gap instead of silently exporting bad data.

        Does not mutate the input.
        """
        merged: dict[str, Any] = dict(models)
        for key, synth in cls.BIGMODEL_SYNTH_DATA.items():
            # Resolve sibling zai key: "bigmodel/glm-5" → "zai/glm-5"
            zai_key = "zai/" + key.split("/", 1)[1]
            zai_entry = merged.get(zai_key) or {}
            mirrored = {
                field: zai_entry[field]
                for field in cls._BIGMODEL_MIRRORED_PRICE_FIELDS
                if field in zai_entry
            }
            existing = merged.get(key) or {}
            merged[key] = {**existing, **synth, **mirrored}
        return merged

    @classmethod
    def apply_openai_synth(cls, models: dict[str, Any]) -> dict[str, Any]:
        """
        Overlay OpenAI-authoritative GPT-5 pricing onto the upstream dict.

        LiteLLM upstream trailed OpenAI's July 2026 GPT-5 pricing refresh, so
        OPENAI_SYNTH_DATA carries the officially-published corrections and the
        billing fields absent upstream. The overlay is additive — synth wins on
        any overlapping key, but keys the project already carries and synth does
        not touch (e.g. supported_endpoints, extra supports_* flags) survive.

        Two behaviours, keyed on whether upstream already carries the SKU —
        same contract as apply_anthropic_synth:
          • Present upstream → overlay (``{**existing, **synth}``). Used for
            partial corrections such as the gpt-6-astra context fix.
          • Absent upstream → inject the synth entry wholesale, for complete
            pre-staged models (none at present). A partial overlay whose SKU is missing
            upstream would inject a broken record, so only pre-stage entries
            that are complete (carry ``litellm_provider``).

        Does not mutate the input.
        """
        merged: dict[str, Any] = dict(models)
        for key, synth in cls.OPENAI_SYNTH_DATA.items():
            existing = merged.get(key)
            # Overlay when upstream carries the SKU (partial corrections like
            # the gpt-5.5 priority tier); inject wholesale when absent (complete
            # pre-staged entries such as tts-1 / tts-1-hd). Only pre-stage
            # entries that are complete (carry litellm_provider).
            merged[key] = dict(synth) if existing is None else {**existing, **synth}
        return merged

    @classmethod
    def apply_dashscope_synth(cls, models: dict[str, Any]) -> dict[str, Any]:
        """
        Apply DASHSCOPE_SYNTH_DATA (Alibaba Cloud Model Studio / 百炼).

        Entries are injected wholesale when absent upstream (qwen3.7-flash,
        qwen3.8-2.4t-a95b) and overlaid when present (qwen3.7-plus's
        discounted tiered prices), with the official Model Studio pricing
        page as the source of truth.

        Prices are the **International USD** tariff, matching the convention
        upstream already uses for ``dashscope/*``; the domestic 百炼 CNY
        tariff is a separate book and is deliberately not mixed in.

        Does not mutate the input.
        """
        merged: dict[str, Any] = dict(models)
        for key, synth in cls.DASHSCOPE_SYNTH_DATA.items():
            existing = merged.get(key)
            merged[key] = dict(synth) if existing is None else {**existing, **synth}
        return merged

    @classmethod
    def apply_volcengine_synth(cls, models: dict[str, Any]) -> dict[str, Any]:
        """
        Inject Volcengine Seedance video SKUs not yet on LiteLLM upstream.

        Upstream BerriAI/litellm/main carries only chat / embedding doubao
        SKUs under ``volcengine/*`` today; the six Seedance 2.0 video
        entries are pre-staged from the official Volcengine pricing page
        (https://www.volcengine.com/docs/82379/1544106). When upstream
        eventually publishes any of these keys, ``VOLCENGINE_SYNTH_DATA``
        continues to overlay on top — Volcengine remains the source of
        truth for video pricing.

        Does not mutate the input.
        """
        merged: dict[str, Any] = dict(models)
        for key, synth in cls.VOLCENGINE_SYNTH_DATA.items():
            existing = merged.get(key)
            if existing is None:
                merged[key] = dict(synth)
            else:
                merged[key] = {**existing, **synth}
        return merged

    @classmethod
    def apply_byteplus_synth(cls, models: dict[str, Any]) -> dict[str, Any]:
        """
        Inject BytePlus (overseas) Dreamina Seedance video SKUs.

        Upstream BerriAI/litellm/main carries no Seedance keys at all, so all
        eight entries in ``BYTEPLUS_SYNTH_DATA`` are pre-staged from the
        official BytePlus ModelArk pricing page
        (https://docs.byteplus.com/en/docs/ModelArk/1544106). Injected
        wholesale when absent, overlaid when present — BytePlus stays the
        source of truth for the overseas tariff.

        These are independent SKUs, NOT mirrors of ``volcengine/*``: BytePlus
        publishes USD natively at list prices ~6-8% above the CNY-derived
        domestic ones, so no FX conversion and no mirror mapping applies.

        Does not mutate the input.
        """
        merged: dict[str, Any] = dict(models)
        for key, synth in cls.BYTEPLUS_SYNTH_DATA.items():
            existing = merged.get(key)
            merged[key] = dict(synth) if existing is None else {**existing, **synth}
        return merged

    @classmethod
    def apply_newapi_synth(cls, models: dict[str, Any]) -> dict[str, Any]:
        """
        Mirror authoritative <vendor>/<sku> entries onto new-api/<sku>.

        new-api is a routing-layer aggregator; each ``new-api/<sku>`` here
        is a duplicate of some already-populated source entry. This method
        MUST run after every other vendor synth so those sources are
        already in ``models`` (``filter_all_models`` /
        ``get_filter_stats`` enforce the ordering).

        For each whitelisted ``new-api/<sku>``:
          1. Look up the source key in ``NEWAPI_MIRROR_SOURCES``.
          2. Copy the source's raw entry verbatim, then override
             ``litellm_provider = "new-api"`` so downstream picks the
             new-api provider.
          3. If the source is missing, skip — the mirror silently
             disappears, surfacing the gap via the whitelist's
             zero-price / unsupported-provider drop instead of exporting
             stale duplicated data.

        Does not mutate the input.
        """
        merged: dict[str, Any] = dict(models)
        for key, source_key in cls.NEWAPI_MIRROR_SOURCES.items():
            source = merged.get(source_key)
            if source is None:
                continue
            mirrored = dict(source)
            mirrored["litellm_provider"] = "new-api"
            merged[key] = mirrored
        return merged

    @classmethod
    def apply_ecloud_aicc_synth(cls, models: dict[str, Any]) -> dict[str, Any]:
        """
        Mirror authoritative <vendor>/<sku> entries onto ecloud_aicc/<sku>.

        Structurally identical to ``apply_newapi_synth`` — a catalogue-layer
        aggregator mirror. Must run after every other vendor synth so the
        source entries are already populated in ``models``.

        For each whitelisted ``ecloud_aicc/<sku>``:
          1. Look up the source key in ``ECLOUD_AICC_MIRROR_SOURCES``.
          2. Copy the source's raw entry verbatim, then override
             ``litellm_provider = "ecloud_aicc"`` so downstream picks the
             ecloud_aicc provider.
          3. If the source is missing, skip — surfaces the gap via the
             standard downstream drops instead of exporting stale data.

        Does not mutate the input.
        """
        merged: dict[str, Any] = dict(models)
        for key, source_key in cls.ECLOUD_AICC_MIRROR_SOURCES.items():
            source = merged.get(source_key)
            if source is None:
                continue
            mirrored = dict(source)
            mirrored["litellm_provider"] = "ecloud_aicc"
            merged[key] = mirrored
        return merged

    # ── Capability overrides ─────────────────────────────────────────────
    # The ONLY place a synth table may set a supports_* flag on a key that
    # upstream already carries. capability_check.py enforces it: a synth flag
    # on an upstream-present key must differ from upstream AND appear here,
    # with the vendor source that justifies it. See README "Capability flags".
    _SRC_ZAI_EFFORT = (
        "https://docs.z.ai/guides/capabilities/thinking (2026-09-30): reasoning_effort "
        "'is only supported by GLM-5.2 and above', values max / high, and low "
        "'only supported by GLM-5.3 and GLM-5.3-FLASH'. Upstream leaves it undefined."
    )
    _SRC_ZAI_45_THINKING = (
        "https://docs.z.ai/guides/llm/glm-4.5 (2026-09-30) lists Thinking / Deep Thinking; "
        "the z.ai overview maps GLM-4.5-X, -Air and -AirX to that same guide. "
        "Upstream leaves it undefined."
    )
    _SRC_ZAI_45V_THINKING = (
        "https://docs.z.ai/guides/capabilities/thinking (2026-09-30): 'GLM-4.5V use forced "
        "thinking'; overview tags it 'Flexible Reasoning'. Upstream leaves it undefined."
    )
    _SRC_ZAI_45_CACHE = (
        "https://docs.z.ai/guides/llm/glm-4.5 (2026-09-30) lists Context Caching, and "
        "https://docs.z.ai/guides/overview/pricing publishes a cached-input price for every "
        "GLM-4.5-family SKU. Upstream leaves it undefined."
    )
    _SRC_KIMI_K3_CACHE = (
        "https://platform.kimi.ai/docs/pricing/chat-k3 (2026-09-30): 'The Kimi API "
        "automatically caches repeated request prefixes', with a published Cached Input "
        "Price. Upstream leaves it undefined."
    )

    _SRC_GPT_IMAGE_NO_PDF = (
        "https://developers.openai.com/api/docs/models (2026-09-30): every gpt-image model page "
        "(gpt-image-1, -1-mini, -1.5, -2, -2.5-sunburst, -2.5-flare) states 'Input modalities: "
        "text, image', and the image-generation guide never mentions PDF input. Upstream sets "
        "supports_pdf_input=true on four of them; a forwarded true would let PDFs through."
    )
    _SRC_GEMINI_31_FLASH_LITE_IMAGE_MINIMAL = (
        "https://ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-lite-image (2026-09-30): "
        "capability table 'Thinking: Supported (minimal and high)'. Upstream leaves it undefined."
    )

    _SRC_GEMINI_25_FLASH_IMAGE = (
        "https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash-image (2026-09-30): "
        "capability table 'Caching: Not supported'; 'Inputs: Image and Text' (no PDF). "
        "Upstream sets both flags true."
    )
    _SRC_KIMI_K3_EFFORT = (
        "https://platform.kimi.ai/docs/guide/kimi-k3-quickstart (2026-09-30): 'Reasoning "
        "effort supports `low`, `high`, and `max` (default `max`)'. Upstream records the "
        "levels in reasoning_effort_levels but leaves supports_max_reasoning_effort undefined, "
        "so LiteLLM would reject the vendor's own default."
    )

    CAPABILITY_OVERRIDES: dict[tuple[str, str], str] = {
        ("gemini/gemini-2.5-flash-image", "supports_prompt_caching"): _SRC_GEMINI_25_FLASH_IMAGE,
        ("gemini/gemini-2.5-flash-image", "supports_pdf_input"): _SRC_GEMINI_25_FLASH_IMAGE,
        ("moonshot/kimi-k3", "supports_max_reasoning_effort"): _SRC_KIMI_K3_EFFORT,
        **dict.fromkeys(
            [
                (k, "supports_pdf_input")
                for k in ("gpt-image-2", "gpt-image-1.5", "gpt-image-2.5-sunburst", "gpt-image-2.5-flare")
            ],
            _SRC_GPT_IMAGE_NO_PDF,
        ),
        ("gemini/gemini-3.1-flash-lite-image", "supports_minimal_reasoning_effort"): (
            _SRC_GEMINI_31_FLASH_LITE_IMAGE_MINIMAL
        ),
        ("zai/glm-5.3-flash", "supports_max_reasoning_effort"): _SRC_ZAI_EFFORT,
        ("zai/glm-5.3-flash", "supports_low_reasoning_effort"): _SRC_ZAI_EFFORT,
        ("zai/glm-5.3", "supports_max_reasoning_effort"): _SRC_ZAI_EFFORT,
        ("zai/glm-5.3", "supports_low_reasoning_effort"): _SRC_ZAI_EFFORT,
        ("zai/glm-5.2", "supports_max_reasoning_effort"): _SRC_ZAI_EFFORT,
        # dict.fromkeys, not a comprehension: a comprehension body cannot see
        # class-scope names such as _SRC_ZAI_45_THINKING.
        **dict.fromkeys(
            [(k, "supports_reasoning") for k in ("zai/glm-4.5", "zai/glm-4.5-x", "zai/glm-4.5-air", "zai/glm-4.5-airx")],
            _SRC_ZAI_45_THINKING,
        ),
        ("zai/glm-4.5v", "supports_reasoning"): _SRC_ZAI_45V_THINKING,
        **dict.fromkeys(
            [
                (k, "supports_prompt_caching")
                for k in ("zai/glm-4.5", "zai/glm-4.5-x", "zai/glm-4.5-air", "zai/glm-4.5-airx", "zai/glm-4.5v")
            ],
            _SRC_ZAI_45_CACHE,
        ),
        ("moonshot/kimi-k3", "supports_prompt_caching"): _SRC_KIMI_K3_CACHE,
    }

    # ── Capability mirrors ───────────────────────────────────────────────
    # <target key> -> <source key>. apply_capability_mirrors replaces every
    # supports_* flag on the target with the source's, so a model the vendor
    # says is "the same model" cannot drift from it. Targets must not carry
    # supports_* of their own (tests/test_policy.py enforces it).
    CAPABILITY_MIRRORS: dict[str, str] = {
        # bigmodel/* is the domestic gateway for the same GLM models as zai/*.
        **{key: "zai/" + key.split("/", 1)[1] for key in BIGMODEL_SYNTH_DATA},
        # "the same model as Kimi K2.7 Code, but with an output speed of
        # approximately 180 Tokens/s" — platform.kimi.ai chat-k27-code pricing.
        "moonshot/kimi-k2.7-code-highspeed": "moonshot/kimi-k2.7-code",
    }

    # Synth/overlay pipeline, applied in order by filter_all_models and
    # get_filter_stats. Both call sites share this list so the two cannot
    # drift — the stats.passed == len(filter_all_models) invariant depends
    # on them running exactly the same steps.
    SYNTH_PIPELINE: tuple = ()  # populated below the class body

    @classmethod
    def filter_all_models(cls, models: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """
        Filter all models and return a dict of valid models.

        Returns:
            dict mapping model_key to transformed model data
        """
        # Order matters and is now explicit. Mirror/alias steps must run
        # after whatever populates their sources: apply_deepseek_alias after
        # the vendor synths, and the two aggregator mirrors
        # (new-api, ecloud_aicc) last of all. Previously this was a
        # ten-deep nested call whose indentation had drifted out of step
        # with its parentheses; a flat pipeline is the same computation and
        # makes an insertion a one-line change.
        enriched = models
        for step in cls.SYNTH_PIPELINE:
            enriched = step.__func__(cls, enriched)
        filtered: dict[str, dict[str, Any]] = {}

        for model_key, model_data in enriched.items():
            result = cls.filter_model(model_key, model_data)
            if result:
                filtered[model_key] = result

        return filtered

    @classmethod
    def get_filter_stats(cls, models: dict[str, Any]) -> dict[str, Any]:
        """
        Get statistics about the filtering process.

        Mirrors filter_model's pipeline exactly so passed == len(filter_all_models(models)).
        """
        # Order matters and is now explicit. Mirror/alias steps must run
        # after whatever populates their sources: apply_deepseek_alias after
        # the vendor synths, and the two aggregator mirrors
        # (new-api, ecloud_aicc) last of all. Previously this was a
        # ten-deep nested call whose indentation had drifted out of step
        # with its parentheses; a flat pipeline is the same computation and
        # makes an insertion a one-line change.
        enriched = models
        for step in cls.SYNTH_PIPELINE:
            enriched = step.__func__(cls, enriched)
        total = len(enriched)
        passed = 0
        excluded_by_rule: dict[str, int] = {
            "unsupported_provider": 0,
            "unsupported_mode": 0,
            "provider_exclusion": 0,
            "global_exclusion": 0,
            "date_pattern": 0,
            "exact_match": 0,
            "zero_price": 0,
        }

        for model_key, model_data in enriched.items():
            provider = model_data.get("litellm_provider")
            mode = model_data.get("mode")

            if not cls.is_provider_supported(provider):
                excluded_by_rule["unsupported_provider"] += 1
                continue

            if not cls.is_mode_supported(mode):
                excluded_by_rule["unsupported_mode"] += 1
                continue

            excluded, reason = cls.should_exclude_with_reason(model_key, provider)
            if excluded:
                # reason is one of the bucket keys above
                excluded_by_rule[reason] += 1  # type: ignore[index]
                continue

            if cls.should_exclude_due_to_price(model_data):
                excluded_by_rule["zero_price"] += 1
                continue

            passed += 1

        return {
            "total": total,
            "passed": passed,
            "excluded": total - passed,
            "excluded_by_rule": excluded_by_rule,
        }


# Convenience functions for direct import
def should_exclude(model_key: str, provider: str | None = None) -> bool:
    """Check if a model should be excluded."""
    return ModelSyncRules.should_exclude(model_key, provider)


def format_model_name(model_key: str, provider: str) -> str:
    """Format model key to friendly display name."""
    return ModelSyncRules.format_model_name(model_key, provider)


def is_default_available(model_key: str, provider: str, model_type: str = "language") -> bool:
    """Check if a model is default available."""
    return ModelSyncRules.is_default_available(model_key, provider, model_type)


def filter_model(model_key: str, model_data: dict[str, Any]) -> dict[str, Any] | None:
    """Filter and transform a single model."""
    return ModelSyncRules.filter_model(model_key, model_data)


# Populated after the class body because the members are classmethod objects.
# Inside-out order of the former nested expression, with apply_deepseek_alias
# inserted after the vendor synths that could populate its source.
ModelSyncRules.SYNTH_PIPELINE = (
    ModelSyncRules.__dict__["apply_openai_synth"],
    ModelSyncRules.__dict__["apply_moonshot_synth"],
    ModelSyncRules.__dict__["apply_google_synth"],
    ModelSyncRules.__dict__["apply_zai_synth"],
    ModelSyncRules.__dict__["apply_bigmodel_synth"],
    ModelSyncRules.__dict__["apply_deepseek_alias"],
    ModelSyncRules.__dict__["apply_volcengine_synth"],
    ModelSyncRules.__dict__["apply_dashscope_synth"],
    ModelSyncRules.__dict__["apply_byteplus_synth"],
    ModelSyncRules.__dict__["apply_anthropic_synth"],
    ModelSyncRules.__dict__["apply_capability_mirrors"],  # after all vendor synths
    ModelSyncRules.__dict__["apply_newapi_synth"],
    ModelSyncRules.__dict__["apply_ecloud_aicc_synth"],
)


def filter_all_models(models: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Filter all models and return valid ones."""
    return ModelSyncRules.filter_all_models(models)

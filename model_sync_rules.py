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
# together if the policy rate is repegged. Shared by every CNY-quoted
# vendor tariff in this file (Volcengine Seedance, DeepSeek).
_CNY_USD_FX_RATE = 7.0


def _cny_per_m_to_usd_per_token(cny_per_m: float, sig: int = 4) -> float:
    """Convert CNY per million tokens → USD per token, rounded to ``sig`` sig figs.

    Vendors billing in RMB (Volcengine Seedance, DeepSeek) quote CNY/M. The
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
        # Pre-staged: announced on docs.z.ai but missing from LiteLLM source
        "zai/glm-5.2",
        "zai/glm-5.3",
        "zai/glm-5.3-flash",
        "zai/glm-5.1",
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

    # Authoritative z.ai data overlay. Source: docs.z.ai/guides/overview/overview
    # + docs.z.ai/guides/overview/pricing (snapshot taken 2026-06-13).
    #
    # Two roles:
    #   1. Inject pre-staged SKUs absent from LiteLLM upstream.
    #   2. Overlay/correct fields when upstream disagrees with z.ai
    #      (e.g. zai/glm-4.5v context: upstream 128K vs z.ai 64K — z.ai wins).
    #
    # Once LiteLLM publishes a pre-staged SKU upstream, the entry continues
    # to overlay any conflicting fields (z.ai remains the source of truth).
    ZAI_SYNTH_DATA: dict[str, dict[str, Any]] = {
        # ── Pre-staged SKUs (not yet on LiteLLM) ──────────────────────────
        "zai/glm-5.2": {
            # Long-horizon flagship: bigmodel.cn advertises "真正可用的 1M 上下文"
            # (genuinely usable 1M context). Priced identically to GLM-5.1 on
            # z.ai international (input $1.4 / output $4.4 / cached $0.26 per M).
            "litellm_provider": "zai",
            "mode": "chat",
            "max_input_tokens": 1000000,
            "max_output_tokens": 128000,
            "input_cost_per_token": 1.4e-06,
            "output_cost_per_token": 4.4e-06,
            "cache_read_input_token_cost": 0.26e-06,
            "supports_function_calling": True,
            "supports_vision": False,
            "supports_json_mode": False,
        },
        "zai/glm-5.3": {
            # Prices CONFIRMED against docs.z.ai/guides/overview/pricing
            # (2026-08-26): input $1.4 / cached $0.26 / output $4.4 per M,
            # 1M ctx. These were pre-staged in v1.16.10 by mirroring GLM-5.2
            # before z.ai published GLM-5.3 rates; the published rates turned
            # out identical, so the numbers are unchanged — only their status
            # (guess -> verified) is.
            "litellm_provider": "zai",
            "mode": "chat",
            "max_input_tokens": 1000000,
            "max_output_tokens": 128000,
            "input_cost_per_token": 1.4e-06,
            "output_cost_per_token": 4.4e-06,
            "cache_read_input_token_cost": 0.26e-06,
            "supports_function_calling": True,
            "supports_vision": False,
            "supports_json_mode": False,
        },
        "zai/glm-5.3-flash": {
            # GLM-5.3-Flash — the first NATIVE MULTIMODAL model in the GLM-5
            # series (320B total / 18B active), so supports_vision is True
            # even though the key has no "v" infix and therefore does not
            # match _GLM_VISION_KEY. Text parameters are "consistent with
            # GLM-5.3, with support for a 1M-token context window" per
            # docs.z.ai/guides/vlm/glm-5.3-flash (2026-08-26).
            #
            # PROMOTIONAL PRICE, not list. docs.z.ai/guides/overview/pricing
            # states: "GLM-5.3-Flash is available at a 50% discount
            # (strikethrough prices are list prices). The promotion ends at
            # 24:00 on September 9, 2026 (UTC+8, Singapore time)."
            #   list:      input $0.15 / cached $0.03 / output $0.50 per M
            #   effective: input $0.075 / cached $0.015 / output $0.25 per M
            # The discount is UNCONDITIONAL — every caller gets it — so the
            # effective rate is what customers are actually billed today.
            # Same treatment as ANTHROPIC_SYNTH_DATA's introductory overlays,
            # and deliberately unlike BYTEPLUS_SYNTH_DATA, which stores list
            # because those campaigns are gated on account balance / savings
            # plan and so are not universal.
            #
            # >>> REVERT TO LIST PRICE ON 2026-09-10 <<<
            # input 1.5e-07, cache_read 3e-08, output 5e-07.
            "litellm_provider": "zai",
            "mode": "chat",
            "max_input_tokens": 1000000,
            "max_output_tokens": 128000,
            "input_cost_per_token": 0.075e-06,
            "output_cost_per_token": 0.25e-06,
            "cache_read_input_token_cost": 0.015e-06,
            "supports_function_calling": True,
            "supports_vision": True,
            "supports_json_mode": False,
        },
        "zai/glm-5.1": {
            "litellm_provider": "zai",
            "mode": "chat",
            "max_input_tokens": 200000,
            "max_output_tokens": 128000,
            "input_cost_per_token": 1.4e-06,
            "output_cost_per_token": 4.4e-06,
            "cache_read_input_token_cost": 0.26e-06,
            "supports_function_calling": True,
            "supports_vision": False,
            "supports_json_mode": False,
        },
        "zai/glm-5-turbo": {
            "litellm_provider": "zai",
            "mode": "chat",
            "max_input_tokens": 200000,
            "max_output_tokens": 128000,
            "input_cost_per_token": 1.2e-06,
            "output_cost_per_token": 4.0e-06,
            "cache_read_input_token_cost": 0.24e-06,
            "supports_function_calling": True,
            "supports_vision": False,
            "supports_json_mode": False,
        },
        "zai/glm-4.7-flashx": {
            "litellm_provider": "zai",
            "mode": "chat",
            "max_input_tokens": 200000,
            "max_output_tokens": 128000,
            "input_cost_per_token": 0.07e-06,
            "output_cost_per_token": 0.4e-06,
            "cache_read_input_token_cost": 0.01e-06,
            "supports_function_calling": True,
            "supports_vision": False,
            "supports_json_mode": False,
        },
        "zai/glm-5v-turbo": {
            "litellm_provider": "zai",
            "mode": "chat",
            "max_input_tokens": 200000,
            "max_output_tokens": 128000,
            "input_cost_per_token": 1.2e-06,
            "output_cost_per_token": 4.0e-06,
            "cache_read_input_token_cost": 0.24e-06,
            "supports_function_calling": True,
            "supports_vision": True,
            "supports_json_mode": False,
        },
        "zai/glm-4.6v": {
            "litellm_provider": "zai",
            "mode": "chat",
            "max_input_tokens": 128000,
            "max_output_tokens": 32000,
            "input_cost_per_token": 0.3e-06,
            "output_cost_per_token": 0.9e-06,
            "cache_read_input_token_cost": 0.05e-06,
            "supports_function_calling": True,
            "supports_vision": True,
            "supports_json_mode": False,
        },
        "zai/glm-4.6v-flashx": {
            "litellm_provider": "zai",
            "mode": "chat",
            "max_input_tokens": 128000,
            "max_output_tokens": 32000,
            "input_cost_per_token": 0.04e-06,
            "output_cost_per_token": 0.4e-06,
            "cache_read_input_token_cost": 0.004e-06,
            "supports_function_calling": True,
            "supports_vision": True,
            "supports_json_mode": False,
        },
        "zai/glm-ocr": {
            "litellm_provider": "zai",
            "mode": "chat",
            "max_input_tokens": None,
            "max_output_tokens": None,
            "input_cost_per_token": 0.03e-06,
            "output_cost_per_token": 0.03e-06,
            "supports_function_calling": False,
            "supports_vision": True,
            "supports_json_mode": False,
        },
        # ── Overlays for existing LiteLLM SKUs ────────────────────────────
        # Strategy: only fill what upstream lacks or disagrees with z.ai.
        # Upstream already has correct cache pricing for glm-5/4.7/4.6,
        # so they're not duplicated here. The 4.5 family + 4.5v are.
        "zai/glm-4.5v": {
            # z.ai/overview lists context 64K; upstream says 128K. z.ai wins.
            "max_input_tokens": 64000,
            "cache_read_input_token_cost": 0.11e-06,
        },
        "zai/glm-4.5": {
            "cache_read_input_token_cost": 0.11e-06,
        },
        "zai/glm-4.5-x": {
            "cache_read_input_token_cost": 0.45e-06,
        },
        "zai/glm-4.5-air": {
            "cache_read_input_token_cost": 0.03e-06,
        },
        "zai/glm-4.5-airx": {
            "cache_read_input_token_cost": 0.22e-06,
        },
        # zai/glm-4-32b-0414-128k and zai/glm-ocr: no cache pricing on
        # z.ai/pricing (shown as "-" / "\") — intentionally not added.
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

    # Bigmodel SKU metadata. Pricing is *not* stored here — it is mirrored
    # from the sibling zai/<sku> at synth time (see apply_bigmodel_synth).
    # Each entry only carries non-price fields: context window, capabilities.
    #
    # Source for context/capabilities: docs.z.ai/guides/overview/overview
    # (same models, so the metadata matches the zai/* entries by design).
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
            "supports_function_calling": True,
            "supports_vision": False,
            "supports_json_mode": False,
        },
        # Pre-staged mirror of GLM-5.2 (price mirrored from zai/glm-5.3 sibling).
        "bigmodel/glm-5.3": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 1000000,
            "max_output_tokens": 128000,
            "supports_function_calling": True,
            "supports_vision": False,
            "supports_json_mode": False,
        },
        # Domestic mirror of zai/glm-5.3-flash. Prices are NOT written here —
        # apply_bigmodel_synth copies them from the zai sibling, so the 50%
        # promotional rate (and its 2026-09-10 revert) is maintained in one
        # place. supports_vision must still be stated: it is metadata, not a
        # mirrored price field, and glm-5.3-flash is natively multimodal
        # despite having no "v" infix in the key.
        "bigmodel/glm-5.3-flash": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 1000000,
            "max_output_tokens": 128000,
            "supports_function_calling": True,
            "supports_vision": True,
            "supports_json_mode": False,
        },
        "bigmodel/glm-5": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 200000,
            "max_output_tokens": 128000,
            "supports_function_calling": True,
            "supports_vision": False,
            "supports_json_mode": False,
        },
        "bigmodel/glm-4.7": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 200000,
            "max_output_tokens": 128000,
            "supports_function_calling": True,
            "supports_vision": False,
            "supports_json_mode": False,
        },
        "bigmodel/glm-4.5-air": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 128000,
            "max_output_tokens": 32000,
            "supports_function_calling": True,
            "supports_vision": False,
            "supports_json_mode": False,
        },
        "bigmodel/glm-5.1": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 200000,
            "max_output_tokens": 128000,
            "supports_function_calling": True,
            "supports_vision": False,
            "supports_json_mode": False,
        },
        "bigmodel/glm-5-turbo": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 200000,
            "max_output_tokens": 128000,
            "supports_function_calling": True,
            "supports_vision": False,
            "supports_json_mode": False,
        },
        "bigmodel/glm-4.7-flashx": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 200000,
            "max_output_tokens": 128000,
            "supports_function_calling": True,
            "supports_vision": False,
            "supports_json_mode": False,
        },
        # Vision models
        "bigmodel/glm-5v-turbo": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 200000,
            "max_output_tokens": 128000,
            "supports_function_calling": True,
            "supports_vision": True,
            "supports_json_mode": False,
        },
        "bigmodel/glm-4.6v": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 128000,
            "max_output_tokens": 32000,
            "supports_function_calling": True,
            "supports_vision": True,
            "supports_json_mode": False,
        },
        "bigmodel/glm-4.6v-flashx": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 128000,
            "max_output_tokens": 32000,
            "supports_function_calling": True,
            "supports_vision": True,
            "supports_json_mode": False,
        },
        "bigmodel/glm-4.5v": {
            "litellm_provider": "bigmodel",
            "mode": "chat",
            "max_input_tokens": 64000,
            "max_output_tokens": 32000,
            "supports_function_calling": True,
            "supports_vision": True,
            "supports_json_mode": False,
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
    # Reverse-whitelist for deepseek/* SKUs. Only the V4 series is active
    # on api-docs.deepseek.com/quick_start/pricing (snapshot 2026-06-30).
    # Excluded for being deprecated / no longer listed officially:
    #   - deepseek-chat, deepseek-reasoner: scheduled deprecation 2026-07-24
    #     (currently aliases of deepseek-v4-flash thinking/non-thinking modes)
    #   - deepseek-v3, deepseek-v3.2, deepseek-r1, deepseek-coder:
    #     superseded by V4, not on official pricing page
    DEEPSEEK_ALLOWED_KEYS = frozenset({
        "deepseek/deepseek-v4-flash",
        "deepseek/deepseek-v4-pro",
    })

    # Moonshot (Kimi) whitelist — reverse-whitelist for moonshot/* keys.
    # Pre-staged: not on the LiteLLM source yet; injected via MOONSHOT_SYNTH_DATA.
    MOONSHOT_ALLOWED_KEYS = frozenset({
        "moonshot/kimi-k3",
        "moonshot/kimi-k2.7-code",
        "moonshot/kimi-k2.7-code-highspeed",
    })

    # Moonshot / Kimi pre-staged entries — models on platform.kimi.ai not yet
    # carried by BerriAI upstream. Complete litellm-style records, injected
    # wholesale by apply_moonshot_synth. Prices from platform.kimi.ai/docs.
    MOONSHOT_SYNTH_DATA: dict[str, dict[str, Any]] = {
        # Kimi K3 — $3 in / $15 out per M, cache-hit $0.30; 1M context.
        # Source https://platform.kimi.ai/docs/pricing/chat-k3.
        "moonshot/kimi-k3": {
            "litellm_provider": "moonshot",
            "mode": "chat",
            "input_cost_per_token": 3e-06,
            "output_cost_per_token": 1.5e-05,
            "cache_read_input_token_cost": 3e-07,
            "input_cost_per_token_cache_hit": 3e-07,
            "max_input_tokens": 1048576,
            "max_output_tokens": 1048576,
            "max_tokens": 1048576,
            "source": "https://platform.kimi.ai/docs/pricing/chat-k3",
            "supported_endpoints": ["/v1/chat/completions"],
            "supports_reasoning": True,
            "supports_prompt_caching": True,
            "supports_response_schema": True,
            "supports_tool_choice": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "supports_system_messages": True,
            "supports_native_streaming": True,
            "supports_parallel_function_calling": True,
        },
        # Kimi K2.7 Code — coding model, 256K (262,144) context; text/image/
        # video input, thinking, ToolCalls, JSON Mode. $0.95 in / $4.00 out
        # per M, cache-hit $0.19. Source chat-k2.7-code pricing page.
        "moonshot/kimi-k2.7-code": {
            "litellm_provider": "moonshot",
            "mode": "chat",
            "input_cost_per_token": 9.5e-07,
            "output_cost_per_token": 4e-06,
            "cache_read_input_token_cost": 1.9e-07,
            "input_cost_per_token_cache_hit": 1.9e-07,
            "max_input_tokens": 262144,
            "max_output_tokens": 262144,
            "max_tokens": 262144,
            "source": "https://platform.kimi.ai/docs/pricing/chat-k2.7-code",
            "supported_endpoints": ["/v1/chat/completions"],
            "supports_reasoning": True,
            "supports_prompt_caching": True,
            "supports_response_schema": True,
            "supports_tool_choice": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "supports_system_messages": True,
            "supports_native_streaming": True,
            "supports_parallel_function_calling": True,
        },
        # Kimi K2.7 Code HighSpeed — same model, higher output speed. $1.90 in
        # / $8.00 out per M, cache-hit $0.38; 256K context.
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
            "supports_reasoning": True,
            "supports_prompt_caching": True,
            "supports_response_schema": True,
            "supports_tool_choice": True,
            "supports_vision": True,
            "supports_function_calling": True,
            "supports_system_messages": True,
            "supports_native_streaming": True,
            "supports_parallel_function_calling": True,
        },
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

    # DeepSeek overlays. Source: api-docs.deepseek.com/quick_start/pricing
    # (snapshot 2026-08-20). LiteLLM upstream carries the correct context
    # (1M input) but trails on two points: max_output_tokens is stuck at
    # 8192 (official 384K) and its prices predate the 2026-08 tariff.
    #
    # Currency: the official page quotes CNY/M. Stored as USD/token via the
    # shared policy FX rate (see _cny_per_m_to_usd_per_token) so the billing
    # manager needs no runtime FX lookup — same treatment as Seedance.
    #
    # Peak vs off-peak: DeepSeek halves every rate outside Beijing-time
    # 09:00–12:00 / 14:00–18:00. LiteLLM has no time-of-day price axis, so
    # we carry the PEAK tariff (the ceiling — never under-bills). Off-peak
    # is exactly 0.5x if a discount axis is ever added.
    #
    #   Peak CNY/M          flash        pro
    #   cache-miss input      3.0        9.0
    #   cache-hit input       0.10       0.30
    #   output                9.0       27.0
    #
    # input_cost_per_token_cache_hit is DeepSeek's own upstream field name;
    # cache_read_input_token_cost is the litellm-generic one. Both carry the
    # same number, mirroring the upstream entry shape. Cache writes are free
    # (cache_creation_input_token_cost stays 0.0 from upstream).
    DEEPSEEK_SYNTH_DATA: dict[str, dict[str, Any]] = {
        "deepseek/deepseek-v4-flash": {
            "max_output_tokens": 384000,
            "input_cost_per_token": _cny_per_m_to_usd_per_token(3.0),
            "output_cost_per_token": _cny_per_m_to_usd_per_token(9.0),
            "cache_read_input_token_cost": _cny_per_m_to_usd_per_token(0.10),
            "input_cost_per_token_cache_hit": _cny_per_m_to_usd_per_token(0.10),
        },
        "deepseek/deepseek-v4-pro": {
            "max_output_tokens": 384000,
            "input_cost_per_token": _cny_per_m_to_usd_per_token(9.0),
            "output_cost_per_token": _cny_per_m_to_usd_per_token(27.0),
            "cache_read_input_token_cost": _cny_per_m_to_usd_per_token(0.30),
            "input_cost_per_token_cache_hit": _cny_per_m_to_usd_per_token(0.30),
        },
    }

    # ── Anthropic overlays ────────────────────────────────────────────────
    # Source: claude.com/pricing (snapshot 2026-07-01).
    #
    # LiteLLM upstream tracks Anthropic's post-introductory tariffs. When
    # Anthropic runs a time-boxed introductory price we overlay the
    # currently-effective numbers here so saas-models-source reflects what
    # customers actually get billed today. Remove each entry once its
    # window closes (upstream then flows through unchanged).
    #
    # Active window(s):
    #   claude-sonnet-5 — introductory through 2026-08-31.
    #     input:  $2/M   (standard $3/M kicks in 2026-09-01)
    #     output: $10/M  (standard $15/M)
    #     cache_read (0.1×): $0.20/M (standard $0.30/M)
    #     cache_creation (1.25×, 5m):  $2.50/M (standard $3.75/M)
    # Two entry kinds live here (see apply_anthropic_synth):
    #   • Partial overlay — patches an entry already carried by upstream
    #     (e.g. claude-sonnet-5 introductory pricing). Overlaid, never injected.
    #   • Complete pre-staged entry (carries `litellm_provider`) — a model not
    #     yet on BerriAI upstream (e.g. claude-opus-5, current flagship per
    #     platform.claude.com). Injected wholesale when absent upstream.
    ANTHROPIC_SYNTH_DATA: dict[str, dict[str, Any]] = {
        "claude-sonnet-5": {
            "input_cost_per_token": 2e-06,
            "output_cost_per_token": 1e-05,
            "cache_read_input_token_cost": 2e-07,
            "cache_creation_input_token_cost": 2.5e-06,
        },
        # Claude Opus 5 — current flagship ($5/$25 per M, 1M ctx, 128K out),
        # GA 2026-06-09; source platform.claude.com/docs models overview +
        # pricing. Same request surface / capabilities as Opus 4.8.
        "claude-opus-5": {
            "litellm_provider": "anthropic",
            "mode": "chat",
            "input_cost_per_token": 5e-06,
            "output_cost_per_token": 2.5e-05,
            "cache_read_input_token_cost": 5e-07,
            "cache_creation_input_token_cost": 6.25e-06,
            "cache_creation_input_token_cost_above_1hr": 1e-05,
            "max_input_tokens": 1000000,
            "max_output_tokens": 128000,
            "max_tokens": 128000,
            "search_context_cost_per_query": {
                "search_context_size_high": 0.01,
                "search_context_size_low": 0.01,
                "search_context_size_medium": 0.01,
            },
            "supports_adaptive_thinking": True,
            "supports_assistant_prefill": False,
            "supports_computer_use": True,
            "supports_function_calling": True,
            "supports_pdf_input": True,
            "supports_prompt_caching": True,
            "supports_reasoning": True,
            "supports_response_schema": True,
            "supports_sampling_params": False,
            "supports_tool_choice": True,
            "supports_vision": True,
            "supports_xhigh_reasoning_effort": True,
            "supports_max_reasoning_effort": True,
            "supports_output_config": True,
        },
        # Claude Mythos 5 — Project Glasswing limited-availability sibling of
        # Fable 5 (defensive-cyber). Same specs, pricing, and API surface as
        # Fable 5: $10 / $50 per M, cache-read $1, 5m write $12.50, 1h $20,
        # 1M ctx, 128K out. Source platform.claude.com models overview +
        # pricing. Not on BerriAI upstream — injected wholesale.
        "claude-mythos-5": {
            "litellm_provider": "anthropic",
            "mode": "chat",
            "input_cost_per_token": 1e-05,
            "output_cost_per_token": 5e-05,
            "cache_read_input_token_cost": 1e-06,
            "cache_creation_input_token_cost": 1.25e-05,
            "cache_creation_input_token_cost_above_1hr": 2e-05,
            "max_input_tokens": 1000000,
            "max_output_tokens": 128000,
            "max_tokens": 128000,
            "search_context_cost_per_query": {
                "search_context_size_high": 0.01,
                "search_context_size_low": 0.01,
                "search_context_size_medium": 0.01,
            },
            "supports_adaptive_thinking": True,
            "supports_assistant_prefill": False,
            "supports_computer_use": True,
            "supports_function_calling": True,
            "supports_pdf_input": True,
            "supports_prompt_caching": True,
            "supports_reasoning": True,
            "supports_response_schema": True,
            "supports_sampling_params": False,
            "supports_tool_choice": True,
            "supports_vision": True,
            "supports_xhigh_reasoning_effort": True,
            "supports_max_reasoning_effort": True,
            "provider_specific_entry": {"us": 1.1},
            "supports_output_config": True,
        },
    }

    # Google / Gemini pre-staged entries — models newly published on
    # ai.google.dev but not yet on BerriAI upstream. Each is a complete
    # litellm-style entry, injected wholesale by apply_google_synth. Prices
    # from ai.google.dev/gemini-api/docs/pricing; context windows mirror the
    # same-generation sibling (the pricing page omits them).
    GOOGLE_SYNTH_DATA: dict[str, dict[str, Any]] = {
        # Gemini 3.6 Flash — $1.50 in / $7.50 out per M, cache $0.15.
        "gemini/gemini-3.6-flash": {
            "litellm_provider": "gemini",
            "mode": "chat",
            "input_cost_per_token": 1.5e-06,
            "output_cost_per_token": 7.5e-06,
            "output_cost_per_reasoning_token": 7.5e-06,
            "cache_read_input_token_cost": 1.5e-07,
            "max_input_tokens": 1048576,
            "max_output_tokens": 65535,
            "max_tokens": 65535,
            "source": "https://ai.google.dev/gemini-api/docs/pricing",
            "supported_endpoints": ["/v1/chat/completions", "/v1/completions", "/v1/batch"],
            "supported_modalities": ["text", "image", "audio", "video"],
            "supported_output_modalities": ["text"],
            "supports_audio_input": True,
            "supports_audio_output": False,
            "supports_function_calling": True,
            "supports_parallel_function_calling": True,
            "supports_pdf_input": True,
            "supports_prompt_caching": True,
            "supports_reasoning": True,
            "supports_response_schema": True,
            "supports_system_messages": True,
            "supports_tool_choice": True,
            "supports_url_context": True,
            "supports_video_input": True,
            "supports_vision": True,
            "supports_web_search": True,
            "supports_native_streaming": True,
        },
        # Gemini 3.5 Flash-Lite — $0.30 in / $2.50 out per M, cache $0.03.
        "gemini/gemini-3.5-flash-lite": {
            "litellm_provider": "gemini",
            "mode": "chat",
            "input_cost_per_token": 3e-07,
            "output_cost_per_token": 2.5e-06,
            "output_cost_per_reasoning_token": 2.5e-06,
            "cache_read_input_token_cost": 3e-08,
            "max_input_tokens": 1048576,
            "max_output_tokens": 65536,
            "max_tokens": 65536,
            "source": "https://ai.google.dev/gemini-api/docs/pricing",
            "supported_endpoints": ["/v1/chat/completions", "/v1/completions", "/v1/batch"],
            "supported_modalities": ["text", "image", "audio", "video"],
            "supported_output_modalities": ["text"],
            "supports_audio_input": True,
            "supports_audio_output": False,
            "supports_function_calling": True,
            "supports_parallel_function_calling": True,
            "supports_pdf_input": True,
            "supports_prompt_caching": True,
            "supports_reasoning": True,
            "supports_response_schema": True,
            "supports_system_messages": True,
            "supports_tool_choice": True,
            "supports_url_context": True,
            "supports_video_input": True,
            "supports_vision": True,
            "supports_web_search": True,
            "supports_native_streaming": True,
        },
        # Gemini 3.1 Flash-Lite Image (Nano Banana 2 Lite) — image model:
        # $0.25 in / $1.50 out text per M; images $30/M tokens ($0.0336/image).
        "gemini/gemini-3.1-flash-lite-image": {
            "litellm_provider": "gemini",
            "mode": "image_generation",
            "input_cost_per_token": 2.5e-07,
            "output_cost_per_token": 1.5e-06,
            "output_cost_per_image_token": 3e-05,
            "output_cost_per_image": 0.0336,
            "max_input_tokens": 65536,
            "max_output_tokens": 32768,
            "max_tokens": 32768,
            "source": "https://ai.google.dev/gemini-api/docs/pricing",
            "supported_endpoints": ["/v1/chat/completions", "/v1/completions", "/v1/batch"],
            "supported_modalities": ["text", "image"],
            "supported_output_modalities": ["text", "image"],
            "supports_function_calling": False,
            "supports_prompt_caching": True,
            "supports_response_schema": True,
            "supports_system_messages": True,
            "supports_vision": True,
            "supports_web_search": True,
        },
    }

    # ── OpenAI overlays ───────────────────────────────────────────────────
    # Source: developers.openai.com/api/docs/pricing (Standard / Batch / Flex /
    # Priority tabs, snapshot 2026-07-15), cross-checked field-by-field against
    # the pinned GhishaDev/litellm-internal ship/v1.89.0 backup.
    #
    # LiteLLM upstream (BerriAI/main) trailed OpenAI's July 2026 GPT-5 refresh,
    # so we overlay the officially-published numbers here. The overlay is purely
    # ADDITIVE (merged on top of upstream via {**existing, **synth}); it never
    # removes richer upstream fields the project already carries. Corrections:
    #   • gpt-5.5 priority tier — $12.50 in / $1.25 cached / $75 out per M
    #     (upstream had the old $10 / $1 / $60).
    #   • gpt-5.4-{mini,nano} — short-context only: max_input 272K (not 1.05M),
    #     plus the batch cached-read rate absent upstream.
    #   • gpt-5.6 family — the flex long-context (>272K) tier (4 fields).
    #   • service-tier / regional-uplift billing flags missing upstream.
    # NOTE: gpt-5.4 cached-read flex stays 1.3e-07 ($0.13) — that is OpenAI's
    # own published figure (Flex/Batch tabs), NOT a rounding artefact.
    # Remove an entry once BerriAI upstream carries the same values.
    OPENAI_SYNTH_DATA: dict[str, dict[str, Any]] = {
        "gpt-5": {
            "regional_processing_uplift_multiplier_eu": 1.1,
            "regional_processing_uplift_multiplier_us": 1.1,
            "supports_service_tier": True,
        },
        "gpt-5-mini": {
            "regional_processing_uplift_multiplier_eu": 1.1,
            "regional_processing_uplift_multiplier_us": 1.1,
            "supports_service_tier": True,
        },
        "gpt-5-nano": {
            "regional_processing_uplift_multiplier_eu": 1.1,
            "regional_processing_uplift_multiplier_us": 1.1,
        },
        "gpt-5.1": {
            "supports_service_tier": True,
        },
        "gpt-5.2": {
            "supports_service_tier": True,
        },
        "gpt-5.4": {
            "supports_service_tier": True,
        },
        "gpt-5.4-mini": {
            "cache_read_input_token_cost_batches": 3.75e-08,
            "max_input_tokens": 272000,
            "supports_service_tier": True,
        },
        "gpt-5.4-nano": {
            "cache_read_input_token_cost_batches": 1e-08,
            "max_input_tokens": 272000,
            "supports_service_tier": True,
        },
        "gpt-5.5": {
            "cache_read_input_token_cost_priority": 1.25e-06,
            "input_cost_per_token_priority": 1.25e-05,
            "output_cost_per_token_priority": 7.5e-05,
            "supports_service_tier": True,
        },
        "gpt-5.6": {
            # max_input_tokens: upstream still reports 922000 (that is
            # GPT-5.5's figure); developers.openai.com states 1,050,000.
            # Verified 2026-08-21 and re-checked 2026-08-26.
            #
            # The four *_above_272k_tokens_flex overlays that used to live
            # here were REMOVED on 2026-08-26: upstream now carries those
            # fields itself, and OpenAI cut the 5.6 Sol tariff. Keeping our
            # (pre-cut) values would have pinned flex long-context output at
            # $22.50/M against the real $15/M. Do not re-add them without
            # re-checking whether upstream still supplies them.
            "max_input_tokens": 1050000,
        },
        "gpt-5.6-sol": {
            # max_input_tokens: upstream regressed to 922000 (2026-08);
            # developers.openai.com/api/docs/models/gpt-5.6-sol states
            # 1,050,000. Verified 2026-08-21 on all four family pages.
            "max_input_tokens": 1050000,
        },
        "gpt-5.6-terra": {
            # max_input_tokens: upstream still reports 922000 (that is
            # GPT-5.5's figure); developers.openai.com states 1,050,000.
            # Verified 2026-08-21 and re-checked 2026-08-26.
            #
            # The four *_above_272k_tokens_flex overlays that used to live
            # here were REMOVED on 2026-08-26: upstream now carries those
            # fields itself, and OpenAI cut the 5.6 Sol tariff. Keeping our
            # (pre-cut) values would have pinned flex long-context output at
            # $22.50/M against the real $15/M. Do not re-add them without
            # re-checking whether upstream still supplies them.
            "max_input_tokens": 1050000,
        },
        "gpt-5.6-luna": {
            # max_input_tokens: upstream still reports 922000 (that is
            # GPT-5.5's figure); developers.openai.com states 1,050,000.
            # Verified 2026-08-21 and re-checked 2026-08-26.
            #
            # The four *_above_272k_tokens_flex overlays that used to live
            # here were REMOVED on 2026-08-26: upstream now carries those
            # fields itself, and OpenAI cut the 5.6 Sol tariff. Keeping our
            # (pre-cut) values would have pinned flex long-context output at
            # $22.50/M against the real $15/M. Do not re-add them without
            # re-checking whether upstream still supplies them.
            "max_input_tokens": 1050000,
        },
        # gpt-4o-mini-tts text input — OpenAI official is $0.60 / 1M tokens
        # (developers.openai.com); upstream carried the Azure/aggregator
        # $2.50 rate. Audio output ($12/1M) is already correct upstream.
        "gpt-4o-mini-tts": {
            "input_cost_per_token": 6e-07,
        },
        # Standalone TTS models — pre-staged (character-billed). Source
        # openai.com: tts-1 $15 / 1M characters, tts-1-hd $30 / 1M characters.
        "tts-1": {
            "litellm_provider": "openai",
            "mode": "audio_speech",
            "output_cost_per_character": 1.5e-05,
            "supported_endpoints": ["/v1/audio/speech"],
            "supported_modalities": ["text"],
            "supported_output_modalities": ["audio"],
        },
        "tts-1-hd": {
            "litellm_provider": "openai",
            "mode": "audio_speech",
            "output_cost_per_character": 3e-05,
            "supported_endpoints": ["/v1/audio/speech"],
            "supported_modalities": ["text"],
            "supported_output_modalities": ["audio"],
        },
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
        # OpenAI audio-transcription variants not in the approved whitelist.
        # (gpt-4o-mini-transcribe is the sanctioned SKU; the full-fat and
        # diarize variants are intentionally kept out — narrow product scope,
        # not a bug.)
        "gpt-4o-transcribe",
        "gpt-4o-transcribe-diarize",
        # Same policy, applied to the 2026-08 rename generation: OpenAI
        # dropped the "4o" infix, so these arrive as bare keys that no
        # existing pattern catches. Full-fat ASR — excluded for the same
        # narrow-scope reason as gpt-4o-transcribe, not because upstream
        # data is wrong. Promote to the whitelist if the product scope
        # widens to full-fat transcription.
        "gpt-transcribe",
        "gpt-live-transcribe",
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
        # Note: gpt-audio-* and gpt-realtime-* are excluded via EXCLUDE_PATTERNS
        # Gemini non-standard models
        "gemini/gemini-gemma-2-27b-it",
        "gemini/gemini-gemma-2-9b-it",
        "gemini/gemini-pro",
        "gemini/gemini-pro-vision",
        # Gemini special-purpose models
        "gemini/gemini-3.1-pro-preview-customtools",
        "gemini/gemini-3.1-flash-live-preview",
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
    # NOTE: INCLUDE_PATTERNS shortcuts every rule *after* PROVIDER_EXCLUSION_RULES
    # (date_pattern, EXCLUDE_PATTERNS, EXCLUDE_MODEL_KEYS). It does NOT override
    # provider-level exclusions — those must be narrowed at their own site.
    INCLUDE_PATTERNS: list[re.Pattern] = [
        re.compile(r"^gpt-.*-chat-latest$", re.IGNORECASE),  # Allow gpt-*-chat-latest despite -latest rule
        re.compile(r"^gemini/gemini-[3-9].*-preview$", re.IGNORECASE),  # Allow Gemini 3.x+ preview models
        # OpenAI audio / realtime allow-list (exact match). Needed to
        # bypass -preview- / date_pattern / ^gpt-realtime global excludes
        # on the dated realtime preview and gpt-realtime bare key.
        re.compile(r"^gpt-4o$", re.IGNORECASE),
        re.compile(r"^gpt-4o-mini$", re.IGNORECASE),
        re.compile(r"^gpt-realtime$", re.IGNORECASE),
        re.compile(r"^gpt-4o-realtime-preview-2024-12-17$", re.IGNORECASE),
        re.compile(r"^gpt-4o-mini-transcribe$", re.IGNORECASE),
        re.compile(r"^gpt-4o-mini-tts$", re.IGNORECASE),
        re.compile(r"^whisper-1$", re.IGNORECASE),
        re.compile(r"^tts-1$", re.IGNORECASE),
        re.compile(r"^tts-1-hd$", re.IGNORECASE),
    ]

    # Data source URL
    DATA_SOURCE_URL = (
        "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
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
        "image_generation": (
            "input_cost_per_token",
            "input_cost_per_image_token",
            "input_cost_per_image",
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
        "realtime": (
            "input_cost_per_token",
            "output_cost_per_token",
            "input_cost_per_audio_token",
            "output_cost_per_audio_token",
            "input_cost_per_image",
        ),
    }

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

        # Volcengine / new-api / ecloud_aicc Seedance video:
        #   volcengine/doubao-seedance-2-0-260128       → Doubao-Seedance 2.0
        #   volcengine/doubao-seedance-2-0-fast-260128  → Doubao-Seedance 2.0 Fast
        #   volcengine/doubao-seedance-2-0-mini-260615  → Doubao-Seedance 2.0 Mini
        #   volcengine/doubao-seedance-2-0              → Doubao-Seedance 2.0
        #   new-api/doubao-seedance-2-0-fast            → Doubao-Seedance 2.0 Fast
        #   ecloud_aicc/doubao-seedance-2-0-mini        → Doubao-Seedance 2.0 Mini
        # Dated suffixes (-260128, -260615) are the official Volcengine
        # model-version stamps (YYMMDD); strip them for the friendly name.
        # new-api and ecloud_aicc are catalogue-layer mirror providers that
        # reuse Volcengine's naming; the branch covers all three prefixes.
        if (
            provider in ("volcengine", "new-api", "ecloud_aicc")
            or key.startswith(("volcengine/", "new-api/", "ecloud_aicc/"))
        ):
            suffix = re.sub(
                r"^(?:volcengine|new-api|ecloud_aicc)/doubao-seedance-",
                "",
                key,
                flags=re.IGNORECASE,
            )
            suffix = re.sub(r"-\d{6}$", "", suffix)  # drop -YYMMDD
            parts = suffix.split("-")
            version = (
                f"{parts[0]}.{parts[1]}" if len(parts) >= 2 else suffix
            )
            variant = (
                " ".join(p.capitalize() for p in parts[2:])
                if len(parts) > 2
                else ""
            )
            return f"Doubao-Seedance {version} {variant}".rstrip()

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
        Overlay time-boxed Anthropic pricing on upstream entries.

        Two behaviours, keyed on whether upstream already carries the SKU:
          • Present upstream → overlay (``{**existing, **synth}``). Used for
            time-boxed price patches like ``claude-sonnet-5`` introductory
            pricing; remove such entries once their window closes.
          • Absent upstream → inject the synth entry wholesale. Used for
            complete pre-staged models not yet on LiteLLM (e.g.
            ``claude-opus-5``). A partial overlay entry whose SKU is missing
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
    def apply_deepseek_synth(cls, models: dict[str, Any]) -> dict[str, Any]:
        """
        Overlay official deepseek pricing-page metadata onto upstream entries.

        Patches ``max_output_tokens`` (api-docs.deepseek.com states 384K,
        LiteLLM upstream reports 8K) plus the peak-hour token prices, which
        upstream trails. See DEEPSEEK_SYNTH_DATA for the CNY source tariff
        and the peak/off-peak policy.

        SKUs absent from upstream stay absent — DEEPSEEK_SYNTH_DATA is a
        pure overlay, not an injector (whitelist enforces presence).

        Does not mutate the input.
        """
        merged: dict[str, Any] = dict(models)
        for key, synth in cls.DEEPSEEK_SYNTH_DATA.items():
            existing = merged.get(key)
            if existing is None:
                continue
            merged[key] = {**existing, **synth}
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

        SKUs absent from upstream stay absent; OPENAI_SYNTH_DATA only patches
        keys already present, never injects wholesale models.

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

    @classmethod
    def filter_all_models(cls, models: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """
        Filter all models and return a dict of valid models.

        Returns:
            dict mapping model_key to transformed model data
        """
        enriched = cls.apply_ecloud_aicc_synth(
            cls.apply_newapi_synth(
                cls.apply_anthropic_synth(
                    cls.apply_byteplus_synth(
                        cls.apply_volcengine_synth(
                            cls.apply_deepseek_synth(
                                cls.apply_bigmodel_synth(
                                    cls.apply_zai_synth(
                                        cls.apply_google_synth(
                                            cls.apply_moonshot_synth(cls.apply_openai_synth(models))
                                        )
                                    )
                                )
                            )
                        )
                    )
                )
            )
        )
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
        enriched = cls.apply_ecloud_aicc_synth(
            cls.apply_newapi_synth(
                cls.apply_anthropic_synth(
                    cls.apply_byteplus_synth(
                        cls.apply_volcengine_synth(
                            cls.apply_deepseek_synth(
                                cls.apply_bigmodel_synth(
                                    cls.apply_zai_synth(
                                        cls.apply_google_synth(
                                            cls.apply_moonshot_synth(cls.apply_openai_synth(models))
                                        )
                                    )
                                )
                            )
                        )
                    )
                )
            )
        )
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


def filter_all_models(models: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Filter all models and return valid ones."""
    return ModelSyncRules.filter_all_models(models)

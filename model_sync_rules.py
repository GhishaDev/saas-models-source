#!/usr/bin/env python3
"""
Model Sync Rules Configuration

Defines filtering and mapping rules for syncing models from LiteLLM data source
https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json
"""

from __future__ import annotations

import re
from typing import Any, Callable


class ModelSyncRules:
    """Model sync rules configuration and utilities."""

    # Supported providers list
    PROVIDERS = ["openai", "anthropic", "gemini"]

    # Provider name mapping (lowercase for DB consistency)
    PROVIDER_MAPPING = {
        "openai": "openai",
        "anthropic": "anthropic",
        "gemini": "google",
    }

    # Supported model modes
    SUPPORTED_MODES = ["chat", "embedding"]

    # Mode to model type mapping
    MODE_MAPPING = {
        "chat": "language",
        "completion": "language",
        "embedding": "embedding",
        "image_generation": "image",
        "audio_transcription": "audio",
        "audio_speech": "audio",
    }

    # Provider-specific exclusion rules
    PROVIDER_EXCLUSION_RULES: dict[str, dict[str, Any]] = {
        "openai": {
            # Exclude gpt-4 series (including gpt-4o, gpt-4o-mini)
            # Exclude o1 series (keep o3, o4 series)
            # Exclude gpt-*-chat without -latest suffix (keep gpt-*-chat-latest)
            # Exclude ada embedding models (keep text-embedding-*-large/small only)
            # Exclude search-api models
            "patterns": [
                re.compile(r"^gpt-4", re.IGNORECASE),
                re.compile(r"^o1", re.IGNORECASE),
                re.compile(r"^gpt-.*-chat$", re.IGNORECASE),
                re.compile(r"^text-embedding-ada", re.IGNORECASE),
                re.compile(r"-search-api$", re.IGNORECASE),
            ],
            "custom_check": None,
            "description": "Exclude gpt-4, o1, gpt-*-chat w/o -latest, ada, search-api",
        },
        "anthropic": {
            # Only allow models starting with 'claude-'
            # Exclude Claude 4.1 versions
            "patterns": [re.compile(r"claude-\w+-4-1$", re.IGNORECASE)],
            "custom_check": lambda key: not key.startswith("claude-"),
            "description": "Only allow claude-* prefix, exclude regional variants and Claude 4.1",
        },
        "google": {
            # Exclude gemini-1 series and gemini-2.0 series (keep gemini-2.5)
            "patterns": [
                re.compile(r"^gemini/gemini-1\.", re.IGNORECASE),
                re.compile(r"^gemini/gemini-2\.0", re.IGNORECASE),
            ],
            "custom_check": None,
            "description": "Exclude gemini-1 series and gemini-2.0 series (keep gemini-2.5)",
        },
        "gemini": {
            # Same as google - for when litellm_provider is 'gemini' instead of 'google'
            "patterns": [
                re.compile(r"^gemini/gemini-1\.", re.IGNORECASE),
                re.compile(r"^gemini/gemini-2\.0", re.IGNORECASE),
            ],
            "custom_check": None,
            "description": "Exclude gemini-1 series and gemini-2.0 series (keep gemini-2.5)",
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
    ]

    # Exclude specific model keys (exact match)
    EXCLUDE_MODEL_KEYS = [
        # OpenAI legacy/older models
        "gpt-3.5-turbo",
        "gpt-3.5-turbo-16k",
        "gpt-4",
        "gpt-4-32k",
        "gpt-4-turbo",
        # Note: gpt-audio-* and gpt-realtime-* are excluded via EXCLUDE_PATTERNS
        # Gemini non-standard models
        "gemini/gemini-gemma-2-27b-it",
        "gemini/gemini-gemma-2-9b-it",
        "gemini/gemini-pro",
        "gemini/gemini-pro-vision",
    ]

    # Date patterns for validation
    DATE_PATTERNS = {
        "yyyymmdd_dash": re.compile(r"-(\d{4})-(\d{2})-(\d{2})$"),
        "yyyymmdd": re.compile(r"(\d{4})(\d{2})(\d{2})$"),
        "mmdd": re.compile(r"-(\d{2})(\d{2})$"),
    }

    # Include patterns (exceptions to exclude rules)
    INCLUDE_PATTERNS: list[re.Pattern] = [
        re.compile(r"^gpt-.*-chat-latest$", re.IGNORECASE),  # Allow gpt-*-chat-latest despite -latest rule
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
    def should_exclude(cls, model_key: str, provider: str | None = None) -> bool:
        """Check if a model key should be excluded."""
        # Provider-specific exclusion rules have highest priority
        if provider:
            if cls.should_exclude_by_provider(model_key, provider):
                return True

        # Then check include patterns (exceptions to global rules only)
        for pattern in cls.INCLUDE_PATTERNS:
            if pattern.search(model_key):
                return False

        # Check exact match exclude list
        if model_key in cls.EXCLUDE_MODEL_KEYS:
            return True

        # Check for date patterns
        if cls.contains_date_pattern(model_key):
            return True

        # Check global exclude patterns
        for pattern in cls.EXCLUDE_PATTERNS:
            if pattern.search(model_key):
                return True

        return False

    @classmethod
    def should_exclude_due_to_price(cls, model_data: dict[str, Any]) -> bool:
        """Check if a model should be excluded due to zero/missing price."""
        input_cost = model_data.get("input_cost_per_token")
        output_cost = model_data.get("output_cost_per_token")
        mode = model_data.get("mode")

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
            claude-opus-4-1 → Claude 4.1 Opus
            gpt-5-mini → GPT-5 Mini
            o3-mini → o3 Mini
            gemini-2.5-flash → Gemini 2.5 Flash
        """
        key = model_key.lower()

        # Anthropic: claude-opus-4-1 → Claude 4.1 Opus
        if provider == "anthropic" or key.startswith("claude-"):
            parts = key.replace("claude-", "").split("-")
            # Expected format: opus-4-1, sonnet-4-5, haiku-4-5
            if len(parts) >= 3:
                variant = parts[0].capitalize()  # Opus, Sonnet, Haiku
                major_version = parts[1]  # 4
                minor_version = parts[2]  # 1, 5
                return f"Claude {major_version}.{minor_version} {variant}"
            # Fallback: capitalize words
            return " ".join(w.capitalize() for w in key.split("-"))

        # OpenAI: gpt-5-mini → GPT-5 Mini, o3-mini → o3 Mini
        if provider == "openai":
            # o series: o3-mini → o3 Mini, o4-mini → o4 Mini
            if re.match(r"^o\d+", key):
                match = re.match(r"^(o\d+)(?:-(.+))?$", key)
                if match:
                    main = match.group(1)  # o3, o4
                    suffix = match.group(2)  # mini, etc.
                    if suffix:
                        suffix_formatted = " ".join(
                            w.capitalize() for w in suffix.split("-")
                        )
                        return f"{main} {suffix_formatted}"
                    return main

            # GPT series: gpt-5-mini → GPT-5 Mini
            if key.startswith("gpt-"):
                parts = key.replace("gpt-", "").split("-")
                version = parts[0].upper()  # 5, 4.1, etc.
                suffix = " ".join(w.capitalize() for w in parts[1:])
                return f"GPT-{version} {suffix}" if suffix else f"GPT-{version}"

            # Fallback
            return " ".join(w.capitalize() for w in key.split("-"))

        # Google: gemini-2.5-flash → Gemini 2.5 Flash
        # gemini/gemini-2.5-flash → Gemini 2.5 Flash
        if provider == "google" or key.startswith("gemini"):
            # Remove gemini/ prefix if present
            clean_key = key
            if clean_key.startswith("gemini/"):
                clean_key = clean_key[7:]  # Remove 'gemini/'
            # Remove gemini- prefix
            clean_key = clean_key.replace("gemini-", "")

            parts = clean_key.split("-")
            if len(parts) >= 2:
                version = parts[0]  # 2.5, 1.5
                variant = " ".join(w.capitalize() for w in parts[1:])  # Flash, Flash Lite, Pro
                return f"Gemini {version} {variant}"
            return " ".join(w.capitalize() for w in clean_key.split("-"))

        # Fallback: capitalize each word
        return " ".join(w.capitalize() for w in key.split("-"))

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

        return {
            "model_key": model_key,
            "provider": mapped_provider,
            "type": model_type,
            "friendly_name": friendly_name,
            "input_cost_per_token": model_data.get("input_cost_per_token"),
            "output_cost_per_token": model_data.get("output_cost_per_token"),
            "max_input_tokens": model_data.get("max_input_tokens"),
            "max_output_tokens": model_data.get("max_output_tokens"),
            "supports_vision": model_data.get("supports_vision", False),
            "supports_function_calling": model_data.get("supports_function_calling", False),
            "supports_json_output": model_data.get("supports_json_mode", False),
            "raw_data": model_data,
        }

    @classmethod
    def filter_all_models(cls, models: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """
        Filter all models and return a dict of valid models.

        Returns:
            dict mapping model_key to transformed model data
        """
        filtered: dict[str, dict[str, Any]] = {}

        for model_key, model_data in models.items():
            result = cls.filter_model(model_key, model_data)
            if result:
                filtered[model_key] = result

        return filtered

    @classmethod
    def get_filter_stats(cls, models: dict[str, Any]) -> dict[str, Any]:
        """Get statistics about the filtering process."""
        total = len(models)
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

        for model_key, model_data in models.items():
            provider = model_data.get("litellm_provider")
            mode = model_data.get("mode")

            # Check provider support
            if not cls.is_provider_supported(provider):
                excluded_by_rule["unsupported_provider"] += 1
                continue

            # Check mode support
            if not cls.is_mode_supported(mode):
                excluded_by_rule["unsupported_mode"] += 1
                continue

            # Check provider-specific exclusion
            if cls.should_exclude_by_provider(model_key, provider):
                excluded_by_rule["provider_exclusion"] += 1
                continue

            # Check exact match
            if model_key in cls.EXCLUDE_MODEL_KEYS:
                excluded_by_rule["exact_match"] += 1
                continue

            # Check date pattern
            if cls.contains_date_pattern(model_key):
                excluded_by_rule["date_pattern"] += 1
                continue

            # Check global patterns
            excluded_by_pattern = False
            for pattern in cls.EXCLUDE_PATTERNS:
                if pattern.search(model_key):
                    excluded_by_rule["global_exclusion"] += 1
                    excluded_by_pattern = True
                    break

            if excluded_by_pattern:
                continue

            # Check price
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


def filter_model(model_key: str, model_data: dict[str, Any]) -> dict[str, Any] | None:
    """Filter and transform a single model."""
    return ModelSyncRules.filter_model(model_key, model_data)


def filter_all_models(models: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Filter all models and return valid ones."""
    return ModelSyncRules.filter_all_models(models)

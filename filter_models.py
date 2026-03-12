#!/usr/bin/env python3
"""
Filter LiteLLM models by provider with comprehensive filtering rules.

Fetches model data from LiteLLM and filters for OpenAI, Anthropic, and Google models
using the rules defined in model_sync_rules.py.
"""

import argparse
import json
import sys
import time
import urllib.request
from typing import Any

from model_sync_rules import ModelSyncRules


def fetch_models(url: str, timeout: int = 30, max_retries: int = 3, retry_delay: int = 5) -> dict[str, Any]:
    """Fetch model data from URL with retry logic."""
    for attempt in range(max_retries):
        try:
            print(f"Fetching data from {url}... (attempt {attempt + 1}/{max_retries})")
            with urllib.request.urlopen(url, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
                print(f"Successfully fetched {len(data)} models")
                return data
        except Exception as e:
            print(f"Error fetching data (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                print("Max retries reached. Exiting.")
                sys.exit(1)

    return {}


def save_to_file(data: Any, filename: str) -> None:
    """Save data to JSON file."""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved to {filename}")


def print_summary(stats: dict[str, Any]) -> None:
    """Print filtering summary statistics."""
    print("\n" + "=" * 60)
    print("FILTERING SUMMARY")
    print("=" * 60)
    print(f"Total models:          {stats['total']:,}")
    print(f"Passed filters:        {stats['passed']:,}")
    print(f"Excluded:              {stats['excluded']:,}")
    print(f"Pass rate:             {stats['passed'] / stats['total'] * 100:.1f}%")

    print("\nExclusion breakdown:")
    for rule, count in stats["excluded_by_rule"].items():
        if count > 0:
            rule_name = rule.replace("_", " ").title()
            print(f"  - {rule_name}: {count:,}")


def print_models_by_provider(models: dict[str, dict[str, Any]]) -> None:
    """Print filtered models grouped by provider."""
    # Group by provider
    by_provider: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for model_key, model_info in models.items():
        provider = model_info["provider"]
        if provider not in by_provider:
            by_provider[provider] = []
        by_provider[provider].append((model_key, model_info))

    # Print each provider's models
    for provider in ["openai", "anthropic", "google"]:
        if provider not in by_provider:
            continue

        provider_models = by_provider[provider]
        print(f"\n{'=' * 60}")
        print(f"{provider.upper()} ({len(provider_models)} models)")
        print("=" * 60)

        for model_key, model_info in sorted(provider_models, key=lambda x: x[0]):
            friendly_name = model_info["friendly_name"]
            input_cost = model_info.get("input_cost_per_token", 0)
            output_cost = model_info.get("output_cost_per_token", 0)
            max_input = model_info.get("max_input_tokens", "N/A")

            # Convert token costs to per million tokens for readability
            input_per_m = input_cost * 1_000_000 if input_cost else 0
            output_per_m = output_cost * 1_000_000 if output_cost else 0

            print(f"  {friendly_name}")
            print(f"    Key: {model_key}")
            print(f"    Context: {max_input:,} tokens | Cost: ${input_per_m:.2f}/${output_per_m:.2f} per M tokens")


def export_for_sync(models: dict[str, dict[str, Any]], output_file: str) -> None:
    """Export models in a format ready for database sync."""
    export_data = {
        "version": "1.0",
        "source": ModelSyncRules.DATA_SOURCE_URL,
        "models": models,
    }
    save_to_file(export_data, output_file)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Filter LiteLLM models with comprehensive rules"
    )
    parser.add_argument(
        "--output", "-o",
        default="filtered_models.json",
        help="Output file path (default: filtered_models.json)",
    )
    parser.add_argument(
        "--url",
        default=ModelSyncRules.DATA_SOURCE_URL,
        help="Custom data source URL",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress detailed output, show summary only",
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Only show statistics, don't save file",
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "anthropic", "google"],
        help="Filter to specific provider only",
    )

    args = parser.parse_args()

    # Fetch all models
    all_models = fetch_models(
        args.url,
        timeout=ModelSyncRules.SYNC_CONFIG["timeout"] // 1000,
        max_retries=ModelSyncRules.SYNC_CONFIG["max_retries"],
        retry_delay=ModelSyncRules.SYNC_CONFIG["retry_delay"] // 1000,
    )

    # Filter models using rules
    filtered = ModelSyncRules.filter_all_models(all_models)

    # Filter to specific provider if requested
    if args.provider:
        filtered = {
            k: v for k, v in filtered.items()
            if v["provider"] == args.provider
        }

    # Get statistics
    stats = ModelSyncRules.get_filter_stats(all_models)

    # Print summary
    print_summary(stats)

    # Print detailed model list unless quiet mode
    if not args.quiet:
        print_models_by_provider(filtered)

    # Save to file unless stats-only mode
    if not args.stats_only:
        export_for_sync(filtered, args.output)

    print("\n" + "=" * 60)
    print(f"Exported {len(filtered)} models to {args.output}")
    print("=" * 60)


if __name__ == "__main__":
    main()

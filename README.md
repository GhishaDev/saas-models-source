# SaaS Models Source

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

A comprehensive tool for filtering and syncing AI model data from LiteLLM, designed for SaaS applications that need up-to-date model information.

## Features

- **Multi-Provider Support**: Filters models from OpenAI, Anthropic, Google, Z.AI (GLM international), and Bigmodel (智谱开放平台, GLM domestic)
- **Multi-Modal Support**: Chat (language), embedding, and image generation models
- **Smart Filtering Rules**: Comprehensive exclusion rules for deprecated, preview, and versioned models
- **Mode-Aware Price Validation**: Validates pricing using mode-specific fields (per-token, per-image-token, per-image)
- **Flexible Output**: JSON export ready for database synchronization
- **Detailed Statistics**: Track filtering metrics and exclusion reasons with full consistency between `stats.passed` and exported count

## Supported Providers

- **OpenAI**: GPT-5 series, o3/o4 series, text-embedding models, `gpt-image-*` series
- **Anthropic**: Claude 4.5+ series (Haiku, Sonnet, Opus), including dated snapshots
- **Google**: Gemini 2.5+ series (Flash, Flash Lite, Pro), Gemini embedding 2, `gemini-*-image*` series
- **Z.AI (GLM, international)**: Whitelist-curated `zai/glm-*` SKUs with z.ai-authoritative data overlay (GLM-4.5/4.6/4.7/5/5.1 family + vision/OCR variants), priced in USD
- **Bigmodel (智谱开放平台, GLM domestic)**: Whitelist-curated `bigmodel/glm-*` SKUs sourced from `bigmodel.cn/pricing`, RMB→USD converted at a fixed rate (10 SKUs: GLM-4.5-Air, GLM-4.5V, GLM-4.7, GLM-4.7-FlashX, GLM-5, GLM-5-Turbo, GLM-5.1, GLM-5V-Turbo, GLM-4.6V, GLM-4.6V-FlashX)

## Supported Model Types

| Type | Mode | Examples |
|------|------|----------|
| `language` | `chat` | `claude-opus-4-7`, `gpt-5.5`, `gemini/gemini-3-pro-preview`, `zai/glm-5`, `zai/glm-4.5v`, `bigmodel/glm-5` |
| `embedding` | `embedding` | `text-embedding-3-large`, `gemini/gemini-embedding-2` |
| `image` | `image_generation` | `gpt-image-1.5`, `gemini/gemini-2.5-flash-image` |

## Installation

```bash
git clone https://github.com/your-org/saas-models-source.git
cd saas-models-source
```

## Usage

### Basic Usage

```bash
python filter_models.py
```

This will:
1. Fetch the latest model data from LiteLLM
2. Apply filtering rules
3. Save filtered models to `filtered_models.json`

### Advanced Options

```bash
# Show summary only, don't save file
python filter_models.py --stats-only

# Quiet mode (summary only)
python filter_models.py --quiet

# Filter to specific provider
python filter_models.py --provider openai

# Custom output file
python filter_models.py --output my_models.json

# Custom data source URL
python filter_models.py --url https://custom-source.com/models.json
```

## Filtering Rules

### Provider-Specific Rules

#### OpenAI
- ✅ Include: GPT-5 series, o3/o4 series, text-embedding-3-*, `gpt-image-*` series
- ❌ Exclude: GPT-4 series, o1 series, ada embedding models
- ❌ Exclude: `dall-e-*`, `chatgpt-image-*` (legacy image models)
- ❌ Exclude: Models with `openai/` prefix, search-api variants

#### Anthropic
- ✅ Include: Claude 4.5+ variants (Haiku, Sonnet, Opus)
- ✅ Include: Dated snapshots ≥ 4.5 (e.g. `claude-sonnet-4-5-20250929`)
- ❌ Exclude: Claude 4.1 and below versions
- ❌ Exclude: Non-claude prefixed models
- ❌ Exclude: Dated snapshots < 4.5

#### Google
- ✅ Include: Gemini 2.5+ series
- ✅ Include: `gemini-*-image*` series (e.g. `gemini-2.5-flash-image`)
- ❌ Exclude: Gemini 1.x and 2.0–2.4 series
- ❌ Exclude: Gemma models, deprecated versions
- ❌ Exclude: `imagen-*`, `flash-exp-image` (legacy/experimental image models)

#### Z.AI
- ✅ Include: only keys listed in `ModelSyncRules.ZAI_ALLOWED_KEYS` (reverse whitelist)
- ✅ **z.ai as source of truth** via `ZAI_SYNTH_DATA` overlay (sourced from [docs.z.ai/guides/overview/overview](https://docs.z.ai/guides/overview/overview) + [pricing](https://docs.z.ai/guides/overview/pricing)):
  - Pre-staged SKUs absent from LiteLLM are synthesised from z.ai data (GLM-5.1, GLM-5-Turbo, GLM-4.7-FlashX, GLM-5V-Turbo, GLM-4.6V, GLM-4.6V-FlashX, GLM-OCR)
  - When upstream conflicts with z.ai, z.ai wins (e.g. `zai/glm-4.5v` context = 64K per z.ai overview, not the 128K LiteLLM reports)
- ✅ Vision flag auto-inferred for keys matching `glm-*v` or `glm-ocr` when upstream omits `supports_vision`
- ❌ Exclude: `zai/glm-5-code` (not on z.ai official pricing page), other-gateway GLM (openrouter / fireworks / together / bedrock / vertex / novita / cerebras / baseten / gmi / wandb / vercel_ai_gateway / deepinfra)
- ❌ Exclude: Free-tier SKUs via Zero Price rule (e.g. `zai/glm-4.5-flash`, `glm-4.7-flash`, `glm-4.6v-flash`)

#### Bigmodel (智谱开放平台)
- ✅ Include: only keys listed in `ModelSyncRules.BIGMODEL_ALLOWED_KEYS` (reverse whitelist, 10 SKUs)
- ✅ **bigmodel.cn as source of truth** via `BIGMODEL_SYNTH_DATA` (sourced from [bigmodel.cn/pricing](https://www.bigmodel.cn/pricing), snapshot 2026-06-16):
  - Every `bigmodel/` SKU is pre-staged — LiteLLM upstream does not carry `bigmodel/*` keys, so entries are injected wholesale
  - Bigmodel uses tiered pricing (by input length / output length); each SKU is compressed to its **longest-input tier** as a conservative upper-bound
  - RMB prices converted to USD/token at fixed `CNY_USD_RATE = 6.78` (constant lives in `model_sync_rules.py`; bumping it rescales all bigmodel/ prices)
- ✅ Vision flag auto-inferred for `bigmodel/glm-*v` keys (same regex as zai)
- ❌ Exclude (no public API token pricing on bigmodel.cn — only listed under private-instance GPU/day rates): `bigmodel/glm-4.6`, `bigmodel/glm-4.5`, `bigmodel/glm-4.5-x`, `bigmodel/glm-4.5-airx`, `bigmodel/glm-4-32b-0414-128k`, `bigmodel/glm-ocr`
- ❌ Exclude: Free-tier SKUs (`bigmodel/glm-4.5-flash`, `bigmodel/glm-4.7-flash`, `bigmodel/glm-4.6v-flash`) via Zero Price rule

> **Why two GLM providers?** `zai/` and `bigmodel/` describe the **same models on different platforms with different prices**. z.ai (international) bills in USD; bigmodel.cn (中国版) bills in RMB. SKU-level pricing on the two platforms is **not** a simple exchange-rate conversion. Pick the namespace that matches the gateway you actually call.

### Global Exclusion Rules

- **Version Patterns**: Exclude date-stamped models (YYYY-MM-DD, YYYYMMDD), except claude snapshots ≥ 4.5
- **Image Variants**: Exclude size/quality variants (`low/`, `medium/`, `high/`, `standard/`, `hd/`, `auto/`, `WxH/` prefixes)
- **Preview/Legacy**: Exclude `-preview`, `-old`, `-deprecated`, `-legacy` suffixes
- **Latest Versions**: Exclude models ending with `-latest` (except `gpt-*-chat-latest`)
- **Fine-tuned**: Exclude models starting with `ft:`
- **Cloud-Specific**: Exclude Azure, Bedrock, Sagemaker variants
- **Price Validation**: Mode-aware — excludes models with zero/missing input pricing across all applicable fields

### Default Availability Rules

Each model includes an `is_default_available` field indicating default user availability:

- **Default**: `true` for all models
- **OpenAI o series** (o3, o4, o3-mini, o4-mini): `false`
- **OpenAI chat series** (gpt-*-chat-*): `false`
- **Image models** (all `image` type): `false`

These models require special access or configuration and are not available to all users by default.

## Output Format

```json
{
  "version": "1.0",
  "source": "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json",
  "models": {
    "claude-sonnet-4-6": {
      "model_key": "claude-sonnet-4-6",
      "provider": "anthropic",
      "type": "language",
      "friendly_name": "Claude 4.6 Sonnet",
      "is_default_available": true,
      "input_cost_per_token": 3e-06,
      "output_cost_per_token": 1.5e-05,
      "cache_read_input_token_cost": 3e-07,
      "max_input_tokens": 200000,
      "max_output_tokens": 64000,
      "supports_vision": true,
      "supports_function_calling": true,
      "supports_json_output": false
    },
    "o3": {
      "model_key": "o3",
      "provider": "openai",
      "type": "language",
      "friendly_name": "o3",
      "is_default_available": false,
      "input_cost_per_token": 2e-06,
      "output_cost_per_token": 8e-06,
      "max_input_tokens": 200000,
      "max_output_tokens": 100000,
      "supports_vision": true,
      "supports_function_calling": true,
      "supports_json_output": false
    },
    "gpt-image-1.5": {
      "model_key": "gpt-image-1.5",
      "provider": "openai",
      "type": "image",
      "friendly_name": "GPT Image 1.5",
      "is_default_available": false,
      "input_cost_per_token": 5e-06,
      "output_cost_per_token": 1e-05,
      "max_input_tokens": null,
      "max_output_tokens": null,
      "supports_vision": false,
      "supports_function_calling": false,
      "supports_json_output": false
    },
    "claude-sonnet-4-5-20250929": {
      "model_key": "claude-sonnet-4-5-20250929",
      "provider": "anthropic",
      "type": "language",
      "friendly_name": "Claude 4.5 Sonnet 20250929",
      "is_default_available": true,
      "input_cost_per_token": 3e-06,
      "output_cost_per_token": 1.5e-05,
      "max_input_tokens": 200000,
      "max_output_tokens": 64000,
      "supports_vision": true,
      "supports_function_calling": true,
      "supports_json_output": false
    },
    "zai/glm-4.5v": {
      "model_key": "zai/glm-4.5v",
      "provider": "zai",
      "type": "language",
      "friendly_name": "GLM-4.5V",
      "is_default_available": true,
      "input_cost_per_token": 6e-07,
      "output_cost_per_token": 1.8e-06,
      "cache_read_input_token_cost": 1.1e-07,
      "max_input_tokens": 64000,
      "max_output_tokens": 32000,
      "supports_vision": true,
      "supports_function_calling": true,
      "supports_json_output": false
    }
  }
}
```

## Project Structure

```
.
├── filter_models.py          # Main filtering script
├── model_sync_rules.py       # Filtering rules configuration
├── filtered_models.json      # Output file (generated)
├── LICENSE                   # MIT License
└── README.md                 # This file
```

## Data Source

Model data is fetched from:
https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json

## Configuration

Edit `model_sync_rules.py` to customize:

- **PROVIDERS**: Supported provider list
- **PROVIDER_EXCLUSION_RULES**: Provider-specific regex patterns
- **EXCLUDE_PATTERNS**: Global exclusion patterns
- **EXCLUDE_MODEL_KEYS**: Exact model keys to exclude
- **SYNC_CONFIG**: Retry and timeout settings

## Example Output Statistics

```
============================================================
FILTERING SUMMARY
============================================================
Total models:          2,801
Passed filters:        74
Excluded:              2,727
Pass rate:             2.6%

Exclusion breakdown:
  - Unsupported Provider: 2,471
  - Unsupported Mode: 56
  - Provider Exclusion: 58
  - Global Exclusion: 73
  - Date Pattern: 60
  - Exact Match: 6
  - Zero Price: 3
```

> `Total` includes 7 z.ai pre-staged SKUs injected by `ZAI_SYNTH_DATA` and 10 bigmodel SKUs injected by `BIGMODEL_SYNTH_DATA`. `passed` always equals `len(filter_all_models(models))`.

> `passed` always equals `len(filter_all_models(models))`. Stats and export share the same exclusion pipeline (`should_exclude_with_reason`).

## Requirements

- Python 3.10+
- Standard library only (no external dependencies)

## API Reference

### ModelSyncRules Class

```python
from model_sync_rules import ModelSyncRules

# Check if a model should be excluded
ModelSyncRules.should_exclude("gpt-4", "openai")  # True

# Format model name
ModelSyncRules.format_model_name("claude-sonnet-4-6", "anthropic")
# Returns: "Claude 4.6 Sonnet"

# Check if a model is default available
ModelSyncRules.is_default_available("o3", "openai")  # False
ModelSyncRules.is_default_available("gpt-5", "openai")  # True
ModelSyncRules.is_default_available("gpt-image-1.5", "openai", "image")  # False

# Check if a model key is an allowed claude dated snapshot (version >= 4.5)
ModelSyncRules.is_claude_dated_snapshot("claude-sonnet-4-5-20250929")  # True
ModelSyncRules.is_claude_dated_snapshot("claude-opus-4-1-20250805")  # False

# Exclusion with reason (for telemetry / stats)
ModelSyncRules.should_exclude_with_reason("dall-e-3", "openai")
# Returns: (True, "provider_exclusion")

# Filter a single model
result = ModelSyncRules.filter_model(model_key, model_data)

# Filter all models
filtered = ModelSyncRules.filter_all_models(all_models)

# Get filtering statistics
stats = ModelSyncRules.get_filter_stats(all_models)
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/improvement`)
3. Commit changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/improvement`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Model data provided by [LiteLLM](https://github.com/BerriAI/litellm)
- Inspired by the need for clean, production-ready model catalogs

## Changelog

### v1.7.0 (2026-06-16)
- Add **Bigmodel (智谱开放平台)** as the fifth supported provider via reverse-whitelist (`BIGMODEL_ALLOWED_KEYS`)
- 10 `bigmodel/glm-*` SKUs sourced from [bigmodel.cn/pricing](https://www.bigmodel.cn/pricing) (snapshot 2026-06-16): GLM-5, GLM-5-Turbo, GLM-5.1, GLM-5V-Turbo, GLM-4.7, GLM-4.7-FlashX, GLM-4.6V, GLM-4.6V-FlashX, GLM-4.5-Air, GLM-4.5V
- Bigmodel's tiered pricing compressed to **longest-input tier** per SKU as conservative upper-bound; RMB→USD at fixed `CNY_USD_RATE = 6.78`
- `zai/` and `bigmodel/` coexist: same GLM models, distinct platform pricing (USD vs RMB-derived). Downstream consumers pick the namespace matching their gateway
- Generalise vision detection regex (`_GLM_VISION_KEY`) and `format_model_name` GLM branch to cover both `zai/` and `bigmodel/`
- `apply_bigmodel_synth()` runs at the entry of both `filter_all_models` and `get_filter_stats` (stats remain consistent with export)
- Exclude bigmodel SKUs without public API token pricing: `bigmodel/glm-4.6`, `bigmodel/glm-4.5`, `bigmodel/glm-4.5-x`, `bigmodel/glm-4.5-airx`, `bigmodel/glm-4-32b-0414-128k`, `bigmodel/glm-ocr` (these only appear under private-instance GPU/day rates on bigmodel.cn)

### v1.6.0 (2026-06-13)
- Export `cache_read_input_token_cost` field (cached input pricing per token)
- Overlay z.ai-authoritative cached input pricing for `zai/glm-4.5` family + `zai/glm-4.5v` (upstream missed these)
- `zai/glm-4-32b-0414-128k` and `zai/glm-ocr` correctly export `null` cache cost (z.ai shows no cache pricing)

### v1.5.0 (2026-06-13)
- Add `ZAI_SYNTH_DATA` overlay — z.ai becomes the source of truth for whitelisted GLM SKUs
- Synthesise full data (context, max output, pricing, capabilities) for 7 pre-staged SKUs from [docs.z.ai/guides/overview](https://docs.z.ai/guides/overview/overview): GLM-5.1, GLM-5-Turbo, GLM-4.7-FlashX, GLM-5V-Turbo, GLM-4.6V, GLM-4.6V-FlashX, GLM-OCR
- Override `zai/glm-4.5v` context to 64K (LiteLLM reports 128K, z.ai overview lists 64K)
- `apply_zai_synth()` runs at the entry of both `filter_all_models` and `get_filter_stats` (stats remain consistent with export)

### v1.4.0 (2026-06-13)
- Add **Z.AI (GLM)** as the fourth supported provider via reverse-whitelist (`ZAI_ALLOWED_KEYS`)
- Whitelist GLM-4.5 family (Air/AirX/X/V/32B), GLM-4.6, GLM-4.7, GLM-5
- Pre-stage upcoming SKUs from [docs.z.ai pricing](https://docs.z.ai/guides/overview/pricing) (GLM-5.1, GLM-5-Turbo, GLM-4.7-FlashX, GLM-5V-Turbo, GLM-4.6V, GLM-4.6V-FlashX, GLM-OCR) — activate automatically when LiteLLM publishes them
- Auto-infer `supports_vision=true` for `zai/glm-*v` and `zai/glm-ocr` keys
- Friendly-name formatting (`GLM-4.5-Air`, `GLM-4.5V`, `GLM-4.5-AirX`, `GLM-OCR`)
- Exclude `zai/glm-5-code` (not on z.ai official pricing page) and all other-gateway GLM listings
- Fix `filter_models.py` crash on `max_input_tokens=None` (image SKUs)
- `--provider` choices now derived from `PROVIDER_MAPPING` (no hardcoded list)

### v1.3.0 (2026-05-20)
- Support `image_generation` mode with mode-aware price validation
- Include `gpt-image-*` (OpenAI) and `gemini-*-image*` (Gemini) series
- Exclude size/quality variants (`low/`, `high/`, `hd/`, `1024-x-1024/`, etc.)
- Exclude `dall-e-*`, `chatgpt-image-*`, `imagen-*`, `flash-exp-image` variants
- Set `is_default_available=false` for all image models
- Refactor exclusion logic into `should_exclude_with_reason` single source of truth
- Fix stats `passed` count to match exported model count exactly

### v1.2.0 (2026-05-19)
- Allow claude dated snapshots with version ≥ 4.5 (e.g. `claude-sonnet-4-5-20250929`)
- Format dated snapshot friendly names as `Claude 4.5 Sonnet 20250929`
- Sync Claude 4.7 Opus, GPT-5.5, Gemini Embedding 2

### v1.1.0 (2026-03-12)
- Add `is_default_available` field to model output
- Implement default availability rules for OpenAI o series and chat series
- Update documentation with field explanation and examples

### v1.0.0 (2026-03-12)
- Initial release
- Support for OpenAI, Anthropic, and Google providers
- Comprehensive filtering rules
- JSON export functionality

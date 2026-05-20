# SaaS Models Source

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

A comprehensive tool for filtering and syncing AI model data from LiteLLM, designed for SaaS applications that need up-to-date model information.

## Features

- **Multi-Provider Support**: Filters models from OpenAI, Anthropic, and Google
- **Multi-Modal Support**: Chat (language), embedding, and image generation models
- **Smart Filtering Rules**: Comprehensive exclusion rules for deprecated, preview, and versioned models
- **Mode-Aware Price Validation**: Validates pricing using mode-specific fields (per-token, per-image-token, per-image)
- **Flexible Output**: JSON export ready for database synchronization
- **Detailed Statistics**: Track filtering metrics and exclusion reasons with full consistency between `stats.passed` and exported count

## Supported Providers

- **OpenAI**: GPT-5 series, o3/o4 series, text-embedding models, `gpt-image-*` series
- **Anthropic**: Claude 4.5+ series (Haiku, Sonnet, Opus), including dated snapshots
- **Google**: Gemini 2.5+ series (Flash, Flash Lite, Pro), Gemini embedding 2, `gemini-*-image*` series

## Supported Model Types

| Type | Mode | Examples |
|------|------|----------|
| `language` | `chat` | `claude-opus-4-7`, `gpt-5.5`, `gemini/gemini-3-pro-preview` |
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
Total models:          2,720
Passed filters:        45
Excluded:              2,675
Pass rate:             1.7%

Exclusion breakdown:
  - Unsupported Provider: 2,421
  - Unsupported Mode: 56
  - Provider Exclusion: 57
  - Global Exclusion: 73
  - Date Pattern: 60
  - Exact Match: 6
  - Zero Price: 2
```

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

# SaaS Models Source

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

A comprehensive tool for filtering and syncing AI model data from LiteLLM, designed for SaaS applications that need up-to-date model information.

## Features

- **Multi-Provider Support**: Filters models from OpenAI, Anthropic, Google, Z.AI (GLM international), Bigmodel (智谱开放平台, GLM domestic), DeepSeek, Volcengine (ByteDance Ark — Doubao Seedance video), and two aggregator mirrors: new-api and ecloud_aicc
- **Multi-Modal Support**: Chat (language), embedding, image generation, video generation, and audio (speech / transcription) models
- **Smart Filtering Rules**: Comprehensive exclusion rules for deprecated, preview, and versioned models
- **Mode-Aware Price Validation**: Validates pricing using mode-specific fields (per-token, per-image-token, per-image)
- **Flexible Output**: JSON export ready for database synchronization
- **Detailed Statistics**: Track filtering metrics and exclusion reasons with full consistency between `stats.passed` and exported count

## Supported Providers

- **OpenAI**: GPT-5 series, o3/o4 series, text-embedding models, `gpt-image-*` series, plus a curated audio / realtime allow-list (`gpt-4o`, `gpt-4o-mini`, `gpt-realtime`, `gpt-4o-realtime-preview-2024-12-17`, `gpt-4o-mini-transcribe`, `gpt-4o-mini-tts`, `whisper-1`)
- **Anthropic**: Claude 4.5+ series (Haiku, Sonnet, Opus), including dated snapshots
- **Google**: Gemini 2.5+ series (Flash, Flash-Lite, Pro), Gemini Embedding 2, `gemini-*-image*` series
- **Z.AI (GLM, international)**: Whitelist-curated `zai/glm-*` SKUs with z.ai-authoritative data overlay (GLM-4.5/4.6/4.7/5/5.1 family + vision/OCR variants), priced in USD
- **Bigmodel (智谱开放平台, GLM domestic gateway)**: Whitelist-curated `bigmodel/glm-*` SKUs that mirror sibling `zai/*` USD pricing 1:1 (11 SKUs: GLM-5.2, GLM-5.1, GLM-5, GLM-5-Turbo, GLM-5V-Turbo, GLM-4.7, GLM-4.7-FlashX, GLM-4.6V, GLM-4.6V-FlashX, GLM-4.5-Air, GLM-4.5V)
- **DeepSeek**: Whitelist-curated active SKUs from `api-docs.deepseek.com/quick_start/pricing` (2 SKUs: DeepSeek-V4-Flash, DeepSeek-V4-Pro — 1M context, 384K max output)
- **Volcengine (ByteDance Ark, Doubao Seedance video)**: Whitelist-curated Seedance 2.0 video SKUs from [volcengine.com/docs/82379/1544106](https://www.volcengine.com/docs/82379/1544106) (6 entries: standard / Fast / Mini × dated + alias). Prices stored as **USD/token** via the standard `output_cost_per_token[_<res>][_with_input_video]` family — the underlying CNY tariff has been converted at our internal LiteLLM fork's policy FX rate (`1 USD = 7.0 CNY`); the LiteLLM billing manager bills in USD with no runtime FX lookup
- **new-api (aggregator gateway)**: Reverse-whitelist mirror provider. Every `new-api/<sku>` is a full copy of an already-populated `<vendor>/<sku>` record with only `litellm_provider` re-labelled. Seedance is the first family mirrored (6 SKUs from `volcengine/doubao-seedance-*`); extending to more vendors is a two-line change (whitelist entry + `NEWAPI_MIRROR_SOURCES` mapping)
- **ecloud_aicc (aggregator gateway)**: Second mirror provider — same mechanic as new-api, distinct namespace so deployments routing through the ecloud_aicc gateway can address SKUs by their aggregator-side name. Currently mirrors the same 6 Seedance SKUs from `volcengine/doubao-seedance-*`

## Supported Model Types

| Type | Mode | Examples |
|------|------|----------|
| `language` | `chat` | `claude-opus-4-7`, `gpt-5.5`, `gemini/gemini-3-pro-preview`, `zai/glm-5`, `bigmodel/glm-5`, `deepseek/deepseek-v4-flash` |
| `embedding` | `embedding` | `text-embedding-3-large`, `gemini/gemini-embedding-2` |
| `image` | `image_generation` | `gpt-image-1.5`, `gemini/gemini-2.5-flash-image` |
| `video` | `video_generation` | `volcengine/doubao-seedance-2-0`, `new-api/doubao-seedance-2-0-fast`, `ecloud_aicc/doubao-seedance-2-0-mini` |
| `audio` | `audio_speech`, `audio_transcription` | `gpt-4o-mini-tts` (TTS), `gpt-4o-mini-transcribe` / `whisper-1` (ASR) |

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
- ✅ Include (audio / realtime allow-list, exact match via `INCLUDE_PATTERNS`): `gpt-4o`, `gpt-4o-mini`, `gpt-realtime`, `gpt-4o-realtime-preview-2024-12-17`, `gpt-4o-mini-transcribe`, `gpt-4o-mini-tts`, `whisper-1`
- ✅ Supports **audio_speech** (TTS) and **audio_transcription** (ASR) modes — `PRICE_FIELDS_BY_MODE` accepts either per-token or per-second billing (whisper-1 uses `input_cost_per_second`; gpt-4o-*-transcribe/tts use `input_cost_per_token` + `output_cost_per_audio_token`)
- ✅ Include GPT-4.1 lineage: `gpt-4.1`, `gpt-4.1-mini`, `gpt-4.1-nano` (passes narrowed `^gpt-4` pattern)
- ✅ Supports `responses` mode (OpenAI's `/v1/responses` endpoint — used by codex, gpt-*-pro, deep-research families). `MODE_MAPPING["responses"] = "language"`. Only `gpt-5.3-codex` is whitelisted; wider codex / pro / deep-research variants stay excluded (see below)
- ❌ Exclude: GPT-4 legacy (`gpt-4`, `gpt-4-turbo`, `gpt-4-32k`, `gpt-4-YYYY-MM-DD`) — narrowed pattern preserves GPT-4o and 4.1 families
- ❌ Exclude: o1 series, ada embedding models
- ❌ Exclude: `dall-e-*`, `chatgpt-image-*` (legacy image models)
- ❌ Exclude via `EXCLUDE_MODEL_KEYS` (outside sanctioned allow-lists):
  - audio: `gpt-4o-transcribe`, `gpt-4o-transcribe-diarize`
  - responses: `gpt-5-codex`, `gpt-5-pro`, `gpt-5.1-codex`, `gpt-5.1-codex-max`, `gpt-5.1-codex-mini`, `gpt-5.2-codex`, `gpt-5.2-pro`, `gpt-5.4-pro`, `gpt-5.5-pro`, `o3-deep-research`, `o3-pro`, `o4-mini-deep-research`
- ❌ Exclude: Models with `openai/` prefix, search-api variants
- ✅ Friendly name follows OpenAI's own house style: size suffixes `mini` / `nano` stay **lowercase** (`GPT-5 mini`, `GPT-5.4 nano`, `GPT-4o mini`); `GPT-4o` keeps the lowercase branded `o`; the o-series is shown as its lowercase id (`o3`, `o3-mini`, `o4-mini`); `text-embedding-3-*` is shown as the lowercase id; `gpt-5.3-codex` → `GPT-5.3-Codex` (hyphenated); dated realtime preview drops the snapshot (`gpt-4o-realtime-preview-2024-12-17` → `GPT-4o Realtime`); `GPT Realtime` uses a spaced form; segment overrides upcase `TTS` / `ASR`

#### Anthropic
- ✅ Include: Claude 4.5+ variants (Haiku, Sonnet, Opus), plus Claude 5 (Sonnet, Opus), plus special-name flagships (`claude-fable-5`, `claude-mythos-5`, etc.)
- ✅ Include: Dated snapshots ≥ 4.5 (e.g. `claude-sonnet-4-5-20250929`)
- ✅ **Introductory-price overlay** via `ANTHROPIC_SYNTH_DATA` / `apply_anthropic_synth`: when Anthropic runs a time-boxed intro price, LiteLLM upstream tracks the post-window standard tariff — we overlay the currently-effective numbers so the catalogue matches what customers actually get billed today
  - Active window: **`claude-sonnet-5` through 2026-08-31** ($2 / $10 / $0.20 / $2.50 per M input / output / cache-read / cache-write-5m). Standard tariff ($3 / $15 / $0.30 / $3.75) resumes 2026-09-01 — remove the `ANTHROPIC_SYNTH_DATA["claude-sonnet-5"]` entry that day so upstream flows through unchanged
- ✅ Friendly name follows Anthropic's official variant-first order: `Claude {Variant} {ver}` for the standard Opus/Sonnet/Haiku family (e.g. `Claude Sonnet 5`, `Claude Sonnet 4.5`, `Claude Opus 4.7`); special-name flagships keep a capitalized fallback (`Claude Fable 5`). Dated snapshots carry **no** date suffix — they share the base model's display name (e.g. `claude-sonnet-4-5-20250929` → `Claude Sonnet 4.5`), matching platform.claude.com
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
  - Pre-staged SKUs absent from LiteLLM are synthesised from z.ai data (GLM-5.2, GLM-5.1, GLM-5-Turbo, GLM-4.7-FlashX, GLM-5V-Turbo, GLM-4.6V, GLM-4.6V-FlashX, GLM-OCR)
  - When upstream conflicts with z.ai, z.ai wins (e.g. `zai/glm-4.5v` context = 64K per z.ai overview, not the 128K LiteLLM reports)
- ✅ Vision flag auto-inferred for keys matching `glm-*v` or `glm-ocr` when upstream omits `supports_vision`
- ❌ Exclude: `zai/glm-5-code` (not on z.ai official pricing page), other-gateway GLM (openrouter / fireworks / together / bedrock / vertex / novita / cerebras / baseten / gmi / wandb / vercel_ai_gateway / deepinfra)
- ❌ Exclude: Free-tier SKUs via Zero Price rule (e.g. `zai/glm-4.5-flash`, `glm-4.7-flash`, `glm-4.6v-flash`)

#### Bigmodel (智谱开放平台)
- ✅ Include: only keys listed in `ModelSyncRules.BIGMODEL_ALLOWED_KEYS` (reverse whitelist, 11 SKUs)
- ✅ **Pricing mirrors `zai/*` (z.ai international USD)** via `apply_bigmodel_synth`:
  - Every `bigmodel/` SKU is pre-staged — LiteLLM upstream does not carry `bigmodel/*` keys
  - `BIGMODEL_SYNTH_DATA` provides metadata only (context, capabilities); `input_cost_per_token`, `output_cost_per_token`, and `cache_read_input_token_cost` are copied from the sibling `zai/<sku>` at synth time
  - `apply_bigmodel_synth` runs **after** `apply_zai_synth` so prices reflect z.ai overlays + LiteLLM upstream (e.g. `bigmodel/glm-5` inherits `zai/glm-5`'s upstream prices; `bigmodel/glm-4.5v` inherits its z.ai cache overlay)
  - If a sibling `zai/<sku>` lacks a price field, the bigmodel SKU drops out via the zero-price filter — gaps surface instead of being silently zeroed
- ✅ Vision flag auto-inferred for `bigmodel/glm-*v` keys (same regex as zai)
- ❌ Exclude (no sibling zai pricing → would fail zero-price filter): `bigmodel/glm-4.6`, `bigmodel/glm-4.5`, `bigmodel/glm-4.5-x`, `bigmodel/glm-4.5-airx`, `bigmodel/glm-4-32b-0414-128k`, `bigmodel/glm-ocr`
- ❌ Exclude: Free-tier SKUs (`bigmodel/glm-4.5-flash`, `bigmodel/glm-4.7-flash`, `bigmodel/glm-4.6v-flash`) via Zero Price rule

> **Why two GLM providers?** `zai/` and `bigmodel/` describe the **same models served by two gateways** — z.ai (international) and bigmodel.cn (中国版). Pricing is currently unified to z.ai's USD tariff on both sides; the two namespaces remain distinct so downstream consumers can pick the gateway they actually call without rewriting the model key.

#### Volcengine (ByteDance Ark — Doubao Seedance video)
- ✅ Include: only keys listed in `ModelSyncRules.VOLCENGINE_ALLOWED_KEYS` (reverse whitelist, 6 SKUs covering Seedance 2.0 / Fast / Mini × {dated official ID, date-less alias})
- ✅ **Currency: USD/token** via the standard `output_cost_per_token[_<res>][_with_input_video]` family. Top-level `output_cost_per_token` carries the base 720p / no-input-video tier; resolution-suffixed (`_1080p` / `_4k`) and v2v-suffixed (`_with_input_video`) variants flow through under `raw_data` for tier-aware billing.
- ✅ The underlying tariff is CNY (Volcengine publishes per-million-token CNY rates tiered by resolution and v2v). USD numbers in this catalogue are produced at a policy rate of **`1 USD = 7.0 CNY`**, mirroring the LiteLLM fork's `VOLCENGINE_FX_POLICY.md`. Refresh both sides together if the FX policy changes.
- ✅ Prices are rounded to **4 significant digits** via `_cny_per_m_to_usd_per_token()` — matches upstream LiteLLM precision and stays reversible to the source integer CNY value (e.g. `6.571e-06 × 7.0 × 10⁶ ≈ 46 CNY/M`)
- ✅ `input_cost_per_token` is `null` (Volcengine bills only the output tokens for video, not the text prompt).
- ✅ `is_default_available = false` for all video SKUs (treated the same as image)
- ❌ Exclude: any other `volcengine/*` SKU upstream may add (chat, embedding, audio); whitelist is exhaustive
- ❌ Exclude: Volcengine chat/embedding models routed through non-Ark gateways

> **dated vs date-less alias.** Each Seedance variant ships two whitelisted keys with **identical pricing** — the dated official ID (e.g. `volcengine/doubao-seedance-2-0-260128`, the snapshot the Volcengine SDK defaults to) and the date-less alias (e.g. `volcengine/doubao-seedance-2-0`, the long-lived shortcut Volcengine's gateway resolves to "latest stable"). Downstream consumers should **pick one form per environment and stick to it** — mixing the two over the same workload causes the billing aggregator to double-count usage, and tariff updates have to be made in both places.

> **`supports_vision` semantics for video SKUs.** All Seedance entries report `supports_vision: false`. The field means **"can analyze image content to answer questions"** (a chat-vision capability), not "accepts an image as a generation reference". Image-to-video is supported (and priced via the separate `output_cost_per_token_with_input_video` tier in `raw_data`) — UIs that gate the "upload reference image" affordance on `supports_vision` will under-expose Seedance and should branch on `type == "video"` instead.

> **`volcengine_new_api` vs the `new-api/` mirror provider.** These are two distinct concepts. `volcengine_new_api` is a LiteLLM **routing-layer** label used inside a deployment's config to indicate "this Volcengine deployment sits behind a new-api relay" — it does not appear in the catalogue. Separately, the `new-api/*` prefix in this catalogue is a **catalogue-layer mirror provider**: a copy of vendor SKUs re-namespaced onto a `new-api/` prefix so consumers routing through new-api can address them by their aggregator-side names. See the `#### new-api` section for the mirror mechanic.

#### new-api (aggregator mirror provider)
- ✅ Include: only keys listed in `ModelSyncRules.NEWAPI_ALLOWED_KEYS` (reverse whitelist, 6 SKUs today — all Seedance)
- ✅ **Source of truth: `NEWAPI_MIRROR_SOURCES`** maps each `new-api/<sku>` to its authoritative source key (currently `volcengine/doubao-seedance-*`). `apply_newapi_synth` runs *after* every other vendor synth so those sources are already populated; each new-api entry is a full copy of its source's raw record with only `litellm_provider` re-labelled to `"new-api"`
- ✅ Prices, context, capabilities, and modes stay in **lock-step** with the source — Volcengine tariff change → new-api mirror updates on the next sync, no manual work
- ✅ Missing sources fail silently (the mirror is skipped, its whitelist entry then drops via unsupported-provider / zero-price) — surfaces gaps instead of exporting stale duplicates
- ✅ Adding a new mirrored SKU is a two-line change: append `new-api/<sku>` to `NEWAPI_ALLOWED_KEYS` and add a `NEWAPI_MIRROR_SOURCES[...]` mapping row
- ❌ Exclude: any `new-api/<sku>` without a matching whitelist entry
- ❌ Exclude: `new-api/<sku>` whose source key isn't present in the merged catalogue after all other synths run

#### ecloud_aicc (aggregator mirror provider)
- ✅ Include: only keys listed in `ModelSyncRules.ECLOUD_AICC_ALLOWED_KEYS` (reverse whitelist, 6 SKUs today — all Seedance)
- ✅ **Same mirror mechanic as `new-api`**: `ECLOUD_AICC_MIRROR_SOURCES` maps each `ecloud_aicc/<sku>` to its authoritative source key (currently `volcengine/doubao-seedance-*`). `apply_ecloud_aicc_synth` runs at the tail of the synth chain — every source is already populated by the time it runs
- ✅ Prices / context / capabilities / mode stay in lock-step with the source (Volcengine tariff change → both `new-api/*` and `ecloud_aicc/*` refresh on next sync)
- ✅ Underscore-in-name is intentional (matches how the ecloud_aicc gateway spells its own provider identifier); the friendly-name Seedance branch handles the prefix alongside `volcengine/` and `new-api/`
- ✅ Extending: append a whitelist entry AND an `ECLOUD_AICC_MIRROR_SOURCES` row pointing at the source key (two lines)
- ❌ Exclude: any `ecloud_aicc/<sku>` without a matching whitelist entry
- ❌ Exclude: `ecloud_aicc/<sku>` whose source key isn't present in the merged catalogue after all other synths run

#### DeepSeek
- ✅ Include: only keys listed in `ModelSyncRules.DEEPSEEK_ALLOWED_KEYS` (reverse whitelist, 2 SKUs)
- ✅ **Official DeepSeek pricing page as source of truth** ([api-docs.deepseek.com/quick_start/pricing](https://api-docs.deepseek.com/quick_start/pricing/), snapshot 2026-06-30):
  - LiteLLM upstream carries correct prices, context (1M input), and capabilities; the only mismatch is `max_output_tokens` (upstream `8192`, official `384000`)
  - `DEEPSEEK_SYNTH_DATA` overlays just that field via `apply_deepseek_synth` — no price synthesis needed
- ❌ Exclude `deepseek-chat` / `deepseek-reasoner`: scheduled for deprecation on 2026-07-24 (currently aliases of `deepseek-v4-flash` thinking/non-thinking modes)
- ❌ Exclude `deepseek-v3` / `deepseek-v3.2` / `deepseek-r1` / `deepseek-coder`: superseded by V4, no longer listed on the official pricing page
- ❌ Exclude all bare-key forms (`deepseek-chat`, `deepseek-v4-flash`, etc.): the `deepseek/` namespace is canonical

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
- **Video models** (all `video` type): `false`

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
      "friendly_name": "Claude Sonnet 4.5",
      "is_default_available": true,
      "input_cost_per_token": 3e-06,
      "output_cost_per_token": 1.5e-05,
      "max_input_tokens": 200000,
      "max_output_tokens": 64000,
      "supports_vision": true,
      "supports_function_calling": true,
      "supports_json_output": false
    },
    "volcengine/doubao-seedance-2-0-260128": {
      "model_key": "volcengine/doubao-seedance-2-0-260128",
      "provider": "volcengine",
      "type": "video",
      "friendly_name": "Doubao-Seedance 2.0",
      "is_default_available": false,
      "input_cost_per_token": null,
      "output_cost_per_token": 6.571428571428571e-06,
      "max_input_tokens": 1024,
      "max_output_tokens": 1024,
      "supports_vision": false,
      "supports_function_calling": false,
      "supports_json_output": false,
      "raw_data": {
        "mode": "video_generation",
        "output_cost_per_token": 6.571428571428571e-06,
        "output_cost_per_token_with_input_video": 4e-06,
        "output_cost_per_token_1080p": 7.285714285714286e-06,
        "output_cost_per_token_1080p_with_input_video": 4.428571428571429e-06,
        "output_cost_per_token_4k": 3.714285714285714e-06,
        "output_cost_per_token_4k_with_input_video": 2.285714285714286e-06
      }
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
Total models:          2,803
Passed filters:        76
Excluded:              2,727
Pass rate:             2.7%

Exclusion breakdown:
  - Unsupported Provider: 2,471
  - Unsupported Mode: 56
  - Provider Exclusion: 58
  - Global Exclusion: 73
  - Date Pattern: 60
  - Exact Match: 6
  - Zero Price: 3
```

> `Total` includes 8 z.ai pre-staged SKUs injected by `ZAI_SYNTH_DATA` and 11 bigmodel SKUs injected by `BIGMODEL_SYNTH_DATA`. `passed` always equals `len(filter_all_models(models))`.

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

### v1.16.4 (2026-07-25)
- Include **Claude Mythos 5** (`claude-mythos-5`) — supersedes the v1.16.3 note that excluded it. Project Glasswing limited-availability sibling of Fable 5 (defensive-cyber); same specs, pricing, and API surface as Fable 5: **$10 / $50 per M** input / output, cache-read $1, 5m write $12.50, 1h write $20, 1M ctx, 128K out. Prices verified against the platform.claude.com pricing table. Injected wholesale via `ANTHROPIC_SYNTH_DATA`. Exported total **118 → 119** (+1); no existing entries changed.

### v1.16.3 (2026-07-25)
- Sync **newly released Claude and Gemini models** from vendor docs (not yet on BerriAI upstream) via wholesale-inject synth entries. Exported total **114 → 118** (+4); no existing entries changed.
  - **Claude Opus 5** (`claude-opus-5`) — current flagship per platform.claude.com: $5 / $25 per M input / output, cache-read $0.50, 1M ctx, 128K max output; same request surface as Opus 4.8. Injected via `ANTHROPIC_SYNTH_DATA` (now inject-when-absent / overlay-when-present).
  - **Gemini 3.6 Flash** (`gemini/gemini-3.6-flash`) — $1.50 / $7.50 per M, cache $0.15.
  - **Gemini 3.5 Flash-Lite** (`gemini/gemini-3.5-flash-lite`) — $0.30 / $2.50 per M, cache $0.03.
  - **Gemini 3.1 Flash-Lite Image** / Nano Banana 2 Lite (`gemini/gemini-3.1-flash-lite-image`) — image model: $0.25 in / $1.50 out text per M; images $30/M tokens ($0.0336/image).
- New `GOOGLE_SYNTH_DATA` + `apply_google_synth` injector wired into `filter_all_models` / `get_filter_stats` (first Google synth channel).
- Prices sourced from platform.claude.com and ai.google.dev/gemini-api/docs/pricing; context windows mirror the same-generation sibling (the pricing pages omit them). **Claude Mythos 5** is intentionally excluded — it is Project Glasswing invitation-only, not GA.

### v1.16.2 (2026-07-21)
- Align **all friendly names to each provider's own official naming** (not a single house style). `format_model_name` per-provider branches updated; 50 friendly names change, no other fields.
  - **Anthropic** — variant-first order per platform.claude.com: `Claude {ver} {Variant}` → **`Claude {Variant} {ver}`** (`Claude Sonnet 5`, `Claude Opus 4.7`, `Claude Haiku 4.5`). Dated snapshots now carry **no date suffix** — they share the base display name (`claude-sonnet-4-5-20250929` → `Claude Sonnet 4.5`). (Claude 3 used version-first; Anthropic switched the order at Claude 4.)
  - **OpenAI** — per openai.com: size suffixes `mini` / `nano` lowercase (`GPT-5 mini`, `GPT-5.4 nano`, `GPT-4o mini`); o-series shown as its lowercase id (`o3-mini`, `o4-mini`); `text-embedding-3-*` shown as the lowercase id; `gpt-5.3-codex` → **`GPT-5.3-Codex`** (hyphenated); dated realtime preview drops the snapshot (`gpt-4o-realtime-preview-2024-12-17` → **`GPT-4o Realtime`**, also fixing a date-split bug).
  - **Google** — per ai.google.dev: **`Flash-Lite`** hyphenated (was `Flash Lite`); **`Gemini Embedding 2`** (was lowercase `embedding`).
  - **Volcengine / new-api / ecloud_aicc** — Seedance now carries the official **`Doubao-`** brand prefix: `Seedance 2.0` → **`Doubao-Seedance 2.0`** (dated `-YYMMDD` still stripped).
  - **z.ai / bigmodel (GLM)** and **DeepSeek** — already matched their vendors' naming; unchanged.
- Net: friendly-name display only; no pricing, context, or capability fields touched.

### v1.16.1 (2026-07-15)
- Overlay **OpenAI-authoritative GPT-5 pricing** via new `OPENAI_SYNTH_DATA` + `apply_openai_synth` (chained at the head of the synth chain). BerriAI/main trailed OpenAI's July 2026 GPT-5 refresh, so the officially-published numbers are overlaid on top. Verified field-by-field against `developers.openai.com/api/docs/pricing` (Standard / Batch / Flex / Priority tabs) and cross-checked with the pinned `litellm-internal` `ship/v1.89.0` backup:
  - `gpt-5.5` **priority tier** corrected: `$10 / $1 / $60` → **`$12.50 / $1.25 / $75`** per M (input / cached-read / output)
  - `gpt-5.4-mini` & `gpt-5.4-nano` are **short-context only**: `max_input_tokens` `1,050,000` → **`272,000`**; plus the batch cached-read rate absent upstream
  - `gpt-5.6` / `gpt-5.6-sol` / `gpt-5.6-terra` / `gpt-5.6-luna` gain the **flex long-context (>272K) tier** (4 fields each)
  - `gpt-5.4` cached-read flex stays **`1.3e-07` ($0.13)** — that is OpenAI's own published figure (Flex/Batch tabs), not a rounding artefact
  - Backfill `supports_service_tier` and `regional_processing_uplift_multiplier_{eu,us}` where missing
- Overlay is **purely additive** (`{**existing, **synth}`) — richer upstream fields the project already carries (e.g. the `/v1/batch` endpoint on the 5.6 family) are preserved
- Net: no model-count change (114 total); pricing-only corrections to 13 GPT-5 SKUs

### v1.16.0 (2026-07-10)
- Add **ecloud_aicc** as the ninth supported provider — a second aggregator mirror alongside new-api (same mechanic, distinct namespace)
- `ECLOUD_AICC_ALLOWED_KEYS` reverse-whitelists 6 Seedance SKUs (standard / Fast / Mini × {dated official ID, date-less alias}), all mirrored from `volcengine/doubao-seedance-*`
- `ECLOUD_AICC_MIRROR_SOURCES` declares each mirror's source key; `apply_ecloud_aicc_synth` chained at the tail of the synth chain (after new-api synth) so sources are already populated
- Friendly-name Seedance branch generalised from 2-prefix to 3-prefix coverage (`volcengine/` | `new-api/` | `ecloud_aicc/`)
- Net effect: exported total 108 → 114 (+6 ecloud_aicc mirrors); no changes to existing providers
- Underscore-in-name is intentional (matches the ecloud_aicc gateway's own identifier spelling)

### v1.15.2 (2026-07-10)
- Sync **GPT-5.6 family** — 4 SKUs now flow through the existing openai whitelist with no rule changes:
  - `gpt-5.6` → `GPT-5.6` ($5 / $30 / $0.50 per M input / output / cache-read, 1M ctx, 128K max output)
  - `gpt-5.6-terra` → `GPT-5.6 Terra` ($2.5 / $15 / $0.25 per M, 1M ctx)
  - `gpt-5.6-luna` → `GPT-5.6 Luna` ($1 / $6 / $0.10 per M, 1M ctx)
  - `gpt-5.6-sol` → `GPT-5.6 Sol` ($5 / $30 / $0.50 per M, 1M ctx)
- All four are `mode=chat`, reasoning + vision + function-calling capable; served on `/v1/chat/completions`, `/v1/batch`, and `/v1/responses` per upstream
- Net: openai/language 24 → 28

### v1.15.1 (2026-07-08)
- Trim IEEE-754 float noise on Volcengine (and mirrored new-api) Seedance prices — all `output_cost_per_token[_<res>][_with_input_video]` fields now render as **4 significant digits** (e.g. `6.571e-06`) instead of the 15-digit division tails (`6.571428571428571e-06`)
- Reintroduce `_cny_per_m_to_usd_per_token(cny_per_m, sig=4)` helper (previously dropped in v1.9.0 when bigmodel switched to mirroring zai); `_VOLCENGINE_FX_RATE = 7.0` module constant makes the FX policy explicit
- Source CNY tariff values (`46`, `28`, `51`, ...) now visible directly in `VOLCENGINE_SYNTH_DATA` as helper arguments — reversible via `round(usd × 7.0 × 10⁶)`
- No pricing changes; new-api mirrors automatically inherit the cleaner values

### v1.15.0 (2026-07-07)
- Add **new-api** as the eighth supported provider — an **aggregator mirror**: `new-api/<sku>` entries are full copies of authoritative `<vendor>/<sku>` records with only `litellm_provider` re-labelled
- `NEWAPI_ALLOWED_KEYS` reverse-whitelists the first 6 mirrored SKUs — the full Seedance 2.0 set (standard / Fast / Mini × {dated official ID, date-less alias}), sourced from `volcengine/doubao-seedance-*`
- `NEWAPI_MIRROR_SOURCES` declares the source key for each mirror. `apply_newapi_synth` runs at the **head** of the synth chain (after every other vendor synth) so sources are already populated when it runs
- No duplicated tariff bookkeeping — Volcengine price changes propagate to new-api automatically on the next sync
- `format_model_name` unified branch: `volcengine/*` and `new-api/*` both format as `Seedance 2.0` / `Seedance 2.0 Fast` / `Seedance 2.0 Mini` (dated `-YYMMDD` stripped)
- Distinguishes the catalogue-layer `new-api/` mirror provider from the LiteLLM routing-layer `volcengine_new_api` label (see README's `#### Volcengine` section closing note)

### v1.14.0 (2026-07-01)
- Support **GPT-4.1 lineage** (`gpt-4.1`, `gpt-4.1-mini`, `gpt-4.1-nano`) — un-narrow `^gpt-4` pattern back to `^gpt-4($|-turbo|-32k|-\d)` (drops the `|\.` clause added in v1.13.0)
- Add **`responses` mode** to `SUPPORTED_MODES` and `MODE_MAPPING["responses"] = "language"` (OpenAI `/v1/responses` endpoint — codex / pro / deep-research families)
- Support **`gpt-5.3-codex`** (`responses` mode); render friendly name as `GPT-5.3 Codex`
- Extend `EXCLUDE_MODEL_KEYS` with the 12 responses-mode SKUs outside the sanctioned allow-list: `gpt-5-codex`, `gpt-5-pro`, `gpt-5.1-codex{,-max,-mini}`, `gpt-5.2-{codex,pro}`, `gpt-5.4-pro`, `gpt-5.5-pro`, `o3-deep-research`, `o3-pro`, `o4-mini-deep-research`
- Net effect: openai/language 20 → 24 (+3 GPT-4.1 + 1 GPT-5.3 Codex); zero unintended `responses` leaks

### v1.13.0 (2026-07-01)
- Add curated OpenAI **audio / realtime allow-list** (7 SKUs): `gpt-4o`, `gpt-4o-mini`, `gpt-realtime`, `gpt-4o-realtime-preview-2024-12-17`, `gpt-4o-mini-transcribe`, `gpt-4o-mini-tts`, `whisper-1`
- New model type **`audio`** covering two modes:
  - `audio_speech` (TTS) — validates `input_cost_per_token` / `output_cost_per_token` / `output_cost_per_audio_token` / `output_cost_per_second`
  - `audio_transcription` (ASR) — validates `input_cost_per_second` / `input_cost_per_audio_token` / `input_cost_per_token` (whisper-1 is per-second only; gpt-4o-*-transcribe uses token fields)
- Narrow `PROVIDER_EXCLUSION_RULES["openai"]` `^gpt-4` pattern to `^gpt-4($|-turbo|-32k|-\d|\.)` so the GPT-4o family passes provider filter; legacy `gpt-4 / gpt-4-turbo / gpt-4-32k / gpt-4-YYYY-MM-DD` and the `gpt-4.1` minor lineage stay excluded
- Extend `INCLUDE_PATTERNS` with exact-match entries for the 7 SKUs — needed to bypass `-preview-` / `date_pattern` / `^gpt-realtime` global excludes on the dated realtime preview and the `gpt-realtime` bare key
- Explicit `EXCLUDE_MODEL_KEYS` entries for `gpt-4o-transcribe` / `gpt-4o-transcribe-diarize` (upstream audio-transcription SKUs outside the sanctioned whitelist)
- `format_model_name` OpenAI branch: `\d+o$` heads (e.g. `4o`) keep lowercase `o` per OpenAI brand (`GPT-4o`, `GPT-4o Mini`); non-numeric heads (`gpt-realtime`) render as `GPT Realtime` (space, no dash); `tts` / `asr` segment overrides upcase the branded abbreviations

### v1.12.0 (2026-07-01)
- Support **Claude Sonnet 5** (`claude-sonnet-5`, 1M context / 128K max output) — auto-flows through the existing Anthropic whitelist; no rule changes needed
- Support **Claude Fable 5** (`claude-fable-5`, 1M context) — non-core variant with $10 / $50 / $1 tariff, whitelisted via the same anthropic-prefix rule
- Add `_CORE_CLAUDE_VARIANTS = {opus, sonnet, haiku}` and fix `format_model_name` so major-only core keys render as `Claude {ver} {Variant}` (e.g. `claude-sonnet-5` → **Claude 5 Sonnet**, matching `Claude 4.5 Sonnet` pattern); non-core variants keep their capitalized fallback (`claude-fable-5` → `Claude Fable 5`)
- Add `ANTHROPIC_SYNTH_DATA` + `apply_anthropic_synth` (time-boxed intro-price overlay). Currently patches `claude-sonnet-5` with the introductory tariff ($2 / $10 / $0.20 / $2.50 per M) in effect through 2026-08-31 per [claude.com/pricing](https://claude.com/pricing). **Remove this overlay on 2026-09-01** so upstream flows through unchanged
- `apply_anthropic_synth` chained at the tail of both `filter_all_models` and `get_filter_stats` (stats remain consistent with export)

### v1.11.0 (2026-06-30)
- Add **Volcengine** as the seventh supported provider via reverse-whitelist (`VOLCENGINE_ALLOWED_KEYS`)
- First **video** model type — `SUPPORTED_MODES` gains `video_generation`; `MODE_MAPPING` adds `video_generation → video`
- 6 active Seedance 2.0 SKUs (standard / Fast / Mini × {dated official ID, date-less alias}) sourced from [volcengine.com/docs/82379/1544106](https://www.volcengine.com/docs/82379/1544106)
- **Currency: USD/token** via the standard `output_cost_per_token[_<res>][_with_input_video]` family. Top-level `output_cost_per_token` carries the base 720p / no-input-video tier; resolution-suffixed (`_1080p`, `_4k`) and v2v-suffixed (`_with_input_video`) variants flow through under `raw_data`. The underlying CNY tariff is converted at a policy rate of `1 USD = 7.0 CNY` (mirrors the LiteLLM fork's `VOLCENGINE_FX_POLICY.md`)
- `PRICE_FIELDS_BY_MODE["video_generation"]` validates against the six USD tiers (720p / 1080p / 4K × {with, without} input video); any one non-zero tier passes the zero-price filter
- `format_model_name` volcengine branch outputs `Seedance 2.0` / `Seedance 2.0 Fast` / `Seedance 2.0 Mini` (strips the `-YYMMDD` version stamp)
- `is_default_available = false` for all video SKUs (same default-deny rule as image)
- `volcengine_new_api` (a LiteLLM routing-layer label for new-api relay deployments) is intentionally **not** a separate provider — the model catalogue exposes a single `volcengine/doubao-seedance-*` entry regardless of how deployments reach it

### v1.10.0 (2026-06-30)
- Add **DeepSeek** as the sixth supported provider via reverse-whitelist (`DEEPSEEK_ALLOWED_KEYS`)
- 2 active SKUs from [api-docs.deepseek.com/quick_start/pricing](https://api-docs.deepseek.com/quick_start/pricing/): `deepseek/deepseek-v4-flash`, `deepseek/deepseek-v4-pro`
- `DEEPSEEK_SYNTH_DATA` overlays `max_output_tokens=384000` (LiteLLM upstream reports `8192`; all other fields come from upstream unchanged)
- `format_model_name` deepseek branch outputs branded `DeepSeek-V4-Flash` / `DeepSeek-V4-Pro`
- `apply_deepseek_synth()` runs at the entry of both `filter_all_models` and `get_filter_stats` (stats remain consistent with export)
- Exclude `deepseek-chat` / `deepseek-reasoner` (scheduled deprecation 2026-07-24, currently V4-Flash aliases), `deepseek-v3` / `v3.2` / `r1` / `coder` (superseded, no longer on official pricing), and all bare-key forms

### v1.9.0 (2026-06-24)
- **Bigmodel pricing now mirrors z.ai international (USD)** 1:1 — `bigmodel/*` SKUs no longer derive prices from `bigmodel.cn` RMB tariffs
- Remove `CNY_USD_RATE` constant and `_cny_per_m_to_usd_per_token` helper (no longer used)
- Strip `input_cost_per_token` / `output_cost_per_token` / `cache_read_input_token_cost` from `BIGMODEL_SYNTH_DATA` entries; metadata-only entries remain
- `apply_bigmodel_synth` now copies price fields from the sibling `zai/<sku>` (after `apply_zai_synth` has merged z.ai overlays + LiteLLM upstream)
- Bigmodel SKUs without a sibling zai entry drop out via the zero-price filter, surfacing gaps explicitly

### v1.8.0 (2026-06-17)
- Add **GLM-5.2** on both `zai/` (international USD) and `bigmodel/` (domestic CNY) namespaces
- GLM-5.2 introduces **1M context** (`max_input_tokens: 1_000_000`) — first SKU in the GLM family with a 1M window
- z.ai pricing matches GLM-5.1 exactly (input $1.4 / output $4.4 / cached $0.26 per M tokens); bigmodel.cn uses single-tier pricing for 5.2 (input ¥8 / output ¥28 / cache_read ¥2), no tier compression needed
- Pre-staged on both sides (LiteLLM upstream not yet carrying 5.2); SYNTH_DATA injects wholesale

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

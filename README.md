# SaaS Models Source

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

A comprehensive tool for filtering and syncing AI model data from LiteLLM, designed for SaaS applications that need up-to-date model information.

## Features

- **Multi-Provider Support**: Filters models from OpenAI, Anthropic, Google, Z.AI (GLM international), Bigmodel (智谱开放平台, GLM domestic), DeepSeek, Moonshot (Kimi), DashScope (阿里云百炼 / Alibaba Cloud Model Studio — Qwen), Volcengine (ByteDance Ark domestic — Doubao Seedance video), BytePlus (ByteDance Ark overseas — Dreamina Seedance video), and two aggregator mirrors: new-api and ecloud_aicc
- **Multi-Modal Support**: Chat (language), embedding, image generation, video generation, and audio (speech / transcription) models
- **Smart Filtering Rules**: Comprehensive exclusion rules for deprecated, preview, and versioned models
- **Mode-Aware Price Validation**: Validates pricing using mode-specific fields (per-token, per-image-token, per-image)
- **Flexible Output**: JSON export ready for database synchronization
- **Detailed Statistics**: Track filtering metrics and exclusion reasons with full consistency between `stats.passed` and exported count

## Supported Providers

- **OpenAI**: GPT-6 Astra, GPT-5 series, o3/o4 series, text-embedding models, `gpt-image-*` series, plus a curated audio / realtime allow-list (`gpt-4o`, `gpt-4o-mini`, `gpt-realtime`, `gpt-4o-realtime-preview-2024-12-17`, `gpt-4o-mini-transcribe`, `gpt-4o-mini-tts`, `tts-1`, `tts-1-hd`, `whisper-1`)
- **Anthropic**: Claude 4.5+ series (Haiku, Sonnet, Opus), the Claude 5 flagships (Opus 5, Sonnet 5) and the Fable / Mythos 5.1 pair, including dated snapshots
- **Google**: Gemini 2.5+ series (Flash, Flash-Lite, Pro), Gemini Embedding 2, `gemini-*-image*` series
- **Z.AI (GLM, international)**: Whitelist-curated `zai/glm-*` SKUs with z.ai-authoritative data overlay (GLM-4.5/4.6/4.7/5/5.1/5.2/5.3 family, including the natively-multimodal GLM-5.3-Flash, + vision/OCR variants), priced in USD
- **Bigmodel (智谱开放平台, GLM domestic gateway)**: Whitelist-curated `bigmodel/glm-*` SKUs that mirror sibling `zai/*` USD pricing 1:1 (13 SKUs: GLM-5.3-Flash, GLM-5.3, GLM-5.2, GLM-5.1, GLM-5, GLM-5-Turbo, GLM-5V-Turbo, GLM-4.7, GLM-4.7-FlashX, GLM-4.6V, GLM-4.6V-FlashX, GLM-4.5-Air, GLM-4.5V)
- **DeepSeek**: Whitelist-curated active SKUs from `api-docs.deepseek.com/quick_start/pricing` (3 SKUs: DeepSeek-V4-Flash, DeepSeek-V4-Flash-Vision-Exp, DeepSeek-V4-Pro — 1M context, 393,216 max output). The official tariff is **USD-native** and split into peak / off-peak windows; we carry the **peak** rate, straight from upstream with no overlay
- **Moonshot (Kimi)**: Whitelist-curated SKUs from `platform.kimi.ai/docs` (3 SKUs: Kimi K3 — $3 / $15 per M, cache-hit $0.30, 1M context; Kimi K2.7 Code — $0.95 / $4.00, cache-hit $0.19, 256K; Kimi K2.7 Code HighSpeed — $1.90 / $8.00, cache-hit $0.38, 256K). Pre-staged via `MOONSHOT_SYNTH_DATA` (injected — not yet on LiteLLM upstream)
- **DashScope (阿里云百炼 / Alibaba Cloud Model Studio, Qwen)**: Whitelist-curated `dashscope/*` SKUs (6 SKUs — the Qwen **3.8** and **3.7** generations, all ~1M context). Prices are the **effective (post-discount)** ones from [qwencloud.com/pricing/api](https://www.qwencloud.com/pricing/api); `qwen3.7-plus` / `qwen3.7-flash` are **tiered by request input size**. *DashScope* is the API/SDK identifier (`dashscope.aliyuncs.com`, `DASHSCOPE_API_KEY`) for the service branded 百炼 / Model Studio — LiteLLM names the provider after the technical id, and using the same namespace means an upstream key of the same name merges instead of colliding. **Unrelated to ModelScope (魔搭)**, which is Alibaba's open-weights community hub. Prices are the **International USD** tariff (the domestic 百炼 CNY book is separate and deliberately not mixed in)
- **Volcengine (ByteDance Ark, Doubao Seedance video)**: Whitelist-curated Seedance 2.0 + 2.5 video SKUs from [volcengine.com/docs/82379/1544106](https://www.volcengine.com/docs/82379/1544106) (8 entries: 2.0 standard / Fast / Mini × {dated + alias}, plus Seedance 2.5 {dated `-260628` + alias} — 480P/720P 70 / 42 CNY/M no-video / with-video, 1080P 77 / 46 CNY/M, 4K 39 / 24 CNY/M *estimated*). Prices stored as **USD/token** via the standard `output_cost_per_token[_<res>][_with_input_video]` family — the underlying CNY tariff has been converted at our internal LiteLLM fork's policy FX rate (`1 USD = 7.0 CNY`); the LiteLLM billing manager bills in USD with no runtime FX lookup
- **BytePlus (ByteDance Ark overseas, Dreamina Seedance video)**: Whitelist-curated Dreamina Seedance 2.0 + 2.5 video SKUs from [docs.byteplus.com/en/docs/ModelArk/1544106](https://docs.byteplus.com/en/docs/ModelArk/1544106) (8 entries: 2.0 standard / Fast / Mini + 2.5, each × {dated + alias}). BytePlus is the overseas sibling of Volcengine — same Ark platform, same YYMMDD version stamps — but a different brand and a **USD-native tariff**, so these are independent SKUs, *not* mirrors of `volcengine/*`. List prices in USD/M tokens (no-video / with-video): 2.5 — 480P/720P **10.70 / 6.40**, 1080P **11.70 / 7.00**, 4K **6.08 / 3.57** *estimated*; 2.0 — 480P/720P **7.00 / 4.30**, 1080P **7.70 / 4.70**, 4K **4.00 / 2.40**; 2.0 Fast — **5.60 / 3.30**; 2.0 Mini — **3.50 / 2.10**. Same `output_cost_per_token[_<res>][_with_input_video]` field family as Volcengine, but **no FX conversion is applied**
- **new-api (aggregator gateway)**: Reverse-whitelist mirror provider. Every `new-api/<sku>` is a full copy of an already-populated `<vendor>/<sku>` record with only `litellm_provider` re-labelled. Seedance is the first family mirrored (8 SKUs from `volcengine/doubao-seedance-*`); extending to more vendors is a two-line change (whitelist entry + `NEWAPI_MIRROR_SOURCES` mapping)
- **ecloud_aicc (aggregator gateway)**: Second mirror provider — same mechanic as new-api, distinct namespace so deployments routing through the ecloud_aicc gateway can address SKUs by their aggregator-side name. Currently mirrors the same 8 Seedance SKUs from `volcengine/doubao-seedance-*`

## Supported Model Types

| Type | Mode | Examples |
|------|------|----------|
| `language` | `chat` | `claude-opus-4-7`, `gpt-5.5`, `gemini/gemini-3-pro-preview`, `zai/glm-5`, `bigmodel/glm-5`, `deepseek/deepseek-v4-flash`, `dashscope/qwen3.8-flash` |
| `embedding` | `embedding` | `text-embedding-3-large`, `gemini/gemini-embedding-2` |
| `image` | `image_generation` | `gpt-image-1.5`, `gemini/gemini-2.5-flash-image` |
| `video` | `video_generation` | `volcengine/doubao-seedance-2-0`, `byteplus/dreamina-seedance-2-5`, `new-api/doubao-seedance-2-0-fast`, `ecloud_aicc/doubao-seedance-2-0-mini` |
| `audio` | `audio_speech`, `audio_transcription` | `gpt-4o-mini-tts` / `tts-1` / `tts-1-hd` (TTS), `gpt-4o-mini-transcribe` / `whisper-1` (ASR) |

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
- ✅ Include (audio / realtime allow-list, exact match via `INCLUDE_PATTERNS`): `gpt-4o`, `gpt-4o-mini`, `gpt-realtime`, `gpt-4o-realtime-preview-2024-12-17`, `gpt-4o-mini-transcribe`, `gpt-4o-mini-tts`, `tts-1`, `tts-1-hd`, `whisper-1`
- ✅ Supports **audio_speech** (TTS) and **audio_transcription** (ASR) modes — `PRICE_FIELDS_BY_MODE` accepts per-token, per-second, or per-character billing (whisper-1 uses `input_cost_per_second`; gpt-4o-*-transcribe/tts use `input_cost_per_token` + `output_cost_per_audio_token`; `tts-1` / `tts-1-hd` use `output_cost_per_character`). Standalone `tts-1` / `tts-1-hd` render as their lowercase id, per OpenAI's utility-model style
- ✅ Include GPT-4.1 lineage: `gpt-4.1`, `gpt-4.1-mini`, `gpt-4.1-nano` (passes narrowed `^gpt-4` pattern)
- ✅ Supports `responses` mode (OpenAI's `/v1/responses` endpoint — used by codex, gpt-*-pro, deep-research families). `MODE_MAPPING["responses"] = "language"`. Only `gpt-5.3-codex` is whitelisted; wider codex / pro / deep-research variants stay excluded (see below)
- ✅ Supports `realtime` mode (OpenAI's `/v1/realtime` endpoint). LiteLLM re-classified these SKUs out of `chat` in 2026-08; `MODE_MAPPING["realtime"] = "language"` keeps them where downstream already had them. `PRICE_FIELDS_BY_MODE["realtime"]` accepts any of the four billing axes (text in/out, audio in/out) plus `input_cost_per_image`. Only the two allow-listed keys pass; the wider `gpt-realtime-*` family stays excluded via `EXCLUDE_PATTERNS`
- ❌ Exclude: GPT-4 legacy (`gpt-4`, `gpt-4-turbo`, `gpt-4-32k`, `gpt-4-YYYY-MM-DD`) — narrowed pattern preserves GPT-4o and 4.1 families
- ❌ Exclude: o1 series, ada embedding models
- ❌ Exclude: `dall-e-*`, `chatgpt-image-*` (legacy image models)
- ❌ Exclude via `EXCLUDE_MODEL_KEYS` (outside sanctioned allow-lists):
  - audio: `gpt-4o-transcribe`, `gpt-4o-transcribe-diarize`, `gpt-transcribe`, `gpt-live-transcribe` (the 2026-08 generation dropped the `4o` infix; same narrow-scope policy)
  - responses: `gpt-5-codex`, `gpt-5-pro`, `gpt-5.1-codex`, `gpt-5.1-codex-max`, `gpt-5.1-codex-mini`, `gpt-5.2-codex`, `gpt-5.2-pro`, `gpt-5.4-pro`, `gpt-5.5-pro`, `o3-deep-research`, `o3-pro`, `o4-mini-deep-research`
- ❌ Exclude: Models with `openai/` prefix, search-api variants
- ✅ Friendly name follows OpenAI's own house style: size suffixes `mini` / `nano` stay **lowercase** (`GPT-5 mini`, `GPT-5.4 nano`, `GPT-4o mini`); `GPT-4o` keeps the lowercase branded `o`; the o-series is shown as its lowercase id (`o3`, `o3-mini`, `o4-mini`); `text-embedding-3-*` is shown as the lowercase id; `gpt-5.3-codex` → `GPT-5.3-Codex` (hyphenated); dated realtime preview drops the snapshot (`gpt-4o-realtime-preview-2024-12-17` → `GPT-4o Realtime`); `GPT Realtime` uses a spaced form; segment overrides upcase `TTS` / `ASR`

#### Anthropic
- ✅ Include: Claude 4.5+ variants (Haiku, Sonnet, Opus), plus Claude 5 (Sonnet, Opus), plus special-name flagships (`claude-fable-5`, `claude-fable-5-1`, `claude-mythos-5`, `claude-mythos-5-1`)
- ⚠️ **The 5.1 pair has a different cache ratio.** `claude-fable-5-1` / `claude-mythos-5-1` bill cache reads at **0.025x** base input ($0.25 against $10), not the usual 0.1x that `claude-fable-5` / `claude-mythos-5` pay ($1). The pricing-page footnote states it explicitly: *"0.1x base input price (0.025x on Claude Fable 5.1 and Claude Mythos 5.1)"*. Do not assume one ratio across the family
- ✅ Mythos SKUs are **pre-staged** via `ANTHROPIC_SYNTH_DATA` — Project Glasswing is limited-availability and BerriAI upstream does not carry `claude-mythos-5` or `claude-mythos-5-1`. Their Fable twins do come from upstream
- ✅ Include: Dated snapshots ≥ 4.5 (e.g. `claude-sonnet-4-5-20250929`)
- ✅ **Introductory-price overlay** via `ANTHROPIC_SYNTH_DATA` / `apply_anthropic_synth`: when Anthropic runs a time-boxed intro price, LiteLLM upstream tracks the post-window standard tariff — we overlay the currently-effective numbers so the catalogue matches what customers actually get billed today
  - **No price overlay is active.** `ANTHROPIC_SYNTH_DATA` currently holds only pre-staged *entries* (`claude-opus-5`, `claude-mythos-5`), not price corrections
  - The `claude-sonnet-5` introductory overlay was **retired on 2026-09-01** — and not because the window closed. Anthropic cancelled the increase: *"The $2/$10 per million input/output token pricing for Claude Sonnet 5, announced at launch as introductory pricing through August 31, 2026, is now the standard price. The previously scheduled increase to $3/$15 per million input/output tokens on September 1, 2026 will not occur."* Upstream carries the permanent rate verbatim, so the overlay had become a no-op and was deleted
  - ⚠️ **Delete an overlay once upstream catches up.** A redundant overlay is not harmless — it silently pins values the moment the vendor moves next. That is exactly how the `gpt-5.6` `*_above_272k_flex` overlays came to bill flex long-context output at $22.50/M against a real $15/M (see v1.16.18)
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
- ❌ Exclude (special-purpose / non-conversational, via `EXCLUDE_MODEL_KEYS`): `gemini/gemini-3.1-pro-preview-customtools`, `gemini/gemini-3.1-flash-live-preview`, `gemini/gemini-3.1-flash-tts-preview`, `gemini/gemini-3.5-live-translate-preview`, `gemini/gemini-3.5-transcribe`, `gemini/gemini-3.5-transcribe-live`. The Google scope is Gemini 2.5+ **chat**, Gemini Embedding, and `gemini-*-image*` — audio is not in it. These keys only reach the filter because the `^gemini/gemini-[3-9].*-preview$` include pattern (written to admit 3.x *chat* previews) is broader than its intent, so keeping them out is a scope decision rather than a data problem. Remove an entry here if the product scope widens to Gemini speech. The 2026-09 transcribe pair carries **no** `-preview` suffix, so nothing else keeps it out — without an explicit entry it enters the export on the next regeneration.
- ⏸️ **Deferred, not rejected:** `gemini/gemini-omni-1.1-flash`. ai.google.dev calls it *"our next-generation video generation and editing model"*, but upstream classifies it as `mode: chat` carrying only the $1.50 in / $9.00 out **text** rates. The published tariff has a second output tier — **$17.50 per M for video output** (5,792 tokens per second of 720p, ~$0.10/s) — which that shape cannot express, so importing it as chat would under-bill video output by roughly half. Admit it once the mode and the video output tier are modelled

#### Z.AI
- ✅ Include: only keys listed in `ModelSyncRules.ZAI_ALLOWED_KEYS` (reverse whitelist)
- ✅ **z.ai as source of truth** via `ZAI_SYNTH_DATA` overlay (sourced from [docs.z.ai/guides/overview/overview](https://docs.z.ai/guides/overview/overview) + [pricing](https://docs.z.ai/guides/overview/pricing)):
  - Pre-staged SKUs absent from LiteLLM are synthesised from z.ai data (GLM-5.3-Flash, GLM-5.2, GLM-5.1, GLM-5-Turbo, GLM-4.7-FlashX, GLM-5V-Turbo, GLM-4.6V, GLM-4.6V-FlashX, GLM-OCR)
  - When upstream conflicts with z.ai, z.ai wins (e.g. `zai/glm-4.5v` context = 64K per z.ai overview, not the 128K LiteLLM reports)
- ✅ Vision flag auto-inferred for keys matching `glm-*v` or `glm-ocr` when upstream omits `supports_vision`. **`zai/glm-5.3-flash` is the exception**: it is natively multimodal but its key has no `v` infix, so `_GLM_VISION_KEY` does not match it — `supports_vision: True` is set explicitly in `ZAI_SYNTH_DATA` instead
- ⏳ **`zai/glm-5.3-flash` carries a promotional price.** z.ai runs a flat **50% discount** on it until **24:00 on 2026-09-09 (UTC+8)**: list $0.15 / $0.03 / $0.50 per M (input / cached / output), effective **$0.075 / $0.015 / $0.25**. The discount is **unconditional** — every caller gets it — so the catalogue stores the effective rate, matching how `ANTHROPIC_SYNTH_DATA` handles introductory pricing. This deliberately differs from `BYTEPLUS_SYNTH_DATA`, which stores *list* because those campaigns are gated on account balance / savings-plan tier and so are not universal. **Revert to list on 2026-09-10** (`input` 1.5e-07, `cache_read` 3e-08, `output` 5e-07) — the code carries the same reminder
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

#### DashScope (阿里云百炼 / Alibaba Cloud Model Studio — Qwen)
- ✅ Include: only keys listed in `ModelSyncRules.DASHSCOPE_ALLOWED_KEYS` (reverse whitelist, 1 SKU today). Upstream carries 45 `dashscope/*` keys — Qwen plus third-party models resold through Model Studio — so the whitelist is what keeps the catalogue narrow
- ✅ **Namespace rationale.** *DashScope* is the API/SDK identifier (`dashscope.aliyuncs.com`, the `dashscope` SDK, `DASHSCOPE_API_KEY`); *百炼 / Model Studio* is the product brand for the same service. Verified 2026-08-29: all 45 upstream keys use `litellm_provider: "dashscope"` **and** the `dashscope/` prefix, with no competing `bailian` / `alibaba` / `aliyun` label. Matching it means an upstream key of the same name merges cleanly rather than colliding with an invented namespace. **Not** ModelScope (魔搭), which is Alibaba's open-weights hub and has no upstream provider label at all
- ✅ **Currency: International USD, native**, sourced from [qwencloud.com/pricing/api](https://www.qwencloud.com/pricing/api). Alibaba publishes two separate books — domestic 百炼 in CNY and International in USD — and upstream's `dashscope/*` prices are the USD ones (`dashscope/qwen3.8-max` is `$2 / $6` upstream while 百炼 lists `12 / 36` CNY, which is *not* 12÷7). We match that convention. **Do not** route these through `_cny_per_m_to_usd_per_token`
- ✅ Scope is the Qwen **3.8** and **3.7** generations. All prices are the **effective (post-discount)** ones — what a caller is billed today:

  | Key | Input tier | Input | Output | Implicit cache | Ctx / out | Vision |
  |---|---|---|---|---|---|---|
  | `qwen3.8-flash` | — | $0.15 | $0.47 | $0.016 | 991,808 / 131,072 | ✅ |
  | `qwen3.8-max` | — | $2 | $6 | $0.25 | 991,808 / 131,072 | ✅ |
  | `qwen3.8-2.4t-a95b` | — | $2 | $6 | $0.25 | 991,808 / 131,072 | ✅ |
  | `qwen3.7-max` | — | $1.25 *(50% off $2.5)* | $3.75 *($7.5)* | $0.25 *($0.5)* | 991,808 / 65,536 | ❌ |
  | `qwen3.7-plus` | ≤256K | $0.32 *(20% off $0.4)* | $1.28 *($1.6)* | $0.064 *($0.08)* | 991,808 / 65,536 | ✅ |
  | | 256K–1M | $0.96 *($1.2)* | $3.84 *($4.8)* | $0.192 *($0.24)* | | |
  | `qwen3.7-flash` | ≤32K | $0.03 | $0.13 | $0.006 | 991,808 / 65,536 | ✅ |
  | | 32K–256K | $0.1 | $0.4 | $0.02 | | |
  | | 256K–1M | $0.2 | $0.8 | $0.04 | | |

- ✅ **Tiered pricing (阶梯计价).** `qwen3.7-plus` and `qwen3.7-flash` bill at a unit price set by the request's total input size. Both representations are written: `tiered_pricing` carries the whole ladder (upstream's `range` + per-tier costs, extended with a per-tier `cache_read_input_token_cost` because qwencloud publishes one), and the flat `input_cost_per_token` family is set to the **highest tier**. A consumer that ignores the ladder then over-bills — visible, and the customer complains — rather than under-billing silently. Same never-under-bill rule as the DeepSeek peak tariff and the BytePlus list price
- ✅ `should_exclude_due_to_price` now recognises `tiered_pricing` via `_has_tiered_price()`, so an upstream-only tiered entry is no longer dropped as "zero price" — that bug is why upstream's own `dashscope/qwen-flash` never reached the export despite being priced
- ⚠️ **Discounts have no published end date.** Unlike the GLM-5.3-Flash overlay (which carries a 2026-09-09 deadline), qwencloud shows only strikethrough-list + live-price with no expiry, so there is no date to schedule a revert against. Each affected entry records its list price inline, making the restore a copy-paste when the promotion lapses

- ✅ `dashscope/qwen3.8-max` is **whitelisted only, with no synth entry** — upstream already carries it and its prices were checked field by field against qwencloud on 2026-08-29 (`$2 / $6 / $0.25`, exact match). Adding a synth entry would only create a second place to keep in sync
- ⚠️ **Cache prices are read from the published table, never derived.** The implicit-cache ratio varies per model *and* per currency: `qwen3.8-flash` is $0.016 against $0.15 (10.7%) while `qwen3.8-max` is $0.25 against $2 (12.5%), and the CNY book differs again (`qwen3.8-flash` ¥0.1 against ¥0.8 = 12.5%). The Context Cache doc's *"typically 10% explicit / 20% implicit"* is a rule of thumb, not a tariff — do not compute cache prices from it
- ❌ Exclude **3.6 and older**: `qwen3.6-max-preview` and earlier remain out of scope. `qwen3.8-flash-next` is also excluded — it is an open-weights release on ModelScope / HuggingFace, absent from every Model Studio pricing table, so not a billable SKU
- ✅ **Cache-hit rate is the implicit-cache one.** Model Studio runs two cache modes at different rates: explicit hits bill at ~10% of standard input, implicit at ~20%. Implicit is automatic and *cannot be disabled*, so 20% (**$0.03/M**) is what an unconfigured caller actually pays — and being the higher of the two it never under-bills. Deployments that opt into explicit caching get $0.015/M
- ✅ `supports_vision: true` — confirmed on the official vision docs, which put it in the **top** image-input tier: *"Qwen3.8-Max, Qwen3.8-Flash, Qwen3.7-Plus series: Up to 2,048 images"* (vs 256 for Qwen3.7-Flash and older). ⚠️ Do **not** infer capabilities from the "选择模型 / Recommended models" page — each category there is a curated shortlist ending in 查看更多 / More, so absence from it proves nothing
- ⚠️ `max_output_tokens` (32,768) is **inferred** from the upstream flash-tier sibling `dashscope/qwen-flash`; Alibaba's per-model spec page sits behind a console SPA that could not be read. Correct it if the published figure differs
- ❌ Exclude: `qwen3.8-flash-next` and other open-weights releases — those live on ModelScope / HuggingFace and are not billable Model Studio SKUs (they carry no price and would fail the Zero Price rule anyway)
- ❌ Exclude: every other `dashscope/*` key upstream carries; whitelist is exhaustive

#### Volcengine (ByteDance Ark — Doubao Seedance video)
- ✅ Include: only keys listed in `ModelSyncRules.VOLCENGINE_ALLOWED_KEYS` (reverse whitelist, 8 SKUs: Seedance 2.0 / Fast / Mini × {dated official ID, date-less alias}, plus Seedance 2.5 {dated + alias})
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

#### BytePlus (ByteDance Ark overseas — Dreamina Seedance video)
- ✅ Include: only keys listed in `ModelSyncRules.BYTEPLUS_ALLOWED_KEYS` (reverse whitelist, 8 SKUs: Dreamina Seedance 2.5 / 2.0 / 2.0 Fast / 2.0 Mini × {dated official ID, date-less alias})
- ✅ **Currency: USD/token, native.** BytePlus publishes USD per million tokens directly, so `_usd_per_m_to_usd_per_token()` is a plain `/1e6` with the same 4-significant-digit rounding. **Do not route these through `_cny_per_m_to_usd_per_token()`** — there is no FX step, and the overseas list prices are ~6–8% above the CNY-derived domestic equivalents (2.0 480P/720P: $7.00 overseas vs 46 CNY → $6.571 domestic), so the two tariffs are genuinely different numbers rather than one converted into the other.
- ✅ **Independent SKUs, not mirrors.** Unlike `new-api/*` and `ecloud_aicc/*`, `byteplus/*` entries carry their own tariff and have no `*_MIRROR_SOURCES` mapping. Same `output_cost_per_token[_<res>][_with_input_video]` field family as Volcengine.
- ✅ **List price, not the promotional price.** BytePlus runs limited-time campaigns ([docs.byteplus.com/en/docs/ModelArk/2630943](https://docs.byteplus.com/en/docs/ModelArk/2630943)) where *"N% of the list price"* means **pay N%**: Seedance 2.5 1080P at 72% until 2026-09-17, 2.0 Fast at 75% and 2.0 Mini at 40% until 2026-09-07. These discounts are **conditional** — pay-as-you-go only, prepaid resource packs excluded, and they require an account balance or AI Savings Plan at the USD 30 tier — so they are not a universal price. Storing list never under-bills and needs no revert when a campaign lapses. (Contrast `ANTHROPIC_SYNTH_DATA`, which *does* carry effective introductory prices — that discount is unconditional.)
- ✅ Pre-staged via `BYTEPLUS_SYNTH_DATA` + `apply_byteplus_synth` (injected wholesale — LiteLLM upstream carries **no** Seedance keys at all, domestic or overseas)
- ✅ 4K is officially priced for Seedance **2.0** ($4.00 / $2.40) but **absent for 2.5** — same shape as the domestic table. The 2.5 4K tier is therefore an **estimate** on both sides: **$6.08 / $3.57**, derived the same way as the domestic one (v1.16.12) by scaling 2.5's 1080P by the 2.0 4K:1080P ratio — `11.70 × (4.00 / 7.70) = 6.08`, `7.00 × (2.40 / 4.70) = 3.57` — computed entirely inside the overseas USD price set so no FX or cross-catalogue mixing enters. Replace with the official rate once BytePlus publishes a 2.5 4K tier.
- ✅ `input_cost_per_token` is `null` and `is_default_available = false`, same as every video SKU
- ❌ Exclude: any other `byteplus/*` SKU upstream may add (the page also lists `seedance-1-5-pro-251215`, `seedance-1-0-pro-250528`, `seedance-1-0-pro-fast-251015`, and non-Seedance families); whitelist is exhaustive

> **The date-less aliases are a project convention here, not vendor-registered IDs.** Verified 2026-08-21: neither the BytePlus Model list ([1330310](https://docs.byteplus.com/en/docs/ModelArk/1330310)) nor its domestic Volcengine counterpart publishes non-dated Seedance IDs — both list only the YYMMDD-stamped forms. The alias entries exist so `byteplus/*` matches the shape downstream consumers already use for `volcengine/*`, and they carry **identical pricing** to their dated twin. The "pick one form per environment" warning in the Volcengine section applies here too.

#### new-api (aggregator mirror provider)
- ✅ Include: only keys listed in `ModelSyncRules.NEWAPI_ALLOWED_KEYS` (reverse whitelist, 8 SKUs today — all Seedance)
- ✅ **Source of truth: `NEWAPI_MIRROR_SOURCES`** maps each `new-api/<sku>` to its authoritative source key (currently `volcengine/doubao-seedance-*`). `apply_newapi_synth` runs *after* every other vendor synth so those sources are already populated; each new-api entry is a full copy of its source's raw record with only `litellm_provider` re-labelled to `"new-api"`
- ✅ Prices, context, capabilities, and modes stay in **lock-step** with the source — Volcengine tariff change → new-api mirror updates on the next sync, no manual work
- ✅ Missing sources fail silently (the mirror is skipped, its whitelist entry then drops via unsupported-provider / zero-price) — surfaces gaps instead of exporting stale duplicates
- ✅ Adding a new mirrored SKU is a two-line change: append `new-api/<sku>` to `NEWAPI_ALLOWED_KEYS` and add a `NEWAPI_MIRROR_SOURCES[...]` mapping row
- ❌ Exclude: any `new-api/<sku>` without a matching whitelist entry
- ❌ Exclude: `new-api/<sku>` whose source key isn't present in the merged catalogue after all other synths run

#### ecloud_aicc (aggregator mirror provider)
- ✅ Include: only keys listed in `ModelSyncRules.ECLOUD_AICC_ALLOWED_KEYS` (reverse whitelist, 8 SKUs today — all Seedance)
- ✅ **Same mirror mechanic as `new-api`**: `ECLOUD_AICC_MIRROR_SOURCES` maps each `ecloud_aicc/<sku>` to its authoritative source key (currently `volcengine/doubao-seedance-*`). `apply_ecloud_aicc_synth` runs at the tail of the synth chain — every source is already populated by the time it runs
- ✅ Prices / context / capabilities / mode stay in lock-step with the source (Volcengine tariff change → both `new-api/*` and `ecloud_aicc/*` refresh on next sync)
- ✅ Underscore-in-name is intentional (matches how the ecloud_aicc gateway spells its own provider identifier); the friendly-name Seedance branch handles the prefix alongside `volcengine/` and `new-api/`
- ✅ Extending: append a whitelist entry AND an `ECLOUD_AICC_MIRROR_SOURCES` row pointing at the source key (two lines)
- ❌ Exclude: any `ecloud_aicc/<sku>` without a matching whitelist entry
- ❌ Exclude: `ecloud_aicc/<sku>` whose source key isn't present in the merged catalogue after all other synths run

#### DeepSeek
- ✅ Include: only keys listed in `ModelSyncRules.DEEPSEEK_ALLOWED_KEYS` (reverse whitelist, 3 SKUs — the whole V4 series)
- ✅ **Official DeepSeek pricing page as source of truth** ([api-docs.deepseek.com/quick_start/pricing](https://api-docs.deepseek.com/quick_start/pricing/), verified live 2026-09-04):
  - **No overlay.** LiteLLM upstream now carries every field of the official table verbatim — prices, `max_input_tokens` `1000000`, `max_output_tokens` `393216`, `supports_vision`. `DEEPSEEK_SYNTH_DATA` / `apply_deepseek_synth` were retired in v1.16.23; see the changelog for why keeping them was actively mis-billing
  - ✅ **Currency: USD, native.** The official page is denominated in USD, so nothing goes through `_cny_per_m_to_usd_per_token`. DeepSeek's own implied FX (6.818) is *not* our `7.0` policy rate — deriving USD from the CNY book under-bills by ~2.7%
  - **Peak-hour tariff is what we carry.** DeepSeek halves every rate outside `01:00–04:00` / `06:00–10:00` UTC, Mon–Fri; LiteLLM has no time-of-day price axis, so the peak (ceiling) rate is stored and off-peak is exactly `0.5x` of it. Peak USD/M — V4-Flash and V4-Flash-Vision-Exp `$0.44` in (cache-miss) / `$0.014` in (cache-hit) / `$1.32` out; V4-Pro `$1.32` / `$0.044` / `$3.96`. Cache writes are free
  - `deepseek-v4-flash-vision-exp` shares V4-Flash's tariff and limits exactly; it adds image input (billed as input tokens by image dimension) and drops FIM Completion
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

### v1.16.23 (2026-09-04)
- Add **`deepseek/deepseek-v4-flash-vision-exp`** — the vision-capable sibling of V4-Flash, listed on the official [Model Details](https://api-docs.deepseek.com/quick_start/pricing/) table alongside V4-Flash and V4-Pro. Identical tariff and limits to V4-Flash (**$0.44 / $1.32** per M, cache-hit **$0.014**, 1M context / 393,216 max output); adds image input (converted to input tokens by image dimension) and drops FIM Completion. Upstream carries it complete, including `supports_vision: true`, so the whitelist entry was the only code needed. Exported total **154 → 155**.
- 🔴 **Retire `DEEPSEEK_SYNTH_DATA` / `apply_deepseek_synth` — the overlay had gone from redundant to wrong in two directions.** It was written when upstream trailed the 2026-08 tariff and pinned `max_output_tokens` at `8192`. Upstream has since caught up on both, and re-reading the official page live today showed the overlay was mis-stating every V4 SKU:

  | | Overlay (before) | Official / upstream (after) | Effect |
  |---|---|---|---|
  | V4-Flash input | $0.4286 /M | **$0.44** /M | under-billed 2.7% |
  | V4-Flash output | $1.286 /M | **$1.32** /M | under-billed 2.7% |
  | V4-Pro input / output | $1.286 / $3.857 | **$1.32 / $3.96** | under-billed 2.7% |
  | `max_output_tokens` | `384000` | **`393216`** | wrong by 9,216 tokens |

- 💱 **Root cause of the price gap: the official page is denominated in USD, and we were deriving USD from the CNY book at our own policy rate.** DeepSeek's implied FX is **6.818**, not our `7.0`. This is the same failure as the Qwen cache-price episode — *read the vendor's published value; do not derive it from a ratio or a rate we chose.* `_cny_per_m_to_usd_per_token` is now documented as applying only to vendors that publish CNY **and no USD book** (Volcengine Seedance is the last one).
- 📏 Root cause of the context gap: `384000` was a decimal reading of the page's "MAXIMUM: 384K". The API takes **384 × 1024 = 393,216**, which upstream had right all along.
- ♻️ Third overlay to rot this way, after the `gpt-5.6` flex entries (v1.16.18) and the `claude-sonnet-5` introductory entry (v1.16.20). The rule stands: **delete an overlay once upstream catches up.** DeepSeek now flows through untouched.
- ✅ Peak-vs-off-peak policy is unchanged and still needs no overlay: upstream carries the **peak** rate (the ceiling, so we never under-bill), and off-peak is exactly `0.5x`. Corrected the documented window to the official `01:00–04:00` / `06:00–10:00` **UTC**, Mon–Fri.

### v1.16.22 (2026-09-04)
- Add **`gemini/gemini-3.8-flash`** — Gemini 3.8 Flash, Google's most capable Flash model: **$0.75 / $3.75** per M, cache **$0.075**, 1,048,576 context / 65,536 output, vision. Upstream data matches [ai.google.dev pricing](https://ai.google.dev/gemini-api/docs/pricing) exactly, so **no synth entry was needed** — only a regeneration. Exported total **153 → 154**.
- ⏳ **Scheduled increase on 2027-01-01.** Google publishes the current rate as time-boxed: *"$0.75 through December 31, 2026. $1.50 starting January 1, 2027"*, with output $3.75 → $7.50 and cache $0.075 → $0.15. Upstream already carries the effective rate, so **no overlay was added** — per v1.16.20, an overlay that merely duplicates upstream becomes a liability the moment the vendor moves. Re-check upstream after the switchover instead.
- ❌ Exclude the two new Gemini speech SKUs, `gemini/gemini-3.5-transcribe` and `gemini/gemini-3.5-transcribe-live` — same Google scope rule that already excludes the TTS and live-translate previews (chat + Embedding + `gemini-*-image*`; audio is not in it). Unlike those, these carry **no** `-preview` suffix, so nothing else was keeping them out: without explicit `EXCLUDE_MODEL_KEYS` entries they would have entered the export alongside 3.8 Flash.
- ⏸️ **Defer `gemini/gemini-omni-1.1-flash`.** ai.google.dev calls it *"our next-generation video generation and editing model"*, yet upstream classifies it as `mode: chat` with only the $1.50 in / $9.00 out text rates. The published tariff has a second output tier — **$17.50 per M for video output** — that the chat shape cannot express, so importing it as-is would under-bill video output by roughly half. Excluded for now with a code comment saying what has to change to admit it.

### v1.16.21 (2026-09-04)
- Add three new flagship SKUs. Exported total **150 → 153**; no existing entries changed.

  | Key | Friendly name | Input / Output | Cache read | Ctx / max out | How |
  |---|---|---|---|---|---|
  | `claude-fable-5-1` | Claude Fable 5.1 | $10 / $50 | **$0.25** | 1M / 128K | upstream, no code change |
  | `claude-mythos-5-1` | Claude Mythos 5.1 | $10 / $50 | **$0.25** | 1M / 128K | pre-staged (not upstream) |
  | `gpt-6-astra` | GPT-6 Astra | $10 / $50 | $1 | **1.05M** / 128K | upstream + context overlay |

- ⚠️ **The Claude 5.1 pair uses a 0.025x cache ratio**, not the 0.1x the rest of the family pays — $0.25 against $10 input, where `claude-fable-5` / `claude-mythos-5` pay $1. Stated in the pricing-page footnote: *"0.1x base input price (0.025x on Claude Fable 5.1 and Claude Mythos 5.1)"*. Upstream independently carries the $0.25 for `claude-fable-5-1`, corroborating it.
- `claude-mythos-5-1` is injected via `ANTHROPIC_SYNTH_DATA`, same as `claude-mythos-5`: Project Glasswing is limited-availability and BerriAI upstream carries neither Mythos SKU.
- 🔴 **`gpt-6-astra` hit the same upstream context defect as the gpt-5.6 family** — `max_input_tokens` reported as `922000` (GPT-5.5's figure) against the official **1,050,000** on [developers.openai.com](https://developers.openai.com/api/docs/models/gpt-6-astra) (verified on both the model page and the models index). `OPENAI_SYNTH_DATA` overlays **only** that field: all 27 of upstream's price fields were checked against the official pricing table and match exactly — short context $10 / $1 cached / $12.50 write / $50 out, long context (>272K) $20 / $2 / $25 / $75, plus the flex / priority / batch variants — so none of them are overlaid, per the v1.16.18 lesson about stale price overlays.
- No new naming rules were needed: the existing formatters already render `Claude Fable 5.1`, `Claude Mythos 5.1` and `GPT-6 Astra` correctly.

### v1.16.20 (2026-09-01)
- **Retire the `claude-sonnet-5` introductory-price overlay** — and *not* because the window expired. The v1.15.x note said to restore $3 / $15 today; that would have been wrong. [platform.claude.com pricing](https://platform.claude.com/docs/en/about-claude/pricing) now states: *"The $2/$10 per million input/output token pricing for Claude Sonnet 5, announced at launch as introductory pricing through August 31, 2026, **is now the standard price**. The previously scheduled increase to $3/$15 per million input/output tokens on September 1, 2026 **will not occur**."*
  - The $2 / $10 / $0.20 / $2.50 rate is permanent, and LiteLLM upstream carries it verbatim — verified field by field on 2026-09-01, all four identical to the overlay
  - So the overlay was deleted as a **no-op**, not swapped for different numbers. Proven by running the filter over one upstream snapshot with and without the overlay: **zero entries differ**, and `filtered_models.json` is unchanged (exported total stays **150**)
  - ⚠️ Lesson recorded in code and in the Anthropic rules section: **delete an overlay once upstream catches up.** A redundant overlay silently pins values the moment the vendor moves next — exactly how the `gpt-5.6` `*_above_272k_flex` overlays came to bill flex long-context output at $22.50/M against a real $15/M (v1.16.18)

### v1.16.19 (2026-08-29)
- Add **DashScope (阿里云百炼 / Alibaba Cloud Model Studio)** as a provider with the **Qwen 3.8 generation** (3 SKUs). Source: [qwencloud.com/pricing/api](https://www.qwencloud.com/pricing/api), snapshot 2026-08-29.

  | Key | Friendly name | Input | Output | Implicit cache | Context / out |
  |---|---|---|---|---|---|
  | `dashscope/qwen3.8-flash` | Qwen3.8-Flash | $0.15 | $0.47 | $0.016 | 991,808 / 131,072 |
  | `dashscope/qwen3.8-max` | Qwen3.8-Max | $2 | $6 | $0.25 | 991,808 / 131,072 |
  | `dashscope/qwen3.8-2.4t-a95b` | Qwen3.8-2.4T-A95B | $2 | $6 | $0.25 | 991,808 / 131,072 |

  All three are single-tier on the official tariff, multimodal, and carry `supports_reasoning` / `supports_tool_choice` / `supports_prompt_caching` to match the upstream `dashscope/*` entry shape.
  - `PROVIDERS` + `PROVIDER_MAPPING` gain `dashscope`; `DASHSCOPE_ALLOWED_KEYS` + `DASHSCOPE_SYNTH_DATA` + `apply_dashscope_synth` follow the established injector shape; `format_model_name` emits `Qwen3.8-Flash`
  - **Namespace:** *DashScope* is the API/SDK identifier (`dashscope.aliyuncs.com`, `DASHSCOPE_API_KEY`) for the service branded 百炼 / Model Studio. Verified all 45 upstream keys use `litellm_provider: "dashscope"` and the `dashscope/` prefix, with no competing `bailian` / `alibaba` / `aliyun` label — so matching it lets a future upstream key merge instead of collide. **Unrelated to ModelScope (魔搭)**, Alibaba's open-weights hub, which has no upstream provider label
  - **Currency:** International **USD**, native. Alibaba keeps two books — domestic 百炼 in CNY (`qwen3.8-flash` at 0.8 / 2.7 CNY) and International in USD — and upstream's `dashscope/*` prices are the USD ones (`dashscope/qwen3.8-max` is `$2 / $6` upstream vs `12 / 36` CNY on 百炼, which is *not* 12÷7). Injected wholesale: upstream has no `qwen3.8-flash` key, and its flash-tier siblings carry no price at all
  - **Cache prices are read from the published table, never derived.** The implicit-cache ratio varies per model *and* per currency — `qwen3.8-flash` is $0.016 against $0.15 (10.7%) while `qwen3.8-max` is $0.25 against $2 (12.5%), and the CNY book differs again (`qwen3.8-flash` ¥0.1 against ¥0.8 = 12.5%). The Context Cache doc's *"typically 10% explicit / 20% implicit"* is a rule of thumb, not a tariff
  - `dashscope/qwen3.8-max` is **whitelisted with no synth entry** — upstream already carries it and its prices match qwencloud field for field ($2 / $6 / $0.25), so a synth entry would only add a second place to keep in sync
  - **Context and max output come from the published spec chips**, not inference: every [qwencloud.com/models](https://www.qwencloud.com/models) card in the 3.8 family shows *"1 M Context"* and *"131.1 K Max Out"*, so all three carry 991,808 / 131,072 (`max_input_tokens` uses the concrete 991,808 that upstream already carries for `qwen3.8-max` — Alibaba publishes 最大输入 as the 1,000,000 window minus an 8,192 reserve)
  - **`supports_vision: true` on all three.** `qwen3.8-flash` and `qwen3.8-max` are tagged *"Text & Code | Image | Video"* on their model cards, and the official vision docs put flash in the top image-input tier (*"up to 2,048 images"*). `qwen3.8-2.4t-a95b` has no explicit modality tag row — it is the open-source build of the same 2.4T flagship as `qwen3.8-max`, and its own card lists multimodal benchmarks (BabyVision 82.0, OSWorld 86.1); this is weaker evidence than the other two and is flagged as such in code
  - **3.7 and older are deliberately out of scope for now.** `qwen3.7-plus`, `qwen3.7-flash` and `qwen3.6-max-preview` are tiered by request input size (阶梯计价), which the flat `input_cost_per_token` schema cannot express — LiteLLM models this with a `tiered_pricing` array that `should_exclude_due_to_price` does not read, which is also why upstream's own `dashscope/qwen-flash` never reaches the export despite being priced. `qwen3.7-max` is single-tier but runs a 50%-off promotion with no published end date, so it needs the list-vs-effective call made first
  - `supports_vision: true`, per the official vision docs' top image-input tier: *"Qwen3.8-Max, Qwen3.8-Flash, Qwen3.7-Plus series: Up to 2,048 images"*. An earlier read of the "选择模型 / Recommended models" page suggested text-only; that page is a curated shortlist ending in 查看更多, so absence from it proves nothing — the rules section now warns against that inference
  - `qwen3.8-flash-next` was **not** added: it is an open-weights release (Qwen4-architecture preview) hosted on ModelScope / HuggingFace, absent from both the CN and International Model Studio pricing tables, and therefore not a billable SKU
- Also adds the Qwen **3.7** generation (`qwen3.7-max`, `qwen3.7-plus`, `qwen3.7-flash`) and, with it, **tiered-pricing support**:
  - `should_exclude_due_to_price` gains `_has_tiered_price()`, so a SKU priced only via `tiered_pricing` is no longer dropped as "zero price". That bug is why upstream's own `dashscope/qwen-flash` never reached the export despite being priced — its prices live in a `tiered_pricing` array the validator did not read
  - `qwen3.7-plus` (2 tiers) and `qwen3.7-flash` (3 tiers) carry the full ladder in `tiered_pricing`, plus flat fields set to the **highest tier** so a tier-unaware consumer over-bills rather than under-bills
  - **Effective (post-discount) prices**, per request: `qwen3.7-max` $1.25 / $3.75 / $0.25 (50% off $2.5 / $7.5 / $0.5); `qwen3.7-plus` 20% off in both tiers. ⚠️ No published end date, so unlike the GLM-5.3-Flash overlay there is no revert to schedule — list prices are recorded inline in the code for an easy restore
  - `qwen3.7-max` is **text-only**: it appears in neither image-count tier of the official vision docs, and upstream leaves `supports_vision` unset. `qwen3.7-plus` (2,048 images) and `qwen3.7-flash` (256 images) are multimodal
- Exported total **144 → 150** (+6); no existing entries changed.

### v1.16.18 (2026-08-26)
- **LiteLLM upstream sync.** No models added or removed (total stays **144**); the substance is a GPT-5.6 price cut and the removal of an overlay that would have blocked it.
- **`gpt-5.6` / `gpt-5.6-sol` price cut, verified at source.** developers.openai.com now lists **GPT-5.6 Sol at `$4 • $20`** (input • output), down from the `$5 • $30` read off the same page on 2026-08-21; `gpt-5.6` is the alias that routes to Sol, so it moves with it. Every derived tier moved proportionally: cached read `$0.50 → $0.40`, cache write `$6.25 → $5`, and all batch / flex / priority / above-272K variants. `gpt-5.6-terra` (`$2 • $12`) and `gpt-5.6-luna` (`$0.20 • $1.20`) are **unchanged** — re-checked terra's model page directly.
- 🔴 **Removed the four `*_above_272k_tokens_flex` overlays from all four `gpt-5.6` entries in `OPENAI_SYNTH_DATA`.** These were added in v1.16.1 because upstream lacked the fields. Upstream now supplies them — and for `terra` / `luna` its values match ours **exactly**, which is what makes trusting it for `sol` justified. Had the overlay stayed, it would have pinned the **pre-cut** numbers on top of the corrected upstream data and billed flex long-context output at **$22.50/M against a real $15/M**. The `max_input_tokens: 1050000` overlay stays (upstream still reports GPT-5.5's `922000`), and its comment now records why the flex fields left, so nobody re-adds them blindly.
- Minor upstream metadata, accepted as-is: `supports_legacy_thinking: true` on `claude-sonnet-4-6` / `claude-opus-4-6` / `claude-opus-4-6-20260205`; `thinking_always_on: true` on `claude-fable-5` / `claude-mythos-5`; `gemini/gemini-3.1-flash-lite-image` `supports_reasoning` **true → false** (upstream churn — it was set true in the 2026-08-21 sync; not a billing field).
- `stats.passed == len(filter_all_models) == 144` holds; GLM-5.3-Flash, BytePlus, DeepSeek and the realtime allow-list are unaffected.

### v1.16.17 (2026-08-26)
- Add **GLM-5.3-Flash** (`zai/glm-5.3-flash`) — the first **natively multimodal** model in the GLM-5 series (320B total / 18B activated). Sources: [docs.z.ai/guides/vlm/glm-5.3-flash](https://docs.z.ai/guides/vlm/glm-5.3-flash) + [pricing](https://docs.z.ai/guides/overview/pricing), snapshot 2026-08-26.
  - **1M context / 128K max output** — z.ai states its text parameters are "consistent with GLM-5.3, with support for a 1M-token context window"
  - **`supports_vision: True`, set explicitly.** The key has no `v` infix, so the `_GLM_VISION_KEY` auto-inference used for `glm-*v` / `glm-ocr` does not match it. Being a VLM whose id doesn't look like one, this is the first SKU that needs the flag hard-set in `ZAI_SYNTH_DATA`
  - **Promotional price stored, not list.** z.ai: *"GLM-5.3-Flash is available at a 50% discount (strikethrough prices are list prices). The promotion ends at 24:00 on September 9, 2026 (UTC+8, Singapore time)."* List $0.15 / $0.03 / $0.50 per M (input / cached / output) → effective **$0.075 / $0.015 / $0.25**. The discount is **unconditional**, so the effective rate is what callers are actually billed — same treatment as `ANTHROPIC_SYNTH_DATA`'s introductory overlays, and deliberately unlike `BYTEPLUS_SYNTH_DATA`, which stores list because those campaigns are gated on account balance / savings-plan tier. **Revert to list on 2026-09-10**; the exact values to restore are in the code comment
  - `bigmodel/glm-5.3-flash` added as the domestic mirror (confirmed available on the bigmodel gateway at the same price). Per the usual mirror mechanic its prices are **not** written into `BIGMODEL_SYNTH_DATA` — `apply_bigmodel_synth` copies them from the `zai/` sibling, so the promo rate and its 2026-09-10 revert are maintained in exactly one place. `supports_vision` *is* stated there, since that is metadata rather than a mirrored price field
- Also promotes `zai/glm-5.3` from *pre-staged guess* to *verified*: v1.16.10 staged it by mirroring GLM-5.2 before z.ai published rates; the published rates ($1.4 / $0.26 / $4.4) turn out identical, so the numbers are unchanged and only the code comment's status claim was corrected.
- Exported total **142 → 144** (+2: `zai/glm-5.3-flash`, `bigmodel/glm-5.3-flash`); no existing entries changed.

### v1.16.16 (2026-08-21)
- Add an **estimated 4K tier** to BytePlus Dreamina Seedance 2.5 (both entries: dated `-260628` + alias). ⚠️ **Not official** — the BytePlus 2.5 table has no 4K row, exactly like the domestic one. Mirrors the derivation used for the domestic estimate in v1.16.12: scale 2.5's 1080P by the 2.0 4K:1080P ratio, computed entirely inside the overseas USD price set so no FX or cross-catalogue mixing enters:
  - no video: `11.70 × (4.00 / 7.70) = 6.078` → **$6.08/M** → `output_cost_per_token_4k` 6.08e-06
  - with video: `7.00 × (2.40 / 4.70) = 3.574` → **$3.57/M** → `output_cost_per_token_4k_with_input_video` 3.57e-06
  - Sanity check recorded in code: the overseas/domestic premium on every *officially* priced 2.5 tier sits in **1.064–1.070**, while these estimates imply 1.091 and 1.041 — the spread comes from the domestic 4K estimate itself being rounded to whole CNY (39 / 24). Replace with the official rate once BytePlus publishes a 2.5 4K tier.
- Marked as an estimate in code and README, same as the domestic tier. Only the two 4K fields added per entry; no additions, no removals, no other price field touched (exported total stays **142**).

### v1.16.15 (2026-08-21)
- **LiteLLM upstream sync**, with every notable change verified against the vendor's own docs rather than taken on trust. Exported total **140 → 142**.
- **Regression fixed — the realtime allow-list had silently dropped out.** Upstream re-classified `gpt-realtime` and `gpt-4o-realtime-preview-2024-12-17` from `mode: "chat"` to a new `mode: "realtime"`; neither key was removed upstream, but `SUPPORTED_MODES` didn't list `realtime`, so both were discarded as `unsupported_mode`. Adds `realtime` to `SUPPORTED_MODES`, maps it to type **`language`** in `MODE_MAPPING` (an LLM interaction, same reasoning as `responses` — and it preserves the downstream contract, since these SKUs already exported as `language`), and gives it a `PRICE_FIELDS_BY_MODE` entry covering all four billing axes (text in/out, audio in/out) plus `input_cost_per_image`. Restores exactly the 2 allow-listed SKUs — the other 15 `realtime` keys upstream stay out via the existing `^gpt-realtime` global exclude.
- **`gpt-5.6` family context corrected back to 1,050,000.** Upstream regressed `max_input_tokens` to `922000` (that is GPT-5.5's input figure). `developers.openai.com/api/docs/models/gpt-5.6-{sol,terra,luna}` all state **1,050,000 context / 128,000 max output** — verified page by page on 2026-08-21 — so `OPENAI_SYNTH_DATA` now overlays it for `gpt-5.6`, `-sol`, `-terra`, `-luna`.
- **Upstream corrections accepted after verification:**
  - `claude-sonnet-4-6` `max_output_tokens` **64,000 → 128,000** — correct per the Legacy models table on platform.claude.com (Sonnet 4.6 max output 128k; it is also in the 300k Batches-API beta list). Upstream was previously wrong.
  - `gemini/gemini-3.1-flash-image` (+ its `-preview` sibling) input **$0.25 → $0.50**, output **$1.50 → $3.00** per M — a **real price increase**, confirmed against ai.google.dev/gemini-api/docs/pricing ("Input price $0.50 (text/image)", "Output price $3 (text and thinking)").
- **New models included (2):**
  - `gemini/gemini-3.7-flash` — Gemini 3.7 Flash, 1,048,576 ctx / 65,536 out, $0.75 / $3.75 per M
  - `gpt-5.6-cyber` — GPT-5.6 Cyber, 400,000 ctx / 128,000 out, $12.50 / $75 per M (cached $1.25, cache write $15.625). Part of OpenAI's Daybreak program (`daybreak-red-latest` aliases to it); all four figures and the 400K context match developers.openai.com exactly. No long-context tier, which is why its context differs from the rest of the 5.6 family.
- **New models deliberately excluded (4)** — scope decisions, not data problems; each is present and correctly priced upstream:
  - `gpt-transcribe`, `gpt-live-transcribe` — full-fat OpenAI ASR. OpenAI dropped the `4o` infix in this generation, so these arrive as bare keys no existing pattern catches. Excluded for the same **narrow product scope** reason already documented for `gpt-4o-transcribe` / `gpt-4o-transcribe-diarize`; `gpt-4o-mini-transcribe` remains the sanctioned ASR SKU.
  - `gemini/gemini-3.1-flash-tts-preview`, `gemini/gemini-3.5-live-translate-preview` — non-conversational Gemini modalities. The Google scope is Gemini 2.5+ chat, Gemini Embedding, and `gemini-*-image*`; audio is not in it. These reach the filter only because the `^gemini/gemini-[3-9].*-preview$` include pattern (written to admit 3.x *chat* previews) is broader than its intent. Joins the existing `gemini/gemini-3.1-flash-live-preview` special-purpose exclusion.
- No entries removed. `stats.passed == len(filter_all_models) == 142` holds; DeepSeek peak pricing and the 8 BytePlus SKUs are unaffected.

### v1.16.14 (2026-08-21)
- Add **BytePlus (ByteDance Ark overseas)** as a provider with the **Dreamina Seedance** video family — 8 SKUs, the overseas counterpart to the domestic `volcengine/doubao-seedance-*` set. Source: [docs.byteplus.com/en/docs/ModelArk/1544106](https://docs.byteplus.com/en/docs/ModelArk/1544106) (same doc ID as the domestic page, different tariff).
  - `PROVIDERS` + `PROVIDER_MAPPING` gain `byteplus`; `BYTEPLUS_ALLOWED_KEYS` reverse-whitelists 4 dated IDs (`dreamina-seedance-2-5-260628`, `-2-0-260128`, `-2-0-fast-260128`, `-2-0-mini-260615`) plus their 4 date-less aliases
  - `BYTEPLUS_SYNTH_DATA` + `apply_byteplus_synth` inject all 8 wholesale — LiteLLM upstream carries **no** Seedance keys at all (verified 2026-08-21: zero `/seedance/i` matches), domestic or overseas
  - **USD-native pricing.** New `_usd_per_m_to_usd_per_token()` helper (plain `/1e6`, same 4-sig-fig rounding) keeps the vendor's own USD/M figures readable in the tariff table. These are **not** the domestic CNY prices run through the FX rate — overseas list prices sit ~6–8% higher (2.0 480P/720P: $7.00 vs domestic 46 CNY → $6.571), so they are independent SKUs with no mirror mapping. List prices, USD/M, no-video / with-video: 2.5 — 480P/720P **10.70 / 6.40**, 1080P **11.70 / 7.00**; 2.0 — 480P/720P **7.00 / 4.30**, 1080P **7.70 / 4.70**, 4K **4.00 / 2.40**; 2.0 Fast — **5.60 / 3.30**; 2.0 Mini — **3.50 / 2.10**
  - **List price, not the promo price.** BytePlus limited-time campaigns ([2630943](https://docs.byteplus.com/en/docs/ModelArk/2630943)) discount 2.5 1080P to 72% (until 2026-09-17), 2.0 Fast to 75% and 2.0 Mini to 40% (until 2026-09-07), where *"N% of list"* means pay N%. Those discounts are conditional (pay-as-you-go only, resource packs excluded, needs balance or AI Savings Plan ≥ USD 30), so list is the canonical value — it never under-bills and needs no revert on expiry
  - `format_model_name` emits **`Dreamina Seedance 2.5`** / `Dreamina Seedance 2.0 Fast` — brand with a **space**, matching docs.byteplus.com, deliberately unlike Volcengine's hyphenated `Doubao-Seedance` (per-vendor official naming, v1.16.2)
  - Confirms the v1.16.12 call that the domestic Seedance **2.5 4K** tier is an estimate: the overseas table prices 4K for 2.0 but has no 4K row for 2.5 either
  - Note: the date-less aliases are a **catalogue convention of this project**, not vendor-registered IDs — verified 2026-08-21 that neither BytePlus's Model list ([1330310](https://docs.byteplus.com/en/docs/ModelArk/1330310)) nor Volcengine's domestic equivalent publishes non-dated Seedance IDs. Alias and dated twin carry identical pricing
  - Exported total **132 → 140** (+8); no existing entries changed. Also corrected the ecloud_aicc mirror count in the provider list (7 → 8)

### v1.16.13 (2026-08-20)
- **DeepSeek V4 price update** (api-docs.deepseek.com/quick_start/pricing). The official table now quotes CNY/M split into peak / off-peak windows (off-peak = exactly half of peak; peak is Beijing-time 09:00–12:00 and 14:00–18:00). LiteLLM has no time-of-day price axis, so `DEEPSEEK_SYNTH_DATA` carries the **peak** rate — the ceiling, so we never under-bill:
  - `deepseek/deepseek-v4-flash` — cache-miss input **3.0 CNY/M** → `input_cost_per_token` 4.286e-07, cache-hit input **0.10 CNY/M** → `cache_read_input_token_cost` / `input_cost_per_token_cache_hit` 1.429e-08, output **9.0 CNY/M** → `output_cost_per_token` 1.286e-06
  - `deepseek/deepseek-v4-pro` — cache-miss input **9.0 CNY/M** → 1.286e-06, cache-hit input **0.30 CNY/M** → 4.286e-08, output **27.0 CNY/M** → 3.857e-06
  - Converted at the policy FX rate `1 USD = 7.0 CNY` via `_cny_per_m_to_usd_per_token`, 4 sig figs (reversible back to the source CNY). Cache writes stay free (`cache_creation_input_token_cost` 0.0)
  - Renamed the FX constant `_VOLCENGINE_FX_RATE` → `_CNY_USD_FX_RATE`: it is now shared by two CNY-quoted vendors (Seedance, DeepSeek). Same value, single use site, no behaviour change
- Net: pricing-only change to 2 SKUs; context (1M), max output (384K), capabilities, and exported total (132) unchanged.

### v1.16.12 (2026-08-19)
- Add an **estimated 4K tier** to Doubao Seedance 2.5 (all 6 entries: dated + alias × volcengine / new-api / ecloud_aicc). ⚠️ **Not official** — the Volcengine 2.5 table has no 4K row. Derived from 2.5's 1080P scaled by the 2.0 4K:1080P ratio (~0.51×): 无视频 **39 CNY/M** → `output_cost_per_token_4k` 5.571e-06, 含视频 **24 CNY/M** → `output_cost_per_token_4k_with_input_video` 3.429e-06 (USD @ 7.0 FX). Marked as an estimate in code; replace with the official rate when Volcengine publishes a 2.5 4K tier. Only the two 4K fields added per entry; no other changes.

### v1.16.11 (2026-08-14)
- **Doubao Seedance 2.5 price update — 1080P tier added** (docs.volcengine.com/docs/82379/2191775). The 480P/720P rates are unchanged (70 / 42 CNY/M no-video / with-video); the table now also lists 1080P: **无视频输入 0.077 元/千 = 77 CNY/M** → `output_cost_per_token_1080p` 1.1e-05, **含视频输入 0.046 元/千 = 46 CNY/M** → `output_cost_per_token_1080p_with_input_video` 6.571e-06 (USD @ 7.0 FX). Applied to all 6 Seedance 2.5 entries (dated + alias × volcengine / new-api / ecloud_aicc); only the two new 1080P fields added per entry. Also corrected the README Seedance counts to 8 (the dated `-260628` ID from #10 wasn't reflected in the docs).

### v1.16.10 (2026-08-14)
- Pre-stage **GLM-5.3** (`zai/glm-5.3` + `bigmodel/glm-5.3`). GLM-5.3 is not yet officially released (z.ai still lists GLM-5.2 as flagship), so its config and price **deliberately mirror GLM-5.2** per request: input **$1.4** / output **$4.4** / cached **$0.26** per M, 1M context. bigmodel price is mirrored from the `zai/glm-5.3` sibling via `apply_bigmodel_synth`. Update once z.ai publishes official GLM-5.3 pricing. Exported total **130 → 132** (+2); no existing entries changed.

### v1.16.9 (2026-08-10)
- Add **Doubao Seedance 2.5** video model (`volcengine/doubao-seedance-2-5`) + its `new-api` / `ecloud_aicc` mirrors. Source: docs.volcengine.com/docs/82379/2191775 (Tokens 抵扣规则). 480P/720P only (no 1080p/4k tier), two input scenarios:
  - no-input-video (文生视频): **70 CNY / 1M tokens** → `output_cost_per_token` 1e-05 (USD @ 7.0 FX).
  - with-input-video (图生视频): **42 CNY / 1M tokens** → `output_cost_per_token_with_input_video` 6e-06.
- Renders as `Doubao-Seedance 2.5`. Whitelist + `VOLCENGINE_SYNTH_DATA` + both mirror maps updated. Date-less alias only — no dated snapshot ID / fast / mini variant published for 2.5 yet. Exported total **124 → 127** (+3); no existing entries changed.

### v1.16.8 (2026-07-31)
- **GPT-5.6 Luna −80%, GPT-5.6 Terra −20%** price cut (OpenAI, effective 2026-07-31; developers.openai.com/api/docs/pricing). Every cost field across all tiers (standard / flex / batch / priority × short / long context) rescaled by the announced factor — verified field-by-field against the official page:
  - `gpt-5.6-terra` ×0.80 — standard $2.50 / $15 / $0.25 → **$2.00 / $12 / $0.20**.
  - `gpt-5.6-luna` ×0.20 — standard $1.00 / $6 / $0.10 → **$0.20 / $1.20 / $0.02**.
- `gpt-5.6-sol` and the `gpt-5.6` base alias unchanged ($5 / $30 / $0.50). No other OpenAI models changed (all still match the official page). `OPENAI_SYNTH_DATA` flex-long-context overlays for terra/luna updated to match. Only 2 entries changed; no additions.

### v1.16.7 (2026-07-30)
- Add Moonshot **Kimi K2.7 Code** (`moonshot/kimi-k2.7-code`) and **Kimi K2.7 Code HighSpeed** (`moonshot/kimi-k2.7-code-highspeed`) — completes the deferral noted in v1.16.6 now that official prices are confirmed (platform.kimi.ai chat-k2.7-code pricing page). Both 256K (262,144) context, text/image/video input, thinking, ToolCalls, JSON Mode:
  - Kimi K2.7 Code — **$0.95 in / $4.00 out** per M, cache-hit **$0.19**.
  - Kimi K2.7 Code HighSpeed — **$1.90 in / $8.00 out** per M, cache-hit **$0.38**.
- `raw_data.supports_reasoning: true` on both; `format_model_name` renders `HighSpeed` with the official camel-case. Exported total **122 → 124** (+2); no existing entries changed.

### v1.16.6 (2026-07-30)
- Add **Moonshot (Kimi)** as a supported provider (reverse-whitelist `MOONSHOT_ALLOWED_KEYS`), with **Kimi K3** (`moonshot/kimi-k3`). Prices verified against platform.kimi.ai/docs/pricing/chat-k3: **$3 / $15 per M** input / output, cache-hit **$0.30**, 1M context. `raw_data.supports_reasoning: true` (so the downstream mock emits reasoning tokens). Exported total **121 → 122** (+1); no existing entries changed.
- New `MOONSHOT_SYNTH_DATA` + `apply_moonshot_synth` injector (wholesale-inject, not yet on LiteLLM upstream) wired into `filter_all_models` / `get_filter_stats`; `PROVIDERS` / `PROVIDER_MAPPING` / `PROVIDER_EXCLUSION_RULES` register `moonshot`; `format_model_name` renders `moonshot/kimi-k3` → `Kimi K3`.
- Kimi K2.7-code / K2.7-code-highspeed **not added** — pricing not verifiable on platform.kimi.ai (chat-k2.7-code page lists 256K context + a highspeed variant but no per-token rates). Add once an official price source is confirmed.

### v1.16.5 (2026-07-28)
- Add standalone OpenAI **TTS** models `tts-1` and `tts-1-hd` to the audio allow-list. Character-billed: `tts-1` **$15 / 1M chars** (`output_cost_per_character` 1.5e-05), `tts-1-hd` **$30 / 1M chars** (3e-05); source openai.com. Exported total **119 → 121** (+2); no existing entries changed.
- `PRICE_FIELDS_BY_MODE["audio_speech"]` now also accepts `input_cost_per_character` / `output_cost_per_character` (previously per-token / per-second only), so per-character TTS models are not zero-price dropped.
- `apply_openai_synth` upgraded to inject-when-absent / overlay-when-present (mirrors the anthropic/google injectors); `INCLUDE_PATTERNS` allows `^tts-1$` / `^tts-1-hd$`; `format_model_name` renders `tts-1` / `tts-1-hd` as their lowercase id.
- Correct `gpt-4o-mini-tts` **text input price** 2.5e-06 → **6e-07 ($0.60 / 1M)** to match OpenAI's official rate (developers.openai.com); upstream carried the Azure/aggregator $2.50 figure. Audio output ($12 / 1M, `output_cost_per_audio_token`) was already correct. OpenAI has marked the model deprecated but it is still available.

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

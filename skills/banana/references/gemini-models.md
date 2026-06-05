# Gemini Image Generation Models

> Last updated: 2026-03-19
> Aligned with Google's March 2026 API state

## Available Models

### gemini-3.1-flash-image-preview -- Nano Banana 2 (DEFAULT)
| Property | Value |
|----------|-------|
| **Model ID** | `gemini-3.1-flash-image-preview` |
| **Tier** | Nano Banana 2 (Flash) |
| **Status** | Preview -- **Active, recommended default** |
| **Speed** | Fast -- optimized for high-volume use |
| **Aspect Ratios** | All 14 ratios including extreme: 1:4, 4:1, 1:8, 8:1 |
| **Max Resolution** | Up to 4096×4096 (4K tier) |
| **Input Tokens** | 131,072 |
| **Features** | Google Search grounding, thinking levels, image-only output, extreme aspect ratios |
| **Rate Limits (Free)** | ~5-15 RPM / ~20-500 RPD |
| **Output Tokens** | ~1,290 output tokens per image |
| **Best For** | All standard production generation and editing |

### gemini-2.5-flash-image -- Nano Banana (Original)
| Property | Value |
|----------|-------|
| **Model ID** | `gemini-2.5-flash-image` |
| **Tier** | Nano Banana (Flash, original generation) |
| **Status** | GA -- **Active** |
| **Speed** | Fast |
| **Aspect Ratios** | 1:1, 16:9, 9:16, 4:3, 3:4, 2:3, 3:2, 4:5, 5:4, 21:9 (10 ratios) |
| **Max Resolution** | Up to 1024×1024 (1K tier) |
| **Input Tokens** | 32,768 |
| **Rate Limits (Free)** | ~5-15 RPM / ~20-500 RPD |
| **Best For** | Free-tier users, budget-conscious high-volume workflows |
| **Cost** | ~$0.039/image at 1K |

## DEPRECATED -- gemini-3-pro-image-preview

**Shut down by Google on March 9, 2026.** API calls to this model ID will fail
with a hard error. Do not use. The replacement is Nano Banana 2
(`gemini-3.1-flash-image-preview`).

## Domain-to-Model Routing

| Domain Mode | Recommended Model | Reason |
|---|---|---|
| Cinema, Landscape, Abstract | Nano Banana 2 | Thinking mode improves complex compositions |
| Product, Portrait | Nano Banana 2 | 2K/4K resolution for fidelity |
| UI, Infographic | Nano Banana 2 | Search grounding for factual diagrams |
| Logo | Nano Banana 2 | Text rendering improvements in 3.1 |
| Editorial | Nano Banana 2 | Default |
| Free tier / budget | Nano Banana (original) | $0.039/image, still excellent |

## Resolution Defaults by Domain

| Domain | Default `imageSize` | Rationale |
|--------|-------------------|-----------|
| Portrait, Product, Logo | `2K` | Fine detail and text fidelity |
| Cinema, Landscape | `2K` + widescreen ratio | Atmospheric depth at larger canvas |
| UI, Infographic | `1K` | Structured output doesn't benefit from 4K |
| Quick draft / preview | `512` (Nano Banana 2 only) | Rapid iteration |
| Print / high fidelity | `4K` | Maximum resolution for physical output |

## Aspect Ratios

| Ratio | Orientation | Use Cases | NB2 (3.1 Flash) | NB (2.5 Flash) |
|-------|-------------|-----------|:----------------:|:--------------:|
| `1:1` | Square | Social posts, avatars, thumbnails | ✅ | ✅ |
| `16:9` | Landscape | Blog headers, YouTube thumbnails | ✅ | ✅ |
| `9:16` | Portrait | Stories, Reels, TikTok, mobile | ✅ | ✅ |
| `4:3` | Landscape | Product shots, classic display | ✅ | ✅ |
| `3:4` | Portrait | Book covers, portrait framing | ✅ | ✅ |
| `2:3` | Portrait | Pinterest pins, posters | ✅ | ✅ |
| `3:2` | Landscape | DSLR standard, photo prints | ✅ | ✅ |
| `4:5` | Portrait | Instagram portrait, social | ✅ | ✅ |
| `5:4` | Landscape | Large format photography | ✅ | ✅ |
| `21:9` | Ultra-wide | Cinematic, film-grade | ✅ | ✅ |
| `1:4` | Tall strip | Vertical banners, side panels | ✅ | ❌ |
| `4:1` | Wide strip | Website banners, headers | ✅ | ❌ |
| `1:8` | Extreme tall | Narrow vertical strips | ✅ | ❌ |
| `8:1` | Extreme wide | Ultra-wide banners | ✅ | ❌ |

## Resolution Tiers

| `imageSize` Value | Pixel Range | Model Availability | Use Case |
|-------------------|-------------|-------------------|----------|
| `512` | Up to 512×512 | Nano Banana 2 only | Drafts, quick iteration |
| `1K` | Up to 1024×1024 | All models | Standard web use, social media |
| `2K` | Up to 2048×2048 | Nano Banana 2 only | Quality assets, detailed work |
| `4K` | Up to 4096×4096 | Nano Banana 2 only | Print production, hero images |

**IMPORTANT:** `imageSize` value MUST be uppercase -- `"2k"` will be silently ignored.

## API Configuration

### Endpoint
```
https://generativelanguage.googleapis.com/v1beta/models/{model-id}:generateContent
```

### Required Parameters
```json
{
  "contents": [{"parts": [{"text": "your prompt here"}]}],
  "generationConfig": {
    "responseModalities": ["TEXT", "IMAGE"],
    "imageConfig": {
      "aspectRatio": "16:9",
      "imageSize": "2K"
    }
  }
}
```

### Thinking Level
```json
{
  "generationConfig": {
    "thinkingConfig": {
      "thinkingLevel": "medium"
    }
  }
}
```
Levels: `minimal`, `low`, `medium`, `high`

## Rate Limits by Tier

| Tier | RPM | RPD |
|------|-----|-----|
| Free | ~5-15 | ~20-500 |
| Tier 1 (billing enabled) | 150-300 | 1,500-10,000 |
| Tier 2 ($250+ spend) | 1,000+ | Unlimited |

## Pricing

| Model | Resolution | Cost per Image |
|-------|-----------|---------------|
| NB2 (3.1 Flash) | 1K | ~$0.067 |
| NB2 (3.1 Flash) | 2K | ~$0.134 |
| NB2 (3.1 Flash) | 4K | ~$0.268 |
| NB (2.5 Flash) | 1K | ~$0.039 |
| Batch API | Any | 50% discount |

## Safety Filters

| `finishReason` | Meaning | Retryable? |
|----------------|---------|:----------:|
| `STOP` | Successful generation | N/A |
| `IMAGE_SAFETY` | Output blocked by safety filter | Rephrase prompt |
| `PROHIBITED_CONTENT` | Content policy violation | No |
| `SAFETY` | General safety block | Rephrase prompt |
| `RECITATION` | Detected copyrighted content | Rephrase prompt |

## Key Limitations
- No video generation (image only)
- No transparent backgrounds (use green screen workaround)
- Text rendering best under 25 characters
- Gemini generates ONE image per API call -- no batch parameter
- No negative prompt parameter -- use semantic reframing
- `imageSize` values MUST be uppercase
- SynthID watermarks always embedded in generated images

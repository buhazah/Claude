# analyze-video

Analyze a YouTube (or any yt-dlp-supported) video frame by frame using the Gemini API.

## Setup (one-time)

1. Run the setup script from the project root:
   ```bash
   bash .claude/skills/video-breakdown/scripts/setup.sh
   ```
2. Add your Gemini API key to `.env`:
   ```
   GEMINI_API_KEY=your_key_here
   ```
   Get a free key at https://aistudio.google.com/apikey

## Usage

```bash
.venv/bin/python .claude/skills/video-breakdown/scripts/analyze.py "<VIDEO_URL>"
```

**Options:**
- `--model gemini-2.5-flash` — Gemini model to use (default: gemini-2.5-flash)
- `--output clip.mp4` — filename for the downloaded video
- `--cookies-from-browser firefox` — for age-gated or private content

## What Claude does

After the script streams frame-by-frame output, provide a strategic analysis covering:
- Executive summary
- Temporal structure with timestamps
- Hook effectiveness (first 3–5 seconds)
- Core messaging and themes
- Target audience fit
- Strengths and improvement opportunities
- Prioritized recommendations

Offer to save the full analysis as a markdown file.

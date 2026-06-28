# Video Breakdown Skill

This Claude skill converts video URLs into detailed frame-by-frame analyses. The system downloads videos via yt-dlp, processes them through Google's Gemini API, and generates structured breakdowns with timestamps, action descriptions, scene details, and image-generation prompts.

## Key Setup Requirements

The skill requires a one-time bootstrap using `setup.sh`, which handles environment configuration. Two items may require manual intervention:

- **ffmpeg installation** — typically needs system-level access
- **Gemini API key** — users must obtain this from aistudio.google.com and add it to `.env`

## Primary Usage

Execute via command line with a video URL as the argument. The script supports options for model selection, output filenames, and browser cookie access for restricted content like age-gated or login-required videos.

## Expected Output & Analysis Role

The script extracts raw frame data, but the meaningful work happens afterward. As Claude, the responsibility is to perform strategic content analysis—examining structure, pacing, hook effectiveness, messaging, audience alignment, and identifying both strengths and improvement opportunities.

## Performance Notes

- Works best with shorter clips (15–60 seconds initially)
- Instagram public content loads directly; private posts require cookie authentication
- Processing time scales with video length
- Rate limiting may affect repeated Instagram requests

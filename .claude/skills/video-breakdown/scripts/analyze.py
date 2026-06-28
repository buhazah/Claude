"""
Automated video analysis pipeline.

Downloads a video (YouTube, Instagram, or any yt-dlp-supported site),
uploads it to the Gemini API, waits for processing, then streams a
frame-by-frame structured breakdown.

Usage:
    python analyze.py <video_url>
    python analyze.py <video_url> --model gemini-2.5-flash
    python analyze.py <video_url> --cookies-from-browser firefox   # private/login-walled
    python analyze.py            # no arg -> prompts interactively

Requires GEMINI_API_KEY in the environment (or a .env file in the cwd).
"""

import argparse
import os
import sys
import time

import yt_dlp
from dotenv import load_dotenv
from google import genai

DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_OUTPUT = "video.mp4"

PROMPT = """\
You are a video analysis engine. Watch the entire video and produce a
frame-by-frame breakdown. Move through the video in short, meaningful
intervals (roughly every 1-2 seconds, or at every notable change).

For EACH interval, output a block in EXACTLY this format:

[Timestamp] MM:SS
[Action Description] What is happening / movement / events in this moment.
[Scene Description] Setting, subjects, lighting, colors, composition, mood.
[Image Generation Prompt] A detailed, self-contained prompt that could be
fed to an image model to recreate this exact frame.

Separate each block with a blank line. Cover the video all the way through the
final frame — do not stop early. Do not add any commentary before or after the
blocks; output only the breakdown blocks.
"""


def download_video(url: str, output: str, cookies_from_browser: str | None) -> str:
    """Download a video URL to `output` as MP4. Returns the path."""
    print(f"\n[1/4] Downloading video from: {url}")

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": output,
        "merge_output_format": "mp4",
        "overwrites": True,
        "quiet": False,
        "noprogress": False,
    }
    if cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = (cookies_from_browser,)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    if not os.path.exists(output):
        raise FileNotFoundError("Download finished but no MP4 was produced.")

    size_mb = os.path.getsize(output) / (1024 * 1024)
    print(f"      Saved {output} ({size_mb:.1f} MB)")
    return output


def upload_and_wait(client: genai.Client, path: str):
    """Upload the file and poll until ACTIVE. Returns the File object."""
    print(f"\n[2/4] Uploading {path} to the Gemini API...")
    video_file = client.files.upload(file=path)
    print(f"      Uploaded as: {video_file.name}")

    print("\n[3/4] Waiting for Gemini to finish processing the video...")
    while video_file.state.name == "PROCESSING":
        print("      still processing...", flush=True)
        time.sleep(5)
        video_file = client.files.get(name=video_file.name)

    if video_file.state.name == "FAILED":
        raise RuntimeError(f"Video processing failed: {video_file.state.name}")

    print("      Processing complete. Video is ACTIVE.")
    return video_file


def analyze(client: genai.Client, video_file, model: str) -> None:
    """Stream the frame-by-frame breakdown to the console."""
    print(f"\n[4/4] Analyzing with {model}...\n")
    print("=" * 70)

    stream = client.models.generate_content_stream(
        model=model,
        contents=[video_file, PROMPT],
    )
    for chunk in stream:
        if chunk.text:
            print(chunk.text, end="", flush=True)

    print("\n" + "=" * 70)
    print("Done.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Frame-by-frame video breakdown via Gemini.")
    parser.add_argument("url", nargs="?", help="Video URL (YouTube, Instagram, etc.)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Gemini model id.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Downloaded MP4 path.")
    parser.add_argument("--cookies-from-browser", default=None,
                        help="Browser to pull cookies from (firefox/chrome) for private posts.")
    args = parser.parse_args()

    load_dotenv()
    if not os.getenv("GEMINI_API_KEY"):
        sys.exit("Error: GEMINI_API_KEY not found. Add it to your .env file.")

    url = args.url or input("Enter a video URL: ").strip()
    if not url:
        sys.exit("Error: no URL provided.")

    client = genai.Client()

    path = download_video(url, args.output, args.cookies_from_browser)
    video_file = upload_and_wait(client, path)
    analyze(client, video_file, args.model)


if __name__ == "__main__":
    main()

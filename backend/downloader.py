"""
downloader.py — Extract metadata and download video from an Instagram post URL.

Uses:
- instaloader: metadata + caption extraction (most reliable for IG data)
- yt-dlp: higher quality video download (1080p vs instaloader's 720p)
  with fallback to instaloader's built-in video download if yt-dlp fails.
"""

import os
import re
import json
import instaloader
import subprocess
import urllib.request
from datetime import datetime


# --- Optional: set your Instagram username here for private post access ---
# Leave as None to only access public posts.
INSTAGRAM_USERNAME = None


def extract_shortcode(url: str) -> str:
    """Pull the shortcode out of various Instagram URL formats.

    Handles:
    - https://www.instagram.com/p/ABC123/
    - https://www.instagram.com/reels/ABC123/
    - https://www.instagram.com/reel/ABC123/
    - Trailing slashes, query params, and share links all handled
    """
    # Strip query params first
    url = url.split("?")[0].rstrip("/")
    match = re.search(r"/(?:p|reel|reels)/([A-Za-z0-9_-]+)", url)
    if not match:
        raise ValueError(
            f"Could not parse Instagram URL: {url}\n"
            "Expected a URL like: https://www.instagram.com/p/ABC123/ or /reel/ABC123/"
        )
    return match.group(1)



def infer_title(caption: str, author: str) -> str:
    """Make a readable title from the first line of a caption."""
    if not caption:
        return f"Recipe by @{author}"
    first_line = caption.strip().split("\n")[0]
    # Truncate long first lines
    if len(first_line) > 80:
        first_line = first_line[:77] + "..."
    return first_line or f"Recipe by @{author}"


def _ytdlp_available() -> bool:
    """Check whether yt-dlp is installed on this system."""
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def download_video_ytdlp(url: str, output_dir: str, shortcode: str) -> str | None:
    """Download video using yt-dlp for best quality (up to 1080p).
    Returns server-relative path or None if yt-dlp fails / is not installed.
    """
    output_path = os.path.join(output_dir, f"{shortcode}.mp4")

    if os.path.exists(output_path):
        return f"/media/{shortcode}.mp4"

    if not _ytdlp_available():
        print("yt-dlp not found — skipping high-quality download")
        return None

    try:
        result = subprocess.run(
            [
                "yt-dlp",
                "--quiet",
                "--no-warnings",
                "--no-playlist",
                "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "-o", output_path,
                "--merge-output-format", "mp4",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode == 0 and os.path.exists(output_path):
            return f"/media/{shortcode}.mp4"
        print(f"yt-dlp non-zero exit: {result.stderr[:300]}")
        return None
    except subprocess.TimeoutExpired:
        print("yt-dlp timed out after 180s")
        return None
    except Exception as e:
        print(f"yt-dlp unexpected error: {e}")
        return None


def download_video_instaloader(post, output_dir: str, shortcode: str) -> str | None:
    """Fallback: download video directly from instaloader Post object (up to 720p)."""
    output_path = os.path.join(output_dir, f"{shortcode}.mp4")
    if os.path.exists(output_path):
        return f"/media/{shortcode}.mp4"
    try:
        video_url = post.video_url
        if not video_url:
            return None
        urllib.request.urlretrieve(video_url, output_path)
        return f"/media/{shortcode}.mp4"
    except Exception as e:
        print(f"Instaloader video fallback failed: {e}")
        return None


def download_thumbnail(post, output_dir: str, shortcode: str) -> str | None:
    """Download the post thumbnail/cover image."""
    thumb_path = os.path.join(output_dir, f"{shortcode}_thumb.jpg")
    if os.path.exists(thumb_path):
        return f"/media/{shortcode}_thumb.jpg"
    try:
        urllib.request.urlretrieve(post.url, thumb_path)
        return f"/media/{shortcode}_thumb.jpg"
    except Exception as e:
        print(f"Thumbnail download failed: {e}")
        return None


def extract_post_data(instagram_url: str, media_dir: str) -> dict:
    """
    Main entry point. Given an Instagram post URL:
    1. Extracts shortcode
    2. Uses instaloader to fetch metadata + caption
    3. Downloads video (yt-dlp first, falls back to instaloader's built-in)
    4. Downloads thumbnail
    5. Returns a dict ready for the database

    Public posts work without login.
    For private posts or your own saved feed, set INSTAGRAM_USERNAME above
    and run `instaloader --login YOUR_USERNAME` once to save a session file.
    """
    shortcode = extract_shortcode(instagram_url)

    # --- Metadata extraction via instaloader ---
    L = instaloader.Instaloader(
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        quiet=True,
    )

    # Load saved session if username is configured
    if INSTAGRAM_USERNAME:
        try:
            L.load_session_from_file(INSTAGRAM_USERNAME)
        except FileNotFoundError:
            print(
                f"Warning: No saved session for '{INSTAGRAM_USERNAME}'. "
                "Run: instaloader --login YOUR_USERNAME"
            )

    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
    except instaloader.exceptions.QueryReturnedNotFoundException:
        raise RuntimeError(
            "Post not found. It may be private, deleted, or the URL is incorrect."
        )
    except instaloader.exceptions.InstaloaderException as e:
        raise RuntimeError(f"Could not fetch post from Instagram: {e}")

    caption = post.caption or ""
    author = post.owner_username or "unknown"

    title = infer_title(caption, author)
    post_date = (
        post.date_utc.isoformat() if post.date_utc else datetime.utcnow().isoformat()
    )

    # --- Video download: try yt-dlp, fall back to instaloader ---
    video_path = None
    if post.is_video:
        video_path = download_video_ytdlp(instagram_url, media_dir, shortcode)
        if not video_path:
            print("yt-dlp failed, trying instaloader fallback…")
            video_path = download_video_instaloader(post, media_dir, shortcode)

    # --- Thumbnail ---
    thumbnail_path = download_thumbnail(post, media_dir, shortcode)

    return {
        "shortcode": shortcode,
        "title": title,
        "caption": caption,
        "author": author,
        "post_date": post_date,
        "video_path": video_path,
        "thumbnail_path": thumbnail_path,
    }

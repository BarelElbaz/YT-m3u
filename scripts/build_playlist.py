#!/usr/bin/env python3
"""
Generate playlist.m3u8 from a YouTube playlist
"""
import json, subprocess, pathlib, tempfile, os, sys
import concurrent.futures

PLAYLIST_ID = os.getenv("YT_PLAYLIST_ID") or sys.exit("YT_PLAYLIST_ID not set")
OUT_FILE     = pathlib.Path("public/playlist.m3u8")      # GitHub Pages root
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

def rows(cmd):
    res = subprocess.check_output(cmd, text=True)
    for line in res.splitlines(): yield line.strip()

print("Fetching video IDs …")
ids = list(rows([
    "yt-dlp", "-j", "--flat-playlist",
    f"https://www.youtube.com/playlist?list={PLAYLIST_ID}"
]))          # each line is a JSON record

print(f"{len(ids)} items found; resolving HLS URLs …")
tmp = tempfile.NamedTemporaryFile("w", delete=False)
tmp.write("#EXTM3U\n")

def fetch_hls(rec):
    """Return (video_id, url_or_None) for a playlist item."""
    vid = rec["id"]
    try:
        url = subprocess.check_output(
            ["yt-dlp", "-gS", "proto:m3u8", f"https://youtu.be/{vid}"],
            text=True,
            stderr=subprocess.DEVNULL      # suppress noisy yt‑dlp output
        ).strip()
        return vid, url
    except subprocess.CalledProcessError:
        # Video unavailable, region‑blocked, etc. – skip but continue
        print(f"Skipping unavailable video {vid}", file=sys.stderr)
        return vid, None

# Fetch HLS master URLs concurrently (8 workers is a good default for GH runners)
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    results = list(
        pool.map(fetch_hls, map(json.loads, ids))
    )

# Write the playlist in the *original* order, skipping missing videos
for idx, (vid, url) in enumerate(results, 1):
    if url:
        tmp.write(f"#EXTINF:-1,{vid}\n{url}\n")

tmp.flush()
tmp.close()
pathlib.Path(tmp.name).replace(OUT_FILE)
print(f"playlist.m3u8 written with {sum(1 for _, u in results if u)} items "
      f"(skipped {sum(1 for _, u in results if u is None)})")
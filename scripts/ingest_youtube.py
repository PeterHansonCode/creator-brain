#!/usr/bin/env python3
"""Turn downloaded YouTube auto-caption files into creator-brain sources.

Expects captions already downloaded via yt-dlp into:
    ingest_captions/<advisor>/*.vtt      (advisor in: hormozi, naval, kallaway)

Writes:
    data/sample/sources.json         (replaces the placeholder corpus)
    data/sample/ingest-summary.json  (human-readable review list)
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPTIONS_DIR = ROOT / "ingest_captions"
OUT_PATH = ROOT / "data/sample/sources.json"
SUMMARY_PATH = ROOT / "data/sample/ingest-summary.json"

ADVISOR_NAMES = {"hormozi": "Alex Hormozi", "naval": "Naval Ravikant", "kallaway": "Kallaway"}

TIME_RE = re.compile(r"\d{2}:\d{2}:\d{2}\.\d{3}\s*-->")
TAG_RE = re.compile(r"<[^>]+>")
ID_RE = re.compile(r"\[([A-Za-z0-9_-]{11})\]$")


def clean_vtt(path: Path) -> str:
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    seen, out = set(), []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        if TIME_RE.search(line) or line.isdigit():
            continue
        line = TAG_RE.sub("", line).strip()
        if line and line not in seen:
            seen.add(line)
            out.append(line)
    return " ".join(out)


def video_url(stem: str) -> str:
    m = ID_RE.search(stem)
    return f"https://www.youtube.com/watch?v={m.group(1)}" if m else ""


def main():
    if not CAPTIONS_DIR.exists():
        print(f"No {CAPTIONS_DIR} folder found — run the yt-dlp download commands first.")
        sys.exit(1)

    sources, summary = [], []
    for advisor_dir in sorted(CAPTIONS_DIR.iterdir()):
        advisor = advisor_dir.name
        if not advisor_dir.is_dir() or advisor not in ADVISOR_NAMES:
            continue
        for vtt in sorted(advisor_dir.glob("*.vtt")):
            text = clean_vtt(vtt)
            words = text.split()
            if len(words) < 40:
                print(f"skip (too short, {len(words)} words): {vtt.name}")
                continue
            words = words[:15000]  # stay well under the 100k-char field cap
            text = " ".join(words)
            stem = vtt.stem.rsplit(".", 1)[0]  # strip the .en / .en-orig language suffix
            title = re.sub(r"\s*\[[A-Za-z0-9_-]{11}\]$", "", stem)
            url = video_url(stem) or "https://www.youtube.com/"
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "video"
            source_id = f"{advisor}-{slug}-{hashlib.sha256(vtt.name.encode()).hexdigest()[:6]}"
            sources.append({
                "source_id": source_id,
                "advisor_id": advisor,
                "title": title,
                "url": url,
                "text": text,
                "attribution": (f"Auto-generated YouTube caption transcript of a public "
                                 f"{ADVISOR_NAMES[advisor]} video, cleaned for ingestion; "
                                 "not a manually verified quotation."),
            })
            summary.append({"source_id": source_id, "advisor_id": advisor, "title": title,
                             "url": url, "word_count": len(words),
                             "preview": " ".join(words[:30])})

    if not sources:
        print("No usable captions found under ingest_captions/<advisor>/*.vtt.")
        sys.exit(1)

    OUT_PATH.write_text(json.dumps(sources, indent=2), encoding="utf-8")
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {len(sources)} sources to {OUT_PATH.relative_to(ROOT)}")
    for row in summary:
        print(f"- [{row['advisor_id']}] {row['title']} ({row['word_count']} words)")


if __name__ == "__main__":
    main()

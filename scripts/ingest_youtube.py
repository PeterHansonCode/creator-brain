#!/usr/bin/env python3
"""Turn downloaded YouTube captions (+ any manual transcripts) into creator-brain sources.

Expects captions already downloaded via yt-dlp into:
    ingest_captions/<advisor>/*.vtt      (advisor in: hormozi, naval, kallaway)
A manually-sourced plain-text transcript can also be dropped in as *.txt in
the same folder, named the same way as the auto-downloaded files:
    "Video Title [videoID].txt"

Naval is intentionally skipped here -- his YouTube episodes are co-hosted
(Nivi speaks throughout, sometimes with a guest) and auto-captions carry no
speaker labels, so there's no way to cleanly separate his words from
theirs. His corpus instead comes from scripts/ingest_nav_al.py, which reads
his own site's speaker-labeled write-ups. If data/sample/naval_site_sources.json
exists (produced by that script), it's merged in here automatically.

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
NAVAL_SITE_SOURCES = ROOT / "data/sample/naval_site_sources.json"

ADVISOR_NAMES = {"hormozi": "Alex Hormozi", "naval": "Naval Ravikant", "kallaway": "Kallaway"}
SKIP_ADVISORS = {"naval"}  # sourced from nav.al instead -- see docstring

TIME_RE = re.compile(r"\d{2}:\d{2}:\d{2}\.\d{3}\s*-->")
TAG_RE = re.compile(r"<[^>]+>")
ID_RE = re.compile(r"\[([A-Za-z0-9_-]{11})\]$")


def clean_transcript(path: Path) -> str:
    """Strip VTT syntax if present; degrades gracefully on plain .txt too."""
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    out = []
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
            continue
        if TIME_RE.search(line) or line.isdigit():
            continue
        line = TAG_RE.sub("", line).strip()
        line = (line.replace("&nbsp;", " ").replace("&amp;", "&")
                    .replace("&#39;", "'").replace("&quot;", '"')
                    .replace("&gt;", ">").replace("&lt;", "<"))
        # >> / << are the caption format's own speaker-change marker, not
        # spoken words -- drop standalone runs of them.
        line = re.sub(r"(?:^|\s)[<>]{2,}(?:\s|$)", " ", line)
        line = " ".join(line.split())
        # Rolling VTT captions repeat the immediately preceding cue's text
        # verbatim as later cues grow it word by word -- only that adjacent
        # repetition should be dropped. A global "seen anywhere" set (the
        # previous approach) also silently dropped genuine repeated speech
        # elsewhere in a long video, e.g. someone saying "I agree" twice.
        if line and line != (out[-1] if out else None):
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
        if advisor in SKIP_ADVISORS:
            print(f"skipping ingest_captions/{advisor}/ (sourced separately, see script docstring)")
            continue
        files = sorted(advisor_dir.glob("*.vtt")) + sorted(advisor_dir.glob("*.txt"))
        for clip in files:
            text = clean_transcript(clip)
            words = text.split()
            if len(words) < 40:
                print(f"skip (too short, {len(words)} words): {clip.name}")
                continue
            words = words[:15000]  # stay well under the 100k-char field cap
            text = " ".join(words)
            stem = clip.stem.rsplit(".", 1)[0] if clip.suffix == ".vtt" else clip.stem  # strip .en / .en-orig
            title = re.sub(r"\s*\[[A-Za-z0-9_-]{11}\]$", "", stem)
            url = video_url(stem) or "https://www.youtube.com/"
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40] or "video"
            source_id = f"{advisor}-{slug}-{hashlib.sha256(clip.name.encode()).hexdigest()[:6]}"
            if clip.suffix == ".txt":
                attribution = (f"Manually sourced transcript of a public {ADVISOR_NAMES[advisor]} video "
                                "(YouTube did not provide auto-captions for it); cleaned for ingestion, "
                                "not independently re-verified against the original audio.")
            else:
                attribution = (f"Auto-generated YouTube caption transcript of a public "
                                f"{ADVISOR_NAMES[advisor]} video, cleaned for ingestion; "
                                "not a manually verified quotation.")
            sources.append({
                "source_id": source_id,
                "advisor_id": advisor,
                "title": title,
                "url": url,
                "text": text,
                "attribution": attribution,
            })
            summary.append({"source_id": source_id, "advisor_id": advisor, "title": title,
                             "url": url, "word_count": len(words),
                             "preview": " ".join(words[:30])})

    if NAVAL_SITE_SOURCES.exists():
        naval_sources = json.loads(NAVAL_SITE_SOURCES.read_text(encoding="utf-8"))
        sources.extend(naval_sources)
        for s in naval_sources:
            summary.append({"source_id": s["source_id"], "advisor_id": s["advisor_id"], "title": s["title"],
                             "url": s["url"], "word_count": len(s["text"].split()),
                             "preview": " ".join(s["text"].split()[:30])})
        print(f"merged {len(naval_sources)} Naval sources from {NAVAL_SITE_SOURCES.relative_to(ROOT)}")
    else:
        print(f"note: {NAVAL_SITE_SOURCES.relative_to(ROOT)} not found -- run ingest_nav_al.py first "
              "if you want Naval included")

    if not sources:
        print("No usable sources found.")
        sys.exit(1)

    OUT_PATH.write_text(json.dumps(sources, indent=2), encoding="utf-8")
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {len(sources)} sources to {OUT_PATH.relative_to(ROOT)}")
    for row in summary:
        print(f"- [{row['advisor_id']}] {row['title']} ({row['word_count']} words)")


if __name__ == "__main__":
    main()

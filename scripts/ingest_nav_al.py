#!/usr/bin/env python3
"""Fetch curated nav.al pages and extract ONLY Naval's own words.

nav.al publishes podcast write-ups as continuous prose: a paragraph is
explicitly labeled "<strong>Naval:</strong> ..." (or "Nivi:", or a guest's
name) only at the START of that person's turn. Paragraphs that follow
with no label are a CONTINUATION of whoever spoke last. So this walks
paragraphs in order, tracks "who is currently speaking", and keeps text
only while that's Naval -- never inventing or reattributing anything.

Usage:
    python scripts/ingest_nav_al.py
Writes:
    data/sample/naval_site_sources.json  (review this before merging)
"""
import hashlib
import json
import re
import sys
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "data/sample/naval_site_sources.json"

# Curated ~25 pages: the two compiled essays (rich, happiness) + standalone
# pieces spanning wealth/business building-blocks, angel investing, and
# recent life-wisdom/AI posts. Swap freely -- this is a starting list.
PAGES = [
    ("rich", "How to Get Rich"),
    ("happiness", "Happiness"),
    ("judgment", "Judgment Is the Decisive Skill"),
    ("kelly-criterion", "Kelly Criterion: Avoid Ruin"),
    ("principal-agent", "Principal-Agent Problem: Act Like an Owner"),
    ("schelling-point", "Schelling Point: Cooperating Without Communicating"),
    ("ethics", "Being Ethical Is Long-Term Greedy"),
    ("business-models", "Pick a Business Model With Leverage"),
    ("accountability-leverage", "Embrace Accountability to Get Leverage"),
    ("reject-advice", "Reject Most Advice"),
    ("stupid-games", "Play Stupid Games, Win Stupid Prizes"),
    ("envy", "Envy Can Be Useful, or It Can Eat You Alive"),
    ("hourly-rate", "Set an Aspirational Hourly Rate"),
    ("working-ourselves", "We Should All Be Working for Ourselves"),
    ("competition-authenticity", "Escape Competition Through Authenticity"),
    ("angel-1", "How to Angel Invest, Part 1"),
    ("angel-2", "How to Angel Invest, Part 2"),
    ("agency", "Blame Yourself for Everything, and Preserve Your Agency"),
    ("curate-people", "Curate People"),
    ("in-the-arena", "In the Arena"),
    ("simplest", "Find the Simplest Thing That Works"),
    ("reflect", "Pause, Reflect, See How Well it Did"),
    ("enjoy", "You Have to Enjoy It a Lot"),
    ("ai", "A Motorcycle for the Mind"),
    ("tokens", "Waste Tokens, Save Time"),
]

TAG_RE = re.compile(r"<[^>]+>")
LABEL_RE = re.compile(r"^\s*([A-Za-z][A-Za-z .]{1,24}?)\s*:\s*$")
PARA_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.S)


def clean(text: str) -> str:
    text = TAG_RE.sub("", text)
    text = text.replace("&nbsp;", " ").replace("&#8217;", "’").replace("&#8220;", "“")
    text = text.replace("&#8221;", "”").replace("&amp;", "&")
    return re.sub(r"\s+", " ", text).strip()


class _ParagraphRuns(HTMLParser):
    """Splits one paragraph's inner HTML into consecutive (text, is_bold)
    runs, where is_bold is True while inside ANY <strong>/<b> ancestor at
    any nesting depth.

    Replaces an earlier approach that used a single anchored regex to check
    whether a paragraph's raw HTML started with a literal <strong>/<b> tag.
    That regex was patched once already to tolerate one specific wrapper
    pattern (<span><strong>Name:</strong></span>), but nav.al also uses the
    REVERSE nesting (<strong><span>Name:</span></strong>) elsewhere, which
    the patched regex still can't see -- lazily matching raw HTML text
    between <strong> and </strong> just isn't tag-aware, no matter how many
    wrapper variants get added to the regex. Walking the actual parse tree
    with a real (if minimal) HTML parser handles arbitrary nesting in either
    direction, and any nesting depth, without needing a new special case
    each time nav.al's markup turns out to nest one way we hadn't seen yet.
    """
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._bold_depth = 0
        self.runs: list = []

    def handle_starttag(self, tag, attrs):
        if tag in ("strong", "b"):
            self._bold_depth += 1

    def handle_endtag(self, tag):
        if tag in ("strong", "b") and self._bold_depth > 0:
            self._bold_depth -= 1

    def handle_data(self, data):
        is_bold = self._bold_depth > 0
        if self.runs and self.runs[-1][1] == is_bold:
            self.runs[-1][0] += data
        else:
            self.runs.append([data, is_bold])


def paragraph_runs(raw_html: str) -> list:
    """Returns [(text, is_bold), ...] for one paragraph's inner HTML, with
    whitespace collapsed and pure-whitespace runs dropped."""
    parser = _ParagraphRuns()
    parser.feed(raw_html)
    parser.close()
    runs = [(re.sub(r"\s+", " ", text), is_bold) for text, is_bold in parser.runs]
    return [(text, is_bold) for text, is_bold in runs if text.strip()]


def extract_naval_text(html: str, slug: str = "", debug_dir: Path = None):
    """Returns (text, note) where note is None or a short string worth surfacing."""
    start = html.find('<div class="content">')
    if start == -1:
        start = html.find('class="entry-content')
    if start == -1:
        if debug_dir is not None:
            debug_dir.mkdir(parents=True, exist_ok=True)
            (debug_dir / f"{slug}.html").write_text(html, encoding="utf-8")
        return "", "no content container found on page (raw HTML saved for review)"
    end = len(html)
    for marker in ('</article>', 'class="post-navigation', 'id="comments"',
                   'class="related-posts', 'class="site-footer'):
        i = html.find(marker, start)
        if i != -1:
            end = min(end, i)
    body = html[start:end]

    paras = PARA_RE.findall(body)
    current_speaker = None
    saw_any_label = False
    kept = []
    unlabeled_fallback = []
    for raw in paras:
        runs = paragraph_runs(raw)
        if not runs:
            continue
        first_text, first_bold = runs[0]
        stripped_first = first_text.strip()
        if first_bold and LABEL_RE.match(stripped_first):
            # A new speaker turn begins here, however the label element
            # happens to be nested -- everything after the bold run is that
            # speaker's own paragraph-opening words.
            saw_any_label = True
            current_speaker = stripped_first.rstrip(":").strip()
            rest_clean = " ".join(t.strip() for t, _ in runs[1:]).strip()
            if current_speaker.lower() == "naval" and rest_clean:
                kept.append(rest_clean)
            continue
        if first_bold and len(runs) == 1:
            # Whole paragraph is just a bolded pull-quote/subheading (no
            # colon, nothing after it) -> skip, don't change speaker.
            continue
        # Either no bold at the start, or a bolded lead-in phrase that isn't
        # a "Name:" label with more text following it -> the whole paragraph
        # is ordinary continuation text of whoever is currently speaking.
        text = " ".join(t.strip() for t, _ in runs).strip()
        if text:
            unlabeled_fallback.append(text)
        if current_speaker and current_speaker.lower() == "naval":
            if text:
                kept.append(text)

    if kept:
        return " ".join(kept), None

    if not saw_any_label and unlabeled_fallback:
        # No speaker turns marked anywhere on this page at all -- these pages
        # are single-topic solo excerpts (no host/guest dialogue), so the
        # whole thing is presumptively Naval's own writing. Flagged in the
        # printed output so it can be spot-checked.
        return " ".join(unlabeled_fallback), "no speaker labels on page -- treated entire page as solo Naval text"

    if debug_dir is not None and len(paras) == 0:
        debug_dir.mkdir(parents=True, exist_ok=True)
        (debug_dir / f"{slug}.html").write_text(html, encoding="utf-8")
    return "", ("found paragraphs but none attributable to Naval (raw HTML saved for review)" if paras
                else "no paragraphs matched at all (raw HTML saved for review)")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")


def main():
    debug_dir = ROOT / "data/sample/naval_site_debug_html"
    sources, summary = [], []
    for slug, fallback_title in PAGES:
        url = f"https://nav.al/{slug}"
        try:
            html = fetch(url)
        except Exception as e:
            print(f"SKIP {slug}: fetch failed ({e})")
            continue
        text, note = extract_naval_text(html, slug=slug, debug_dir=debug_dir)
        words = text.split()
        if len(words) < 80:
            print(f"WARN {slug}: only {len(words)} words extracted"
                  + (f" -- {note}" if note else " -- check this page manually"))
            if not words:
                continue
        elif note:
            print(f"NOTE {slug}: {note}")
        title_m = re.search(r'<h1[^>]*class="[^"]*entry-title[^"]*"[^>]*>(.*?)</h1>', html, re.S)
        title = clean(title_m.group(1)) if title_m else fallback_title
        words = words[:15000]
        text = " ".join(words)
        source_id = f"naval-{slug}"
        if note and "solo Naval text" in note:
            # This page had no speaker labels anywhere, so nothing was
            # actually filtered by speaker turn -- the whole page was kept
            # on the presumption that an unlabeled page is Naval's own solo
            # writing. Saying "kept only paragraphs attributed to him by
            # speaker label" here would overclaim what the parser did.
            attribution = (
                "Text extracted from Naval's own site (nav.al). This page had no speaker "
                "labels at all, so the whole page was kept as presumed solo Naval writing "
                "rather than filtered by speaker turn -- not a manually verified quotation."
            )
        else:
            attribution = (
                "Text extracted from Naval's own site (nav.al), keeping only paragraphs "
                "attributed to him (by explicit speaker label or as a continuation of his "
                "own labeled turn); co-host/guest dialogue and site narration outside his "
                "turns is excluded. Not a manually verified quotation."
            )
        sources.append({
            "source_id": source_id,
            "advisor_id": "naval",
            "title": title,
            "url": url,
            "text": text,
            "attribution": attribution,
        })
        summary.append({"source_id": source_id, "title": title, "url": url, "word_count": len(words)})
        print(f"OK   {slug}: {len(words)} words -- {title}")
        time.sleep(1)  # be polite to nav.al

    if not sources:
        print("Nothing extracted.")
        sys.exit(1)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(sources, indent=2), encoding="utf-8")
    print(f"\nWrote {len(sources)} sources to {OUT_PATH.relative_to(ROOT)}")
    total_words = sum(s["word_count"] for s in summary)
    print(f"Total words across all pages: {total_words}")


if __name__ == "__main__":
    main()

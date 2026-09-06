"""Regression tests for the nav.al speaker-attribution parser.

No network access needed: these build small synthetic HTML fragments that
mirror nav.al's real page structure (including the inline-wrapped speaker
label found on /rich in the wild) and check what extract_naval_text keeps.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ingest_nav_al import extract_naval_text  # noqa: E402

CONTAINER = '<div class="content">{body}</div>'


def page(body: str) -> str:
    return CONTAINER.format(body=body)


def test_plain_strong_label_is_kept_for_naval():
    html = page(
        '<p class="wp-block-paragraph"><strong>Naval:</strong> Build character so luck becomes deterministic.</p>'
    )
    text, note = extract_naval_text(html)
    assert "Build character" in text
    assert note is None


def test_old_template_b_tag_label_is_kept_for_naval():
    html = page('<p><b>Naval: </b>Wealth is assets that earn while you sleep.</p>')
    text, note = extract_naval_text(html)
    assert "Wealth is assets" in text


def test_span_wrapped_label_switches_speaker_away_from_naval():
    # This is the real bug: nav.al/rich wraps some labels in an inline span,
    # e.g. <span class="s4"><strong>Nivi:</strong></span>. Before the fix,
    # BOLD_RE never matched this, so the parser thought no speaker change
    # happened and kept attributing the host's words -- and everything
    # after them, until the next *recognized* label -- to Naval.
    html = page(
        '<p><strong>Naval:</strong> His actual view on luck.</p>'
        '<p><span class="s4"><strong>Nivi:</strong></span> That is an interesting take on luck.</p>'
        '<p>Do you think that generalizes to other people too?</p>'
        '<p><strong>Naval:</strong> Yes, I think it does generalize well.</p>'
    )
    text, note = extract_naval_text(html)
    assert "interesting take" not in text
    assert "generalizes to other people" not in text
    assert "His actual view on luck" in text
    assert "generalize well" in text


def test_unlabeled_continuation_keeps_following_naval_speaker():
    html = page(
        '<p><strong>Naval:</strong> First sentence of a longer answer.</p>'
        '<p>Second sentence, still Naval, no new label here.</p>'
    )
    text, note = extract_naval_text(html)
    assert "First sentence" in text
    assert "Second sentence" in text


def test_page_with_no_labels_at_all_falls_back_to_solo_essay():
    html = page('<p>An essay with no dialogue markers anywhere on the page.</p>')
    text, note = extract_naval_text(html)
    assert "essay with no dialogue" in text
    assert note is not None and "solo" in note


def test_reverse_nested_label_switches_speaker_away_from_naval():
    # A second independent review reproduced a case the first fix missed:
    # nav.al also nests some labels the OTHER way around, <strong><span>
    # Nivi:</span></strong>, rather than <span><strong>...</strong></span>.
    # A single anchored regex tuned for one nesting order can't see the
    # other -- this needs the run-based parser to keep working regardless
    # of which element wraps which.
    html = page(
        '<p><strong>Naval:</strong> His actual view on luck.</p>'
        '<p><strong><span class="s4">Nivi:</span></strong> That is an interesting take on luck.</p>'
        '<p>Do you think that generalizes to other people too?</p>'
        '<p><strong>Naval:</strong> Yes, I think it does generalize well.</p>'
    )
    text, note = extract_naval_text(html)
    assert "interesting take" not in text
    assert "generalizes to other people" not in text
    assert "His actual view on luck" in text
    assert "generalize well" in text


def test_label_with_trailing_nbsp_inside_the_bold_run_is_still_recognized():
    # Some pages put a non-breaking space *inside* the bold element itself,
    # e.g. <strong>Naval:&nbsp;</strong>, rather than after it. Python's
    # html.parser decodes &nbsp; to U+00A0 before LABEL_RE ever sees it, and
    # str.strip() treats U+00A0 as whitespace too, so this should match the
    # same as a plain ASCII space would.
    html = page('<p><strong>Naval:&nbsp;</strong>Wealth compounds while you sleep.</p>')
    text, note = extract_naval_text(html)
    assert "Wealth compounds" in text

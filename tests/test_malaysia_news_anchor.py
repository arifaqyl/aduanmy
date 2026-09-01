"""Malaysian newsroom bylines as a country anchor.

The news lane was collecting rows and having every one discarded. "LRT" alone
is correctly generic — LRT systems exist worldwide — so a Malaysian headline
naming a line but no station had nothing to anchor it to Malaysia and was
dropped. Google News titles carry the outlet, so provenance was already in the
text and simply unused.

The risk in fixing this is admitting foreign transit news, so the foreign
cases below matter more than the Malaysian ones.
"""
from __future__ import annotations

import pytest

from app.core.malaysia_transport_scope import has_strict_malaysia_transport_anchor
from app.pipeline.extract import extract_entity, extract_location


def anchored(text: str) -> bool:
    return has_strict_malaysia_transport_anchor(
        text,
        entity=extract_entity(text, "transport"),
        location=extract_location(text),
    )


@pytest.mark.parametrize("headline", [
    "Rush hour chaos: LRT fault sparks outrage on social media - NST Online",
    "Monorel tergendala akibat gangguan bekalan kuasa - Kosmo Digital",
    "Train derails on Ampang-Sri Petaling line - Free Malaysia Today",
    "MRT service disrupted this morning - Bernama",
    "Laluan Monorel kembali beroperasi seperti biasa - MalaysiaGazette",
])
def test_malaysian_outlet_anchors_a_headline(headline):
    assert anchored(headline) is True


@pytest.mark.parametrize("headline", [
    "LRT delays reported in Manila after signal fault - Reuters",
    "Delhi Metro suspends service on Blue Line - Times of India",
    "Singapore MRT hit by train fault during evening peak - CNA",
    "Sydney train delays after signalling failure - ABC News",
])
def test_foreign_transit_news_is_still_rejected(headline):
    """The whole point of the strict anchor. Widening it must not let these in."""
    assert anchored(headline) is False


def test_rider_post_with_a_station_still_anchors_without_an_outlet():
    assert anchored("stuck at masjid jamek 15 min already lrt not moving") is True


def test_bare_generic_line_mention_is_not_enough():
    """No outlet, no station, no state — nothing ties this to Malaysia."""
    assert anchored("the LRT was delayed again today") is False


def test_the_star_is_deliberately_excluded():
    """Collides with foreign mastheads of the same name, so it must not act as
    a Malaysia anchor on its own."""
    from app.core.malaysia_transport_scope import MALAYSIAN_NEWS_OUTLETS

    assert "the star" not in [o.lower() for o in MALAYSIAN_NEWS_OUTLETS]

"""Static checks for the public static sites (docs/ and tn-live-jobs/public/).

These run offline: they parse the committed HTML/CSS/XML and never contact a
job portal, Telegram or the deployed backend.
"""
import json
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
TN = ROOT / "tn-live-jobs" / "public"


class _IdCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name == "id" and value:
                self.ids.append(value)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _duplicate_ids(html: str):
    parser = _IdCollector()
    parser.feed(html)
    seen, dupes = set(), set()
    for value in parser.ids:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return dupes


def test_public_pages_have_no_duplicate_ids():
    assert _duplicate_ids(_read(DOCS / "index.html")) == set()
    assert _duplicate_ids(_read(TN / "index.html")) == set()


def test_structured_data_is_valid_json():
    for page in (DOCS / "index.html", TN / "index.html"):
        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            _read(page),
            re.S,
        )
        assert blocks, f"expected a JSON-LD block in {page}"
        for block in blocks:
            data = json.loads(block)
            assert data["@type"] == "WebSite"


def test_docs_social_and_canonical_metadata():
    html = _read(DOCS / "index.html")
    for needle in ('rel="canonical"', "og:title", "og:description", "twitter:card"):
        assert needle in html


def test_robots_and_sitemap_are_present_and_valid():
    assert "Sitemap:" in _read(DOCS / "robots.txt")
    root = ET.parse(DOCS / "sitemap.xml").getroot()
    assert root.tag.endswith("urlset")
    assert root.find("{http://www.sitemaps.org/schemas/sitemap/0.9}url") is not None
    assert (TN / "robots.txt").exists()


def test_saved_job_restore_is_guarded_against_blocked_storage():
    html = _read(DOCS / "index.html")
    assert "let savedJobIds = JSON.parse(localStorage" not in html, (
        "unguarded restore aborts the script when storage is blocked"
    )
    assert re.search(
        r"try \{\s*savedJobIds = JSON\.parse\(localStorage\.getItem\('myjob_saved'\)",
        html,
    )


def test_search_input_has_accessible_name():
    html = _read(DOCS / "index.html")
    assert 'for="searchInput"' in html
    assert 'aria-label="Search jobs by role, company, city or keyword"' in html


def test_skip_links_and_noscript_fallbacks():
    docs = _read(DOCS / "index.html")
    tn = _read(TN / "index.html")
    assert "Skip to job feed" in docs and "<noscript>" in docs
    assert "Skip to jobs" in tn and "<noscript>" in tn

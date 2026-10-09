"""Offline checks for the Flask-served HTML templates.

Run with:
    python3 -m unittest tests.test_dashboard_templates -v

These do not start the bot, touch the network, or need any credentials.
"""

import ast
import os
import re
import subprocess
import unittest

from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "templates")
MAIN_PY = os.path.join(ROOT, "main.py")


# Values for the context main.py hands to render_template_string. Anything the
# template uses that is NOT supplied by main.py will raise under StrictUndefined,
# which is exactly the drift this test is meant to catch.
CONTEXT_VALUES = {
    "gemini_status": "ONLINE",
    "groq_status": "OFFLINE",
    "active_key_num": 1,
    "gemini_key_count": 2,
    "success_pct": 50,
    "stroke_offset": 169.6,
    "total_applied": 10,
    "total_skipped": 4,
    "qa_size": 7,
    "active_chat_id": "12345",
    "imap_status": "OFFLINE",
    "ghost_mode_active": False,
    "channels_html": "<div>x</div>",
    "recent_jobs_html": "<p>y</p>",
    "HANDOFF_URL": "https://example.com/job",
    "notion_url": "https://notion.so/abc",
    "stats": {"applied": 10, "skipped": 4, "failed": 1},
    "applied": ["a", "b"],
    "TARGET_CHANNEL": "JobSkull",
    "TARGET_CHANNELS": ["JobSkull", "jobopenings_india"],
    "RESUME_FILE": "resume.pdf",
    "BOT_PAUSED": False,
    "len": len,
    "os": os,
}


def _context_keys_passed_by_main():
    """Read the keyword names of the render_template_string(...) call in main.py."""
    with open(MAIN_PY, encoding="utf-8") as handle:
        source = handle.read()
    tree = ast.parse(source)
    keys = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "render_template_string":
            keys.extend(kw.arg for kw in node.keywords if kw.arg)
    return keys


def _render(template_name, **extra):
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        undefined=StrictUndefined,
        autoescape=False,
    )
    return env.get_template(template_name).render(**extra)


class DashboardTemplateTests(unittest.TestCase):
    def setUp(self):
        keys = _context_keys_passed_by_main()
        self.assertTrue(keys, "could not find the render_template_string call in main.py")
        context = {}
        for key in keys:
            context[key] = CONTEXT_VALUES.get(key, "value")
        self.context = context
        self.rendered = _render("dashboard.html", **self.context)

    def test_every_variable_used_by_the_template_is_supplied(self):
        # StrictUndefined makes an unknown variable raise instead of rendering blank.
        self.assertIn("Elite Job Bot", self.rendered)

    def test_admin_panel_is_not_indexable(self):
        self.assertIn('name="robots" content="noindex, nofollow"', self.rendered)

    def test_accessibility_affordances_survive(self):
        for needle in (
            'class="skip-link"',
            "prefers-reduced-motion",
            ":focus-visible",
            'role="status" aria-live="polite"',
            'role="log"',
            'aria-busy="true"',
        ):
            self.assertIn(needle, self.rendered, f"missing accessibility affordance: {needle}")

    def test_no_third_party_texture_requests(self):
        self.assertNotIn("transparenttextures.com", self.rendered)
        self.assertIn("carbon-weave", self.rendered)

    def test_scraped_radar_data_is_escaped_before_innerHTML(self):
        # The radar renderer must escape every field it interpolates and check URLs.
        self.assertIn("function escapeHtml(", self.rendered)
        self.assertIn("function safeUrl(", self.rendered)
        for field in ("j.title", "j.company", "j.location", "j.description", "src"):
            self.assertIn(f"escapeHtml({field})", self.rendered, f"{field} is not escaped")
        self.assertIn("safeUrl(j.link)", self.rendered)
        # The old vulnerable shape must be gone.
        self.assertNotIn('href="${j.link}"', self.rendered)

    def test_rendered_inline_script_is_valid_javascript(self):
        try:
            subprocess.run(["node", "--version"], capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("node is not available")

        blocks = re.findall(r"<script(?![^>]*\bsrc=)([^>]*)>(.*?)</script>", self.rendered, re.S)
        self.assertTrue(blocks, "expected an inline script")
        for index, (attrs, body) in enumerate(blocks):
            if "ld+json" in attrs:
                continue
            path = os.path.join("/tmp", f"dashboard_inline_{index}.js")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(body)
            result = subprocess.run(["node", "--check", path], capture_output=True, text=True)
            self.assertEqual(
                result.returncode, 0,
                f"inline script {index} does not parse:\n{result.stderr[:800]}",
            )


class MiniAppTemplateTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(TEMPLATES, "miniapp.html"), encoding="utf-8") as handle:
            self.html = handle.read()

    def test_miniapp_is_served_verbatim_so_it_must_not_contain_jinja(self):
        # main.py reads this file and returns it unchanged (no render_template_string),
        # so any Jinja placeholder would be shipped literally to users.
        self.assertNotIn("{{", self.html)
        self.assertNotIn("{%", self.html)

    def test_miniapp_allows_zoom_and_announces_state(self):
        viewport = re.search(r'<meta name="viewport" content="([^"]+)"', self.html).group(1)
        self.assertNotIn("user-scalable=no", viewport)
        self.assertIn("prefers-reduced-motion", self.html)
        self.assertIn('aria-live="polite"', self.html)

    def test_miniapp_checks_url_schemes_before_opening(self):
        self.assertIn("function safeUrl(", self.html)
        self.assertIn("const jobLink = safeUrl(job.link)", self.html)
        self.assertIn("data-apply-url=", self.html)
        # The old shape interpolated the raw scraped URL into a JS string literal.
        self.assertNotIn("openApplyLink('${job.link}'", self.html)


if __name__ == "__main__":
    unittest.main()

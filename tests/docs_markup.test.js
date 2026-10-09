/**
 * Static checks on the published GitHub Pages document (docs/index.html).
 *
 * These guard the SEO/accessibility basics that are easy to regress and that no
 * amount of runtime testing would catch (a missing canonical tag, for example).
 *
 * Run with:  npm install && npm run test:docs
 */
'use strict';

const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const DOCS_DIR = path.join(__dirname, '..', 'docs');
const html = fs.readFileSync(path.join(DOCS_DIR, 'index.html'), 'utf8');

const metaContent = (name) => {
  const m = html.match(new RegExp(`<meta[^>]+name=["']${name}["'][^>]*content=["']([^"']*)["']`, 'i'))
    || html.match(new RegExp(`<meta[^>]+content=["']([^"']*)["'][^>]*name=["']${name}["']`, 'i'));
  return m ? m[1] : null;
};

const propContent = (prop) => {
  const m = html.match(new RegExp(`<meta[^>]+property=["']${prop}["'][^>]*content=["']([^"']*)["']`, 'i'))
    || html.match(new RegExp(`<meta[^>]+content=["']([^"']*)["'][^>]*property=["']${prop}["']`, 'i'));
  return m ? m[1] : null;
};

test('document declares a language and a single h1', () => {
  assert.match(html, /<html[^>]+lang=["']en["']/i);
  const h1s = html.match(/<h1\b/gi) || [];
  assert.equal(h1s.length, 1, 'exactly one h1 keeps the outline clean');
});

test('viewport allows pinch-zoom (WCAG 1.4.4)', () => {
  const viewport = html.match(/<meta[^>]+name=["']viewport["'][^>]*>/i)[0];
  assert.doesNotMatch(viewport, /user-scalable\s*=\s*no/i);
  assert.doesNotMatch(viewport, /maximum-scale\s*=\s*1/i);
  assert.match(viewport, /width=device-width/);
});

test('core SEO metadata is present', () => {
  const description = metaContent('description');
  assert.ok(description && description.length >= 70, 'meta description should be meaningful');
  assert.match(html, /<link[^>]+rel=["']canonical["'][^>]+href=["']https:\/\//i);
  assert.ok(metaContent('robots'));
  assert.equal(propContent('og:title') !== null, true);
  assert.equal(propContent('og:description') !== null, true);
  assert.equal(propContent('og:url') !== null, true);
  assert.ok(metaContent('twitter:card'));
});

test('structured data blocks are valid JSON-LD', () => {
  const blocks = [...html.matchAll(/<script[^>]+application\/ld\+json[^>]*>([\s\S]*?)<\/script>/gi)];
  assert.ok(blocks.length >= 1, 'expected at least one JSON-LD block');
  for (const [, body] of blocks) {
    const parsed = JSON.parse(body);
    assert.ok(parsed['@context'] === 'https://schema.org');
  }
});

test('keyboard and no-JavaScript fallbacks exist', () => {
  assert.match(html, /class=["']skip-link["']/, 'skip link for keyboard users');
  assert.match(html, /<noscript>/, 'noscript summary for crawlers / JS-off visitors');
  assert.match(html, /prefers-reduced-motion/, 'motion preference is respected');
  assert.match(html, /aria-live=/, 'status updates are announced');
});

test('the job snapshot lives in its own cacheable file', () => {
  assert.match(html, /<script src="\.\/data\/snapshot\.js"><\/script>/);
  assert.ok(!/window\.INITIAL_DATA\s*=\s*\[/.test(html), 'snapshot must not be inlined in the HTML');
  const snapshot = fs.readFileSync(path.join(DOCS_DIR, 'data', 'snapshot.js'), 'utf8');
  assert.match(snapshot, /window\.INITIAL_DATA\s*=\s*\[/);
  assert.ok(html.length < 200 * 1024, `docs/index.html should stay small (got ${html.length} bytes)`);
});

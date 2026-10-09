'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { fetchJson } = require('./src/scraper');

test('JSON transport preserves GET defaults and POST method/body', async () => {
  const server = http.createServer(async (request, response) => {
    let body = '';
    for await (const chunk of request) body += chunk;
    response.setHeader('content-type', 'application/json');
    response.end(JSON.stringify({
      method: request.method,
      contentType: request.headers['content-type'] || null,
      body,
    }));
  });
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  try {
    const url = `http://127.0.0.1:${server.address().port}/jobs`;
    const get = await fetchJson(url, { attempts: 1, timeout: 5000 });
    assert.equal(get.json.method, 'GET');
    assert.equal(get.json.body, '');

    const payload = JSON.stringify({ appliedFacets: {}, limit: 20, offset: 0, searchText: 'Chennai' });
    const post = await fetchJson(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: payload,
      attempts: 1,
      timeout: 5000,
    });
    assert.equal(post.json.method, 'POST');
    assert.equal(post.json.contentType, 'application/json');
    assert.equal(post.json.body, payload);
  } finally { await new Promise((resolve) => server.close(resolve)); }
});

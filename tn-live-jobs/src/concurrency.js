'use strict';

/**
 * Run an async worker over a list with a fixed number of workers.
 *
 * Each item is processed exactly once and results keep the input order.
 * A failure is captured per item instead of stopping the whole batch, so one
 * broken item can never cancel the others.
 */
async function runWithConcurrency(items, limit, worker) {
  const list = Array.isArray(items) ? items : [];
  const results = new Array(list.length);
  const size = Math.max(1, Math.min(Number(limit) || 1, list.length || 1));
  let cursor = 0;

  async function run() {
    while (cursor < list.length) {
      const index = cursor;
      cursor += 1;
      try {
        results[index] = { status: 'fulfilled', value: await worker(list[index], index) };
      } catch (error) {
        results[index] = { status: 'rejected', reason: error };
      }
    }
  }

  await Promise.all(Array.from({ length: size }, run));
  return results;
}

module.exports = { runWithConcurrency };

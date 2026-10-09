'use strict';

/**
 * Order a list of cities so the preferred ones come first, then the rest in
 * their given order, without duplicates. Used to build the search plan so the
 * places that matter most are always reached first.
 */
function orderCities(preferred, cities) {
  const preferredList = (preferred || []).map((city) => String(city).trim().toLowerCase());
  const seen = new Set();
  const preferredCities = [];
  const otherCities = [];

  for (const city of cities || []) {
    const text = String(city || '').trim();
    const key = text.toLowerCase();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    if (preferredList.includes(key)) preferredCities.push(text);
    else otherCities.push(text);
  }
  return preferredCities.concat(otherCities);
}

module.exports = { orderCities };

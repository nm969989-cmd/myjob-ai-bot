'use strict';
// Cover different role/city pairs before repeating a role across every city.
function searchPlan(cities, keywords, limit, offset = 0) {
  const places = [...new Set(cities)], terms = [...new Set(keywords)];
  if (!places.length || !terms.length) return [];
  const total = places.length * terms.length;
  return Array.from({ length: Math.min(total, Math.max(0, Math.floor(limit))) }, (_, n) => {
    const index = ((Math.floor(offset) + n) % total + total) % total;
    const cityIndex = index % places.length;
    return { city: places[cityIndex], keyword: terms[(Math.floor(index / places.length) + cityIndex) % terms.length] };
  });
}
module.exports = { searchPlan };

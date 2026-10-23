/**
 * Convert a complete Reflex component identifier to searchable title words.
 *
 * @param {string} query A trimmed search query.
 * @returns {string} The component's title words, or the unchanged query.
 */
export function normalizeSearchQuery(query) {
  return /^rx\.[a-z]\w*(?:\.[a-z]\w*)*$/i.test(query)
    ? query.slice(3).replace(/[_.]+/g, " ")
    : query;
}

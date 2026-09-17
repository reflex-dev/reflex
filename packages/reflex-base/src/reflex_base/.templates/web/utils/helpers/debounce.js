const debounce_timeout_id = {};

/**
 * Generic debounce helper
 *
 * @param {string} name - the name of the event to debounce
 * @param {function} func - the function to call after debouncing
 * @param {number} delay - the time in milliseconds to wait before calling the function
 */
export default function debounce(name, func, delay) {
  const key = `${name}__${delay}`;
  clearTimeout(debounce_timeout_id[key]);
  debounce_timeout_id[key] = setTimeout(() => {
    func();
    delete debounce_timeout_id[key];
  }, delay);
}

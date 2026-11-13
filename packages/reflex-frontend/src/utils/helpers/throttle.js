const in_throttle = {};

/**
 * Generic throttle helper
 *
 * @param {string} name - the name of the event to throttle
 * @param {number} limit - time in milliseconds between events
 * @returns true if the event is allowed to execute, false if it is throttled
 */
export default function throttle(name, limit) {
  const key = `${name}__${limit}`;
  if (!in_throttle[key]) {
    in_throttle[key] = true;

    setTimeout(() => {
      delete in_throttle[key];
    }, limit);
    // function was not throttled, so allow execution
    return true;
  }
  return false;
}

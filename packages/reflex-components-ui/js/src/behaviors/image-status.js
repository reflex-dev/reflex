// How the load of an image ended, said on the image and on what stands in
// for it, so that their styles show one of the two.
//
// The server renders both: the image lies over its stand-in, so a page shows
// a loaded image before this runs, and without JavaScript. An image may have
// loaded, or failed, before React attaches: its events are gone by then, and
// the image itself says how it ended.

/**
 * Follow the load of an image: the `ref` of the `img` element.
 *
 * `data-status` is `loaded` or `error`, on the image and on the element
 * before it. Nothing is rendered again.
 *
 * @param {HTMLImageElement | null} image The image, or null when it leaves.
 * @returns {(() => void) | undefined} What stops following it.
 */
export function watchImage(image) {
  if (!image) return undefined;
  const settle = () => {
    const status = image.naturalWidth > 0 ? "loaded" : "error";
    image.dataset.status = status;
    const standIn = image.previousElementSibling;
    if (standIn instanceof HTMLElement) standIn.dataset.status = status;
  };
  // Already over, before or without an event: an image the browser had
  // loaded or given up on before hydration, or one without an address.
  if (image.complete) settle();
  image.addEventListener("load", settle);
  image.addEventListener("error", settle);
  return () => {
    image.removeEventListener("load", settle);
    image.removeEventListener("error", settle);
  };
}

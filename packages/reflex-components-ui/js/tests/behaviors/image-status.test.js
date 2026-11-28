// What an avatar follows the load of its image with: the image and what
// stands in for it are both in the page, and each is told how the load ended.
import { afterEach, beforeEach, expect, test, vi } from "vitest";

import { watchImage } from "$/reflex-ui/behaviors/image-status.js";

// jsdom loads no image: a test says how the load of each address stands.
/** @type {Record<string, { complete: boolean, naturalWidth: number }>} */
let images;

/** @type {HTMLElement} */
let standIn;
/** @type {HTMLImageElement} */
let image;

/**
 * Put an avatar in the page: a stand-in, then its image.
 *
 * @param {string} src The address of the image.
 */
function render(src) {
  document.body.innerHTML = `<span><span>AB</span><img src="${src}"></span>`;
  standIn = /** @type {HTMLElement} */ (document.querySelector("span > span"));
  image = /** @type {HTMLImageElement} */ (document.querySelector("img"));
}

/**
 * Read what the image and its stand-in were told.
 *
 * @returns {(string | undefined)[]} The status of the stand-in, then of the image.
 */
function statuses() {
  return [standIn.dataset.status, image.dataset.status];
}

beforeEach(() => {
  images = {
    "/loading.png": { complete: false, naturalWidth: 0 },
    "/loaded.png": { complete: true, naturalWidth: 32 },
    "/broken.png": { complete: true, naturalWidth: 0 },
  };
  for (const property of /** @type {const} */ (["complete", "naturalWidth"])) {
    vi.spyOn(HTMLImageElement.prototype, property, "get").mockImplementation(
      /** @this {HTMLImageElement} */
      function () {
        return images[this.getAttribute("src") ?? ""]?.[property];
      },
    );
  }
});

afterEach(() => {
  vi.restoreAllMocks();
  document.body.innerHTML = "";
});

test("an image that loaded before it was followed is loaded at once", () => {
  render("/loaded.png");
  watchImage(image);
  expect(statuses()).toEqual(["loaded", "loaded"]);
});

test("an image that failed before it was followed is an error at once", () => {
  render("/broken.png");
  watchImage(image);
  expect(statuses()).toEqual(["error", "error"]);
});

test("an image that is loading says nothing until its event", () => {
  render("/loading.png");
  watchImage(image);
  expect(statuses()).toEqual([undefined, undefined]);
  images["/loading.png"] = { complete: true, naturalWidth: 32 };
  image.dispatchEvent(new Event("load"));
  expect(statuses()).toEqual(["loaded", "loaded"]);
});

test("an image that fails while it is followed is an error", () => {
  render("/loading.png");
  watchImage(image);
  image.dispatchEvent(new Event("error"));
  expect(statuses()).toEqual(["error", "error"]);
});

test("a new address is followed on the same image", () => {
  render("/broken.png");
  watchImage(image);
  image.setAttribute("src", "/loaded.png");
  image.dispatchEvent(new Event("load"));
  expect(statuses()).toEqual(["loaded", "loaded"]);
});

test("an image that left is no longer followed", () => {
  render("/loading.png");
  const stop = watchImage(image);
  expect(typeof stop).toBe("function");
  stop?.();
  image.dispatchEvent(new Event("error"));
  expect(statuses()).toEqual([undefined, undefined]);
  expect(watchImage(null)).toBeUndefined();
});

test("an image alone is told, with nothing before it", () => {
  document.body.innerHTML = `<img src="/broken.png">`;
  image = /** @type {HTMLImageElement} */ (document.querySelector("img"));
  watchImage(image);
  expect(image.dataset.status).toBe("error");
});

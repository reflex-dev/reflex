// What the two pages of the sweep share: the theme a page is asked to show,
// and reading it back.

import { digest, mount, read } from "./probe.js";

/**
 * The props of a Radix `Theme`, by their Radix names.
 *
 * @typedef {object} ThemeProps
 * @property {string} [accentColor]
 * @property {string} [grayColor]
 * @property {string} [radius]
 * @property {string} [scaling]
 * @property {string} [panelBackground]
 * @property {boolean} [hasBackground]
 * @property {"light" | "dark"} [appearance] On a nested theme only: the page's
 *   own appearance is the class of `html`.
 */

/**
 * A page to show.
 *
 * @typedef {object} Config
 * @property {"light" | "dark"} appearance The class of `html`.
 * @property {Required<Omit<ThemeProps, "appearance">>} theme The root theme.
 * @property {ThemeProps} [nested] A theme inside it, around what is read.
 * @property {boolean} [popover] Read from an open popover, which the browser
 *   renders in the top layer.
 */

/**
 * The functions the test drives a page with.
 *
 * @typedef {object} Harness
 * @property {(names: string[]) => void} setup Says which custom properties to
 *   read.
 * @property {(config: Config) => string[]} show Shows a page and reads it.
 * @property {(configs: Config[]) => Promise<ReturnType<typeof digest>[]>} sweep
 *   Shows each page and digests what it reads.
 */

// React counts the renders it is asked for without a task ending between them,
// and stops at fifty.
const channel = new MessageChannel();

/**
 * Let the current task end.
 *
 * @returns {Promise<void>} Resolved in a task of its own.
 */
function nextTask() {
  return new Promise((resolve) => {
    channel.port1.onmessage = () => resolve();
    channel.port2.postMessage(null);
  });
}

/**
 * Give the page its harness.
 *
 * @param {(config: Config) => Element} render Shows the themes of a
 *   configuration and returns the innermost theme element.
 */
export function install(render) {
  const container = document.createElement("div");
  /** @type {ReturnType<typeof mount>} */
  let probes = [];
  /** @type {Harness["show"]} */
  const show = (config) => {
    if (container.matches(":popover-open")) container.hidePopover();
    container.toggleAttribute("popover", config.popover === true);
    document.documentElement.className = config.appearance;
    const theme = render(config);
    theme.append(container);
    if (config.popover) container.showPopover();
    return read(probes, theme);
  };
  /** @type {Harness} */
  const harness = {
    setup: (names) => {
      container.replaceChildren();
      probes = mount(container, names);
    },
    show,
    sweep: async (configs) => {
      const digests = [];
      for (const config of configs) {
        digests.push(digest(show(config)));
        await nextTask();
      }
      return digests;
    },
  };
  Object.assign(window, { harness });
}

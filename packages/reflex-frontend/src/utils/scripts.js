import {
  createElement,
  Fragment,
  isValidElement,
  startTransition,
  useContext,
  useEffect,
  useState,
} from "react";
import {
  Scripts as RouterScripts,
  UNSAFE_FrameworkContext as FrameworkContext,
} from "react-router";

/**
 * How long a prerendered page waits for its first paint before it starts its
 * scripts anyway, so a page that paints nothing still becomes interactive.
 * Exported for the tests.
 */
export const FIRST_PAINT_TIMEOUT_MS = 1000;

/**
 * Source of the inline script a prerendered page starts its modules from.
 *
 * It is a string, not a function, because it runs in the page before any
 * module has loaded: the prerender writes it into the HTML as it stands here.
 * It is called with the hrefs to preload, the source of the module script
 * react-router renders and the fallback timeout. The modules start on the
 * first of: a paint, a user input, the page being hidden (a background tab
 * does not paint), the timeout, or right away where paint timing is missing.
 * Until this module takes over, the script also records the last click on the
 * page, which nothing can handle yet, in `window.__reflex_early`.
 * Exported for the tests.
 */
export const START_AFTER_FIRST_PAINT = `function(preloads,source,timeout){
var nonce=document.currentScript.nonce,started=false,observer,timer;
var early=window.__reflex_early={click:null,record:function(event){early.click=event}};
document.addEventListener("click",early.record,true);
function start(){
if(started)return;
started=true;
clearTimeout(timer);
if(observer)observer.disconnect();
preloads.forEach(function(href){
var link=document.createElement("link");
link.rel="modulepreload";
link.href=href;
document.head.appendChild(link);
});
var script=document.createElement("script");
script.type="module";
if(nonce)script.nonce=nonce;
script.textContent=source;
document.head.appendChild(script);
}
var types=typeof PerformanceObserver==="function"&&PerformanceObserver.supportedEntryTypes;
if(document.visibilityState==="hidden"||!types||types.indexOf("paint")<0)return start();
["visibilitychange","pointerdown","keydown"].forEach(function(type){
document.addEventListener(type,start,{capture:true,once:true});
});
timer=setTimeout(start,timeout);
observer=new PerformanceObserver(start);
observer.observe({type:"paint",buffered:true});
}`;

/**
 * How long the click of a page that is being hydrated is held back for at
 * most. Hydration settles in milliseconds; the limit is for a page whose
 * hydration never completes, which must not swallow clicks for good.
 * Exported for the tests.
 */
export const HOLD_CLICK_TIMEOUT_MS = 10000;

/**
 * Where a click acts without javascript, or is not safe to dispatch a second
 * time: a link is being followed, a form is submitted or reset, a form
 * control or a `<details>` has changed state. Such a click is left to the
 * browser. A button submits or resets its form unless its type says it is
 * only a button: that one does nothing until a handler is attached.
 */
const ACTS_WITHOUT_SCRIPTS =
  "a[href],area[href],input,select,textarea,label,summary,[contenteditable]," +
  'form button:not([type="button" i]),button[form]:not([type="button" i])';

let earlyClick = null;
let holdTimer;

/**
 * Hold back a click on a page that is being hydrated.
 *
 * React would hydrate at once and run the handler, before any mount effect
 * of the page: a provider that sets itself up in one then overwrites what the
 * handler did. The click is kept from React and dispatched again with the one
 * recorded before, once the page has settled.
 * @param {MouseEvent} event The click, in the capture phase at the window.
 */
const holdClick = (event) => {
  earlyClick = null;
  if (
    event.target instanceof Element &&
    !event.target.closest(ACTS_WITHOUT_SCRIPTS)
  ) {
    earlyClick = event;
    event.stopImmediatePropagation();
  }
};

const stopHolding = () => {
  window.removeEventListener("click", holdClick, true);
  clearTimeout(holdTimer);
};

/**
 * Take over the clicks of a prerendered page that is about to be hydrated.
 *
 * Called right before `hydrateRoot`. The inline script stops recording, and
 * its last click is kept. Until the page has settled, later clicks are held
 * back here, so React never sees a click that is dispatched again afterwards.
 */
export const takeEarlyClick = () => {
  const early = window.__reflex_early;
  if (!early) return;
  document.removeEventListener("click", early.record, true);
  earlyClick = early.click;
  window.__reflex_early = undefined;
  window.addEventListener("click", holdClick, true);
  holdTimer = setTimeout(() => {
    earlyClick = null;
    stopHolding();
  }, HOLD_CLICK_TIMEOUT_MS);
};

/**
 * Dispatch again the last click a prerendered page got before it could
 * handle one properly, and let clicks through from here on.
 *
 * Without this a click before hydration is lost: the page is visible, and no
 * handler is attached yet. Only the last click counts, and only where the
 * browser did nothing with it. An entry point that never took the clicks
 * over gets none dispatched: there is no telling whether React handled it.
 */
const replayEarlyClick = () => {
  stopHolding();
  const click = earlyClick;
  earlyClick = null;
  const target = click?.target;
  if (
    target instanceof Element &&
    target.isConnected &&
    !target.closest(ACTS_WITHOUT_SCRIPTS)
  ) {
    target.dispatchEvent(new MouseEvent("click", click));
  }
};

/**
 * Serialize a value as a javascript literal that is safe in an inline script.
 * @param {unknown} value The value to serialize.
 * @returns {string} The literal, with no `<` to end the script early.
 */
const scriptLiteral = (value) => JSON.stringify(value).replace(/</g, "\\u003c");

/**
 * List the elements react-router's scripts render, in document order.
 * @param {import("react").ReactNode} node What `<Scripts>` returned.
 * @returns {import("react").ReactElement<any>[]} The elements, fragments and arrays flattened.
 */
const flatten = (node) => {
  if (Array.isArray(node)) return node.flatMap(flatten);
  if (!isValidElement(node)) return [];
  if (node.type === Fragment) {
    return flatten(/** @type {any} */ (node.props).children);
  }
  return [node];
};

// The router's component calls hooks, so it is called as one.
const useRouterScripts = RouterScripts;

/**
 * The scripts of the document: react-router's `<Scripts>`, started after the
 * first paint on a prerendered page.
 *
 * A prerendered page is visible without javascript, so its module preloads
 * only compete with the stylesheet it needs to paint. There they are left out
 * of the document, and the module script is replaced by an inline one that
 * adds both back once the page has painted. A page rendered in the browser
 * (dev mode, the SPA fallback) has nothing to paint before its scripts run,
 * and gets what react-router renders.
 *
 * A click that comes while a prerendered page cannot handle one yet, before
 * or during hydration, is dispatched again once the page has settled.
 * @param {import("react-router").ScriptsProps} props Props for the script tags.
 * @returns {import("react").ReactNode} The script and link tags.
 */
export function Scripts(props) {
  const rendered = useRouterScripts(props);
  // Effects run child first, and this component is a leaf: on mount, no
  // provider above it has run its own yet, and none of the updates those
  // schedule has been applied. A transition is rendered only once every
  // update of a higher priority has been, which covers the updates of mount
  // effects and of the effects those renders trigger in turn. So the click is
  // dispatched from the effect of a transition started on mount.
  const [settled, setSettled] = useState(false);
  useEffect(() => startTransition(() => setSettled(true)), []);
  useEffect(() => {
    if (settled) replayEarlyClick();
  }, [settled]);
  const isSpaMode = useContext(FrameworkContext)?.isSpaMode;
  if (isSpaMode !== false || !rendered) return rendered;
  const elements = flatten(rendered);
  const module = elements.find(({ type, props: { type: scriptType } }) => {
    return type === "script" && scriptType === "module";
  });
  if (!module) return rendered;
  const preloads = [];
  const tags = [];
  for (const element of elements) {
    const { rel, href, nonce, dangerouslySetInnerHTML } = element.props;
    if (element.type === "link" && rel === "modulepreload") {
      preloads.push(href);
    } else if (element === module) {
      tags.push(
        createElement("script", {
          nonce,
          suppressHydrationWarning: true,
          dangerouslySetInnerHTML: {
            __html: `(${START_AFTER_FIRST_PAINT})(${scriptLiteral(preloads)},${scriptLiteral(dangerouslySetInnerHTML.__html)},${FIRST_PAINT_TIMEOUT_MS})`,
          },
        }),
      );
    } else {
      tags.push(element);
    }
  }
  return createElement(Fragment, null, ...tags);
}

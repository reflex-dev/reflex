import {
  createElement,
  Fragment,
  isValidElement,
  useContext,
  useEffect,
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
 * Elements a click already acted on without javascript, or that are not safe
 * to click a second time: a link is being followed, a form control or a
 * `<details>` has changed state.
 */
const ACTS_WITHOUT_SCRIPTS =
  "a[href],area[href],input,select,textarea,label,summary,[contenteditable]";

let earlyClick = null;

/**
 * Stop the inline script recording clicks, and keep the last one it saw.
 *
 * Called right before the page is hydrated. From then on React handles a
 * click itself, hydrating first if it has to, so a click recorded any later
 * would run its handler twice.
 */
export const takeEarlyClick = () => {
  const early = window.__reflex_early;
  if (!early) return;
  document.removeEventListener("click", early.record, true);
  earlyClick = early.click;
  window.__reflex_early = undefined;
};

/**
 * Dispatch again the click a prerendered page got before it was hydrated.
 *
 * Without this the click is lost: the page is visible, and no handler is
 * attached yet. Only the last click counts, and only where the browser did
 * nothing with the first one. An entry point that never took the click over
 * gets none dispatched: there is no telling whether React handled it.
 */
const replayEarlyClick = () => {
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
 * A click that comes while a prerendered page cannot handle one yet is
 * dispatched again once it is hydrated.
 * @param {import("react-router").ScriptsProps} props Props for the script tags.
 * @returns {import("react").ReactNode} The script and link tags.
 */
export function Scripts(props) {
  const rendered = useRouterScripts(props);
  useEffect(replayEarlyClick, []);
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

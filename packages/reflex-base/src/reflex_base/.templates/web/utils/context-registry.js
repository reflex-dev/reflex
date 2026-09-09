// React context objects shared by the generated context module and by every
// component that reads state. A provider and its consumers only connect when
// they hold the same context object, so the objects live here rather than in
// a module the compiler rewrites: Vite re-executes a rewritten module on hot
// update, and every module it imports along with it, but this module imports
// nothing that can change and is never re-executed.
import { createContext } from "react";

export const ColorModeContext = createContext({
  colorMode: "system",
  resolvedColorMode: "light",
  toggleColorMode: () => {},
  setColorMode: () => {},
});
export const UploadFilesContext = createContext(null);
export const DispatchContext = createContext(null);
export const EventLoopContext = createContext(null);

ColorModeContext.displayName = "ColorModeContext";
UploadFilesContext.displayName = "UploadFilesContext";
DispatchContext.displayName = "DispatchContext";
EventLoopContext.displayName = "EventLoopContext";

const stateContexts = new Map();

/**
 * Return the context object carrying the named Python state.
 *
 * The first call for a name creates the context; later calls, including ones
 * made from a re-executed generated module, return the same object.
 *
 * @param {string} name - The dotted Python state name.
 * @returns {React.Context} The state's context object.
 */
export function getStateContext(name) {
  let context = stateContexts.get(name);
  if (context === undefined) {
    context = createContext(null);
    context.displayName = `StateContext(${name})`;
    stateContexts.set(name, context);
  }
  return context;
}

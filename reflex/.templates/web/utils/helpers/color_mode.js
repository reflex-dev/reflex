import {lastCompiledTimeStamp} from "/utils/context.js";

export function clearColorModeLocalStorageOnStartup () {
    if (typeof window !== "undefined") {
        const lastCompiledTimeInLocalStorage = localStorage.getItem("last_compiled_time")
        if (lastCompiledTimeInLocalStorage && lastCompiledTimeInLocalStorage == lastCompiledTimeStamp) {
            return
        }
        localStorage.removeItem('chakra-ui-color-mode');
        localStorage.setItem("last_compiled_time", lastCompiledTimeStamp)
      }
};

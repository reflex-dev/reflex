import reflex from "/reflex.json";


export function clearColorModeLocalStorageOnStartup () {
    if (typeof window !== "undefined") {
        const colorModeHash = localStorage.getItem("color_mode_hash") 
        if (colorModeHash && colorModeHash == reflex.color_mode_hash) {
            return 
        }
        localStorage.removeItem('chakra-ui-color-mode');
        localStorage.setItem("color_mode_hash", reflex.color_mode_hash)
      }
};

import { useState } from "react";
import { ChakraProvider, extendTheme } from "@chakra-ui/react";
import { Global, css } from "@emotion/react";
import theme, { radix_theme } from "/utils/theme";
import { clientStorage, initialEvents, initialState, isDevMode, ColorModeContext, StateContext, EventLoopContext } from "/utils/context.js";
import { useEventLoop } from "utils/state";

import { Theme, ThemePanel } from '@radix-ui/themes';
import '@radix-ui/themes/styles.css';

import '/styles/styles.css'

const GlobalStyles = css`
  /* Hide the blue border around Chakra components. */
  .js-focus-visible :focus:not([data-focus-visible-added]) {
    outline: none;
    box-shadow: none;
  }
`;

function EventLoopProvider({ children }) {
  const [state, addEvents, connectError] = useEventLoop(
    initialState,
    initialEvents,
    clientStorage,
  )
  return (
    <EventLoopContext.Provider value={[addEvents, connectError]}>
      <StateContext.Provider value={state}>
        {children}
      </StateContext.Provider>
    </EventLoopContext.Provider>
  )
}

function MyApp({ Component, pageProps }) {
  const [colorMode, setColorMode] = useState("light")
  const toggleColorMode = () => {
    setColorMode((prevMode) => (prevMode === "light" ? "dark" : "light"))
  }
  return (
    <ChakraProvider theme={extendTheme(theme)}>
      <Global styles={GlobalStyles} />
      <ColorModeContext.Provider value={[colorMode, toggleColorMode]}>
        <Theme {...radix_theme} appearance={colorMode}>
          <EventLoopProvider>
            <Component {...pageProps} />
          </EventLoopProvider>
          {isDevMode ? <ThemePanel defaultOpen={false} /> : null}
        </Theme>
      </ColorModeContext.Provider>
    </ChakraProvider>
  );
}

export default MyApp;

import { ChakraProvider, extendTheme } from "@chakra-ui/react";
import { Global, css } from "@emotion/react";
import theme from "/utils/theme";
import { clientStorage, initialEvents, initialState, StateContext, EventLoopContext } from "/utils/context.js";
import { useEventLoop } from "/utils/state";

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
  return (
    <ChakraProvider theme={extendTheme(theme)}>
      <Global styles={GlobalStyles} />
      <EventLoopProvider>
        <Component {...pageProps} />
      </EventLoopProvider>
    </ChakraProvider>
  );
}

export default MyApp;

import { ChakraProvider, extendTheme } from "@chakra-ui/react";
import { Global, css } from "@emotion/react";
import theme from "/utils/theme";
import { initialEvents, initialState, StateContext, EventLoopContext } from "/utils/context.js";
import { useEventLoop } from "utils/state";

import '../styles/tailwind.css'

const GlobalStyles = css`
  /* Hide the blue border around Chakra components. */
  .js-focus-visible :focus:not([data-focus-visible-added]) {
    outline: none;
    box-shadow: none;
  }
`;

function EventLoopProvider({ children }) {
  const [state, Event, notConnected] = useEventLoop(
    initialState,
    initialEvents,
  )
  return (
    <EventLoopContext.Provider value={[Event, notConnected]}>
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

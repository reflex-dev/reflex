import { ChakraProvider, extendTheme } from "@chakra-ui/react";
import { Global, css } from "@emotion/react";
import theme from "/utils/theme";

import '../styles/tailwind.css'

const GlobalStyles = css`
  /* Hide the blue border around Chakra components. */
  .js-focus-visible :focus:not([data-focus-visible-added]) {
    outline: none;
    box-shadow: none;
  }
`;

function MyApp({ Component, pageProps }) {
  return (
    <ChakraProvider theme={extendTheme(theme)}>
      <Global styles={GlobalStyles} />
      <Component {...pageProps} />
    </ChakraProvider>
  );
}

export default MyApp;

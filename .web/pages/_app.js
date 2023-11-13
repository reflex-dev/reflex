import { ChakraProvider, extendTheme } from "@chakra-ui/react"
import theme from "/utils/theme.js"
import { css, Global } from "@emotion/react"
import ChakraColorModeProvider from "/components/reflex/chakra_color_mode_provider.js"


import { EventLoopProvider } from "/utils/context.js";
import { ThemeProvider } from 'next-themes'


import '/styles/styles.css'

const GlobalStyles = css`
  /* Hide the blue border around Chakra components. */
  .js-focus-visible :focus:not([data-focus-visible-added]) {
    outline: none;
    box-shadow: none;
  }
`;


function AppWrap({children}) {


  return (
    <ChakraProvider theme={extendTheme(theme)}>
  <Global styles={GlobalStyles}/>
  <ChakraColorModeProvider>
  {children}
</ChakraColorModeProvider>
</ChakraProvider>
  )
}

export default function MyApp({ Component, pageProps }) {
  return (
    <ThemeProvider defaultTheme="light" storageKey="chakra-ui-color-mode" attribute="class">
      <AppWrap>
        <EventLoopProvider>
          <Component {...pageProps} />
        </EventLoopProvider>
      </AppWrap>
    </ThemeProvider>
  );
}


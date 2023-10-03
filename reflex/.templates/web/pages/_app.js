import { EventLoopProvider, ReflexColorModeProvider } from "/utils/context.js";
import AppWrap from "./_app_wrap.js"


function MyApp({ Component, pageProps }) {
  return (
    <ReflexColorModeProvider>
      <AppWrap>
        <EventLoopProvider>
          <Component {...pageProps} />
        </EventLoopProvider>
      </AppWrap>
    </ReflexColorModeProvider>
  );
}

export default MyApp;

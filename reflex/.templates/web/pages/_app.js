import { EventLoopProvider } from "/utils/context.js";
import AppWrap from "./_app_wrap.js"


function MyApp({ Component, pageProps }) {
  return (
    <AppWrap>
      <EventLoopProvider>
        <Component {...pageProps} />
      </EventLoopProvider>
    </AppWrap>
  );
}

export default MyApp;

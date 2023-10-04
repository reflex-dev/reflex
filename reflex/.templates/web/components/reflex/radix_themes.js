import { Theme, ThemePanel } from "@radix-ui/themes"
import { isDevMode } from "/utils/context.js"
import { radix_theme } from "/utils/theme.js"
import '@radix-ui/themes/styles.css';


export default function RadixThemesTheme({children}) {
    return (
        <Theme {...radix_theme}>
          {children}
          {isDevMode ? <ThemePanel defaultOpen={false} /> : null}
        </Theme>
    )
}

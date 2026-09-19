
import {Fragment,StrictMode,useEffect} from "react"
import {EventLoopProvider,StateProvider} from "$/utils/context"
import {Errorboundary_errorboundary_f3503550cc626882edc0335b9ae43737} from "$/utils/components/Errorboundary_errorboundary_f3503550cc626882edc0335b9ae43737"
import RadixThemesColorModeProvider from "$/components/reflex/radix_themes_color_mode_provider"
import {MemoizedToastProvider_18b15038} from "$/app_components/reflex/compiler/compiler"
import {Theme as RadixThemesTheme} from "@radix-ui/themes"
import theme from "$/utils/theme"
import {DefaultOverlayComponents_04c36749} from "$/app_components/reflex/app"
import {jsx} from "@emotion/react"

import { defaultColorMode } from "$/utils/context";
import { ThemeProvider } from '$/utils/react-theme';
import { Layout as AppLayout } from './_document';
import { Outlet } from 'react-router';
import * as React from "react";
import * as emotion_react from "@emotion/react";
import * as utils_context from "$/utils/context";
import * as utils_state from "$/utils/state";
import * as radix_ui_themes from "@radix-ui/themes";




function ReflexProviders({children}) {
  useEffect(() => {
    // Make contexts and state objects available globally for dynamic eval'd components
    window.__reflex = {
          "react": React,
    "@emotion/react": emotion_react,
    "$/utils/context": utils_context,
    "$/utils/state": utils_state,
    "@radix-ui/themes": radix_ui_themes,
    };
  }, []);

  return jsx(ThemeProvider, {defaultTheme: defaultColorMode, attribute: "class"},
    jsx(AppWrap, {}, children)
  );
}


function AppWrap({children}) {




return (jsx(StrictMode,{},jsx(StateProvider,{},jsx(EventLoopProvider,{},jsx(Errorboundary_errorboundary_f3503550cc626882edc0335b9ae43737,{},jsx(RadixThemesColorModeProvider,{},jsx(Fragment,{},jsx(MemoizedToastProvider_18b15038,{},),jsx(RadixThemesTheme,{accentColor:"blue",css:{...theme.styles.global[':root'], ...theme.styles.global.body}},jsx(Fragment,{},jsx(DefaultOverlayComponents_04c36749,{},),jsx(Fragment,{},children,jsx("div",{css:({ ["position"] : "fixed", ["top"] : 0 }),id:"portal"},)))))))))))
}

export function Layout({children}) {
  return jsx(AppLayout, {}, jsx(ReflexProviders, {}, children));
}

// Used by entry.client.js when mount_target is configured: skips the document
// shell (which renders react-router's <Meta>/<Scripts>/<Links> and requires a
// framework router context) but keeps the runtime providers.
export function EmbedLayout({children}) {
  return jsx(ReflexProviders, {}, children);
}

export default function App() {
  return jsx(Outlet, {});
}


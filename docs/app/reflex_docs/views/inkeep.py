"""UI and logic inkeep chat component."""

import reflex as rx
from reflex.constants import MemoizationMode
from reflex.event import EventSpec
from reflex.experimental.client_state import ClientStateVar
from reflex.utils.imports import ImportVar
from reflex.vars import Var
from reflex.vars.base import VarData


class InkeepSearchBar(rx.NoSSRComponent):
    tag = "InkeepSearchBar"
    library = "@inkeep/cxkit-react@0.5.115"


_INKEEP_LOADED_STATE = "inkeep_loaded"
_INKEEP_OPEN_STATE = "inkeep_open"
_SEARCH_WRAPPER_ID = "inkeep-search-wrapper"
_SEARCH_TRIGGER_ID = "inkeep-search-trigger"
_SEARCH_TRIGGER_FALLBACK_STYLE = (
    f"#{_SEARCH_WRAPPER_ID}:has(> [id^='inkeep-shadow']) "
    f"> #{_SEARCH_TRIGGER_ID} {{ display: none; }}"
)

# Inline copy of assets/icons/search.svg so the placeholder needs no extra request.
_SEARCH_ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none"'
    ' viewBox="0 0 16 16" aria-hidden="true"><path stroke="currentColor"'
    ' stroke-linecap="round" stroke-linejoin="round" stroke-width="1.25"'
    ' d="M11.332 11.333 13.999 14"/><path stroke="currentColor"'
    ' stroke-linecap="round" stroke-linejoin="round" stroke-width="1.25"'
    ' d="M12.667 7.333A5.333 5.333 0 1 0 2 7.333a5.333 5.333 0 0 0 10.667 0"/></svg>'
)

# Runs on mount (as a real effect, not an inert rendered <script>) to:
#   1. Fix the placeholder's keyboard hint for non-Mac platforms, which can't
#      be known during SSR (the default label is the Mac glyph).
#   2. Forward Cmd/Ctrl+K to the placeholder trigger before the widget loads,
#      mounting the real widget with its modal open. Once Inkeep's shadow host
#      mounts, this no-ops and Inkeep's own handler takes over.
_HOTKEY_AND_HINT_HOOK = f"""
useEffect(() => {{
  const triggerId = "{_SEARCH_TRIGGER_ID}";
  const wrapperId = "{_SEARCH_WRAPPER_ID}";
  const platform =
    (navigator.userAgentData && navigator.userAgentData.platform) ||
    navigator.platform ||
    navigator.userAgent ||
    "";
  if (!/mac|iphone|ipad|ipod/i.test(platform)) {{
    const hint = document.getElementById(triggerId)?.querySelector("kbd");
    if (hint) hint.textContent = "Ctrl K";
  }}
  const onKeydown = (event) => {{
    if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== "k") return;
    const trigger = document.getElementById(triggerId);
    const widgetReady = document
      .getElementById(wrapperId)
      ?.querySelector("[id^='inkeep-shadow']");
    if (!trigger || widgetReady) return;
    event.preventDefault();
    trigger.click();
  }};
  document.addEventListener("keydown", onKeydown);
  return () => document.removeEventListener("keydown", onKeydown);
}}, [])
"""


def _controlled_modal_settings(opened: ClientStateVar) -> Var:
    """Create controlled modal settings for the Inkeep search bar.

    Args:
        opened: Client state var tracking whether the modal is open.

    Returns:
        A Var containing the Inkeep props and client state dependencies.
    """
    is_open = opened.value
    on_open_change = opened.set
    return Var(
        "{...searchBarProps, modalSettings: "
        f"{{isOpen: {is_open!s}, onOpenChange: {on_open_change!s}}}}}"
    )._replace(
        merge_var_data=VarData.merge(
            is_open._get_all_var_data(),
            on_open_change._get_all_var_data(),
        )
    )


def _search_trigger_placeholder(on_click: EventSpec) -> rx.Component:
    """Lightweight stand-in for the Inkeep search bar button.

    Mirrors the widget's trigger styling so mounting the real search bar does
    not shift layout, while keeping the ~276 KB Inkeep chunk (and the Google
    Fonts stylesheet it injects) off the critical path until first use.

    Args:
        on_click: Event handler that mounts the real search widget.

    Returns:
        The placeholder button component.
    """
    return rx.el.button(
        rx.html(_SEARCH_ICON_SVG, class_name="flex shrink-0"),
        rx.el.span("Search", class_name="max-xl:hidden"),
        rx.el.kbd(
            "⌘K",
            class_name="max-xl:hidden ml-auto flex items-center justify-center px-1 h-5 rounded bg-secondary-3 text-[0.8125rem] font-[475] leading-5 font-sans",
        ),
        id=_SEARCH_TRIGGER_ID,
        type="button",
        aria_label="Search documentation",
        on_click=on_click,
        class_name=(
            "flex flex-row items-center justify-center xl:justify-start gap-2 rounded-lg "
            "h-8 min-h-8 w-8 xl:w-40 px-0 xl:px-2 "
            "bg-secondary-1 dark:bg-secondary-2 hover:bg-secondary-2 dark:hover:bg-secondary-3 "
            "text-secondary-11 text-sm font-medium leading-6 border-none cursor-pointer "
            "shadow-[0_-1px_0_0_rgba(0,0,0,0.08)_inset,0_0_0_1px_rgba(0,0,0,0.08)_inset,0_1px_2px_0_rgba(0,0,0,0.02),0_1px_4px_0_rgba(0,0,0,0.02)] "
            "dark:shadow-[0_-1px_0_0_rgba(255,255,255,0.06)_inset,0_0_0_1px_rgba(255,255,255,0.04)_inset]"
        ),
    )


class Search(rx.el.Div):
    _memoization_mode = MemoizationMode(recursive=False)

    def add_imports(self):
        """Add the imports for the component."""
        return {
            "react": {ImportVar(tag="useContext"), ImportVar(tag="useEffect")},
            "$/utils/context": {ImportVar(tag="ColorModeContext")},
        }

    def add_hooks(self):
        """Add the hooks for the component."""
        return [
            "const { resolvedColorMode } = useContext(ColorModeContext)",
            _HOTKEY_AND_HINT_HOOK,
            """
const escalationParams = {
  type: "object",
  properties: {
    explanation: {
      type: "string",
      description: "A brief few word justification of why a specific confidence level was chosen.",
    },
    answerConfidence: {
      anyOf: [
        {
          type: "string",
          const: "very_confident",
          description: `\n    The AI Assistant provided a complete and direct answer to all parts of the User Question.\n    The answer fully resolved the issue without requiring any further action from the User.\n    Every part of the answer was cited from the information sources.\n    The assistant did not ask for more information or provide options requiring User action.\n    This is the highest Answer Confidence level and should be used sparingly.\n  `,
        },
        {
          type: "string",
          const: "somewhat_confident",
          description: `\n    The AI Assistant provided a complete and direct answer to the User Question, but the answer contained minor caveats or uncertainties. \n \n    Examples:\n    • The AI Assistant asked follow-up questions to the User\n    • The AI Assistant requested additional information from the User\n    • The AI Assistant suggested uncertainty in the answer\n    • The AI Assistant answered the question but mentioned potential exceptions\n  `,
        },
        {
          type: "string",
          const: "not_confident",
          description: `\n    The AI Assistant tried to answer the User Question but did not fully resolve it.\n    The assistant provided options requiring further action from the User, asked for more information, showed uncertainty,\n    suggested the user contact support or provided contact information, or provided an indirect or incomplete answer.\n    This is the most common Answer Confidence level.\n \n    Examples:\n    • The AI Assistant provided a general answer not directly related to the User Question\n    • The AI Assistant said to reach out to support or provided an email address or contact information\n    • The AI Assistant provided options that require further action from the User to resolve the issue\n  `,
        },
        {
          type: "string",
          const: "no_sources",
          description: `\n    The AI Assistant did not use or cite any sources from the information sources to answer the User Question.\n  `,
        },
        {
          type: "string",
          const: "other",
          description: `\n    The User Question is unclear or unrelated to the subject matter.\n  `,
        },
      ],
      description: "A measure of how confidently the AI Assistant completely and directly answered the User Question.",
    },
  },
  required: ["explanation", "answerConfidence"],
  additionalProperties: false,
};
const searchBarProps = {
  baseSettings: {
    apiKey: '5805add2b45961017ac79c9d388aa34f5db49eb652e228e0',
    customIcons: {search: {custom: "/docs/icons/search.svg"}},
    organizationDisplayName: 'Reflex',
    primaryBrandColor: '#6E56CF',
    transformSource: (source) => {
      const urlPatterns = {
        blog: 'reflex.dev/blog',
        library: 'reflex.dev/docs/library',
        apiRef: 'reflex.dev/docs/api-reference',
        docs: 'reflex.dev/docs',
      }

      function matchUrl(pattern) {
        return source.url.includes(pattern)
      }

      function getBreadcrumbs() {
        if (matchUrl(urlPatterns.blog)) {
          return ['Blogs', ...source.breadcrumbs.slice(1)]
        }
        if (matchUrl(urlPatterns.library)) {
          return ['Components', ...source.breadcrumbs.slice(1)]
        }
        if (matchUrl(urlPatterns.apiRef)) {
          return ['API Reference']
        }
        if (matchUrl(urlPatterns.docs)) {
          return ['Docs', ...source.breadcrumbs.slice(1)]
        }
        return source.breadcrumbs
      }

      const breadcrumbs = getBreadcrumbs()

      function getTabs() {
        const tabMap = {
          [urlPatterns.blog]: 'Blogs',
          [urlPatterns.library]: 'Components',
          [urlPatterns.apiRef]: 'API Reference',
          [urlPatterns.docs]: 'Docs',
        }

        for (const [pattern, tab] of Object.entries(tabMap)) {
          if (matchUrl(pattern)) {
            return [
              ...(source.tabs ?? []),
              // If the first breadcrumb is the same as the tab, use the remaining breadcrumbs
              // This is only if you don't want breadcrumbs to include current tab, e.g. just "Blog Post" instead of "Blogs > Blog Post" in the Blogs tab
              // The tab type accepts a string or an object with a breadcrumbs property i.e. breadcrumbs shown for this source in that tab
              [
                tab,
                { breadcrumbs: breadcrumbs[0] === tab ? breadcrumbs.slice(1) : breadcrumbs },
              ],
            ]
          }
        }
        return source.tabs
      }

      return {
        ...source,
        tabs: getTabs(),
        breadcrumbs,
      }
    },
    colorMode: {
      forcedColorMode: resolvedColorMode, // options: 'light' or dark'
    },
    theme: {
      // The site ships its own fonts; skip the widget's default Google Fonts
      // (Inter) stylesheet injection.
      disableLoadingDefaultFont: true,
      // Add inline styles using the recommended approach from the docs
      styles: [
        {
          key: "custom-theme",
          type: "style",
          value: `
            [data-theme='light'] .ikp-search-bar__button {
              color: var(--secondary-11);
              padding: 0.375rem 0.5rem;
              border-radius: 0.5rem;
              background: var(--secondary-1);
              display: flex;
              flex-direction: row;
              align-items: center;
              justify-content: flex-start;
              gap: 0.5rem;
              width: 100%;
              height: 2rem !important;
              min-height: 2rem !important;
              max-width: 10rem;
              min-width: 0;
              box-shadow:
                0 -1px 0 0 rgba(0, 0, 0, 0.08) inset,
                0 0 0 1px rgba(0, 0, 0, 0.08) inset,
                0 1px 2px 0 rgba(0, 0, 0, 0.02),
                0 1px 4px 0 rgba(0, 0, 0, 0.02);
              font-size: 0.875rem;
              font-family: "Instrument Sans", sans-serif;
              font-weight: 500;
              font-style: normal;
              line-height: 1.5rem;
              border: none;
              transition: none;
            }
            [data-theme='dark'] .ikp-search-bar__button {
              color: var(--secondary-11);
              transition: none;
              height: 2rem !important;
              min-height: 2rem !important;
              padding: 0.375rem 0.5rem;
              border-radius: 0.5rem;
              background: var(--secondary-2);
              display: flex;
              max-width: 10rem;
              flex-direction: row;
              align-items: center;
              justify-content: flex-start;
              gap: 0.5rem;
              width: 100%;
              max-width: none;
              min-width: 0;
              box-shadow:
                0 -1px 0 0 rgba(255, 255, 255, 0.06) inset,
                0 0 0 1px rgba(255, 255, 255, 0.04) inset;
              font-size: 0.875rem;
              font-family: "Instrument Sans", sans-serif;
              font-weight: 500;
              font-style: normal;
              line-height: 1.5rem;
              border: none;
            }
            [data-theme='light'] .ikp-search-bar__button:hover {
              background: var(--secondary-2);
            }
            [data-theme='dark'] .ikp-search-bar__button:hover {
              background: var(--secondary-3);
            }
            @media (min-width: 1024px) {
              .ikp-search-bar__button {
                width: 10rem;
              }
            }

            [data-theme='light'] .ikp-search-bar__container,
            [data-theme='dark'] .ikp-search-bar__container {
              display: flex;
              justify-content: center;
              align-items: center;
              min-height: 2rem;
              max-height: 2rem;
              width: 10rem;
              max-width: 10rem;
            }

            [data-theme='light'] .ikp-search-bar__button:hover {
              background-color: var(--secondary-2);
            }
            [data-theme='dark'] .ikp-search-bar__button:hover {
              background-color: var(--secondary-3);
            }

            [data-theme='dark'] .ikp-modal__overlay {
              background: rgba(18, 17, 19, 0.50);
              backdrop-filter: blur(20px);
            }

            [data-part="modal__content"] {
              font-family: "Instrument Sans", sans-serif;
            }

            @media (max-width: 80em) {
              [data-theme='light'] .ikp-search-bar__container,
              [data-theme='dark'] .ikp-search-bar__container {
                width: auto !important;
              }

              [data-theme='light'] .ikp-search-bar__button,
              [data-theme='dark'] .ikp-search-bar__button {
                padding: 2px 12px;
                display: block;
                height: 32px;
                min-height: 32px;
                width: 32px;
                max-width: 6em;
                min-width: 0px;
              }

              .ikp-search-bar__button {
                align-items: center;
                justify-content: center;
              }

              .ikp-search-bar__kbd-wrapper,
              .ikp-search-bar__text {
                display: none;
              }

              .ikp-search-bar__icon {
                padding: 0;
                margin-right: 2px;
              }

              .ikp-search-bar__content-wrapper {
                justify-content: center;
              }
            }

            .ikp-search-bar__icon {
              display: flex;
            }

            .ikp-search-bar__icon svg {
              width: auto;
            }

            [data-theme='light'] .ikp-search-bar__kbd-wrapper,
            [data-theme='dark'] .ikp-search-bar__kbd-wrapper {
              padding: 0px 0.25rem;
              justify-content: center;
              align-items: center;
              border-radius: 0.25rem;
              box-shadow: none;
              color: var(--secondary-11);
              font-family: "Instrument Sans";
              --ikp-colors-transparent: var(--secondary-3, #fcfcfd);
              background: var(--secondary-3, #f0f0f3) !important;
              font-size: 0.8125rem;
              font-weight: 475;
              line-height: 1.25rem;
              height: 1.25rem;
              font-style: normal;
              margin-left: auto;
              width: fit-content;
            }

            [data-theme='light'] .ikp-search-bar__text,
            [data-theme='dark'] .ikp-search-bar__text,
            [data-theme='light'] .ikp-search-bar__icon,
            [data-theme='dark'] .ikp-search-bar__icon {
              color: var(--secondary-11);
              font-weight: 500;
              font-style: normal;
              line-height: 1.5rem;
              font-size: 0.875rem;
            }
          `,
        },
      ],
    }
  },
  searchSettings: { // optional InkeepSearchSettings
    tabs: ['All', 'Docs', 'Components', 'API Reference', 'Blogs', 'GitHub', 'Forums'].map((t) => [
      t,
      { isAlwaysVisible: true },
    ]),
    placeholder: 'Search',
  },
  aiChatSettings: { // optional typeof InkeepAIChatSettings
    aiAssistantAvatar: 'https://web.reflex-assets.dev/logos/small_logo.svg',
    chatSubjectName: 'Reflex',
    exampleQuestions: [
      'How does Reflex work?',
      'What types of apps can I build with Reflex?',
      'Where can I deploy my apps?',
    ],
    getHelpOptions: [
      {
        action: {
          type: "open_link",
          url: "https://reflex.dev/pricing"
        },
        icon: {
          builtIn: "LuCalendar"
        },
        name: "Get a custom demo"
      },
      {
        action: {
          type: "open_link",
          url: "https://github.com/reflex-dev/reflex/issues/new?assignees=&labels=&projects=&template=bug_report.md&title="
        },
        icon: {
          builtIn: "FaGithub"
        },
        name: "File an issue on Reflex's GitHub."
      },
      {
        action: {
          type: "open_link",
          url: "https://discord.gg/T5WSbC2YtQ"
        },
        icon: {
          builtIn: "FaDiscord"
        },
        name: "Ask on Reflex's Discord."
      }
    ],
    getTools: () => [
      {
        type: "function",
        function: {
          name: "provideAnswerConfidence",
          description: "Determine how confident the AI assistant was and whether or not to escalate to humans.",
          parameters: escalationParams,
        },
        renderMessageButtons: ({ args }) => {
          const confidence = args.answerConfidence;
          if (["not_confident", "no_sources", "other"].includes(confidence)) {
            return [
              {
                label: "Contact Support",
                action: {
                  'type': 'open_form',
                },
              }
            ];
          }
          return [];
        },
      },
    ],

  },
};""",
        ]

    @classmethod
    def create(cls):
        """Create the search component.

        The Inkeep widget is not mounted until the user interacts with the
        search trigger, keeping its large bundle out of the initial page load.
        The modal is controlled and starts open, so the interaction that
        mounts the widget also opens search.
        """
        loaded = ClientStateVar.create(
            _INKEEP_LOADED_STATE, default=False, global_ref=False
        )
        opened = ClientStateVar.create(
            _INKEEP_OPEN_STATE, default=True, global_ref=False
        )
        return super().create(
            rx.el.style(_SEARCH_TRIGGER_FALLBACK_STYLE),
            rx.cond(
                loaded.value,
                InkeepSearchBar.create(
                    special_props=[_controlled_modal_settings(opened)],
                ),
                rx.fragment(),
            ),
            _search_trigger_placeholder(
                on_click=rx.call_function(loaded.set_value(True)),
            ),
            id=_SEARCH_WRAPPER_ID,
        )


inkeep = Search.create

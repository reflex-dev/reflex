"""UI and logic inkeep chat component."""

from reflex_base.config import get_config

import reflex as rx
from reflex.utils.imports import ImportVar


class InkeepSearchBar(rx.NoSSRComponent):
    """Client-only Inkeep search-bar component."""

    tag = "InkeepSearchBar"
    library = "@inkeep/cxkit-react@0.5.115"


class Search(rx.el.Div):
    """Configure the shared Reflex documentation search experience."""

    def add_imports(self):
        """Add imports required by the search wrapper.

        Returns:
            Component import declarations.
        """
        return {
            "react": {ImportVar(tag="useContext")},
            "$/utils/context": {ImportVar(tag="ColorModeContext")},
        }

    def add_hooks(self):
        """Configure Inkeep and synchronize its color mode.

        Returns:
            Client hook source strings.
        """
        hooks = [
            "const { resolvedColorMode } = useContext(ColorModeContext)",
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
    customIcons: {search: {custom: __REFLEX_SEARCH_ICON__}},
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
              font-family: var(--font-instrument-sans);
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
              font-family: var(--font-instrument-sans);
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
              font-family: var(--font-instrument-sans);
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

            .ikp-search-bar__kbd-wrapper {
              padding: 0px 0.25rem;
              justify-content: center;
              align-items: center;
              border-radius: 0.25rem;
              box-shadow: none;
              color: var(--secondary-11);
              font-family: var(--font-instrument-sans);
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

            .ikp-search-bar__text,
            .ikp-search-bar__icon {
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
        frontend_path = (get_config().frontend_path or "").rstrip("/")
        search_icon = f"{frontend_path or ''}/icons/search.svg"
        hooks[1] = hooks[1].replace(
            "__REFLEX_SEARCH_ICON__",
            f'"{search_icon}"',
        )
        return hooks

    @classmethod
    def create(cls):
        """Create the search component.

        Returns:
            Configured Inkeep search wrapper.
        """
        return super().create(
            InkeepSearchBar.create(
                special_props=[rx.Var("{...searchBarProps}")],
            )
        )


inkeep = Search.create

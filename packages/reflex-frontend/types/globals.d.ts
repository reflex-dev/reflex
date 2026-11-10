/**
 * Everything the frontend reads that no module in `src` defines: values other
 * code puts on `window`, the per-app settings file, and what the bundler adds.
 *
 * These are contracts with code outside this package. A name that is not
 * declared here fails `npm run typecheck`, so a new one has to be written down.
 */

/** The settings `reflex` compiles into each app's `.web/env.json`. */
declare module "$/env.json" {
  const env: {
    PING: string;
    EVENT: string;
    UPLOAD: string;
    AUTH_CODESPACE: string;
    HEALTH: string;
    ALL_ROUTES: string;
    TRANSPORT: "websocket" | "polling";
    TEST_MODE: boolean;
    REFLEX_VERSION: string;
    /** Set by the embed plugin: the selector of the element to mount in. */
    MOUNT_TARGET?: string;
  };
  export default env;
}

/** Installed by the code component, which loads it on demand. */
declare module "shiki";

/** Hooks the reflex-otel plugin installs to trace events, uploads and the socket. */
interface ReflexOtelHooks {
  onEventSend?: (event: object) => void;
  onUploadSend?: (handler: string, headers: Record<string, string>) => void;
  onSocketConnect?: () => void;
  onSocketDisconnect?: (reason: string) => void;
}

interface Window {
  /** The libraries bundled for dynamic components, by specifier. */
  __reflex?: Record<string, any>;
  /** Loads bundled libraries a dynamic component names, before it is evaluated. */
  __reflex_load?: (libraries: string[]) => Promise<void>;
  __reflex_otel?: ReflexOtelHooks;
  /** Dynamic components are evaluated outside any module and expect a global React. */
  React?: any;
}

interface ImportMeta {
  /** Vite's hot module replacement API; absent from a production build. */
  hot?: { dispose(callback: () => void): void };
}

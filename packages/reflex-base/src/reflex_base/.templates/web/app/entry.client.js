import { startTransition } from "react";
import { hydrateRoot } from "react-dom/client";
import { HydratedRouter } from "react-router/dom";
import { createElement } from "react";

startTransition(() => {
  hydrateRoot(document, createElement(HydratedRouter));
});

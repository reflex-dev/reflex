import { startTransition } from "react";
import { hydrateRoot } from "react-dom/client";
import { HydratedRouter } from "react-router/dom";
import { createElement } from "react";
import { takeEarlyClick } from "$/utils/scripts";

takeEarlyClick();
startTransition(() => {
  hydrateRoot(document, createElement(HydratedRouter));
});

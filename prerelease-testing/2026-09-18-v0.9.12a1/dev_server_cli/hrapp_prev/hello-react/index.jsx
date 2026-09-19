import React from "react";

export function Hello({ label, children, ...rest }) {
  return React.createElement(
    "div",
    { "data-hello": "1", ...rest },
    React.createElement("span", { id: "hello-label" }, "HELLO:" + (label ?? "none")),
    React.createElement("span", { id: "hello-children" }, children)
  );
}
export default Hello;

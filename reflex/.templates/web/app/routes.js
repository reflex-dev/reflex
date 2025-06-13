import { route } from "@react-router/dev/routes";
import { flatRoutes } from "@react-router/fs-routes";

export default [
  route("*", "routes/[404]_._index.js"),
  route("404", "routes/[404]_._index.js", { id: "404" }),
  ...(await flatRoutes({
    ignoredRouteFiles: ["routes/\\[404\\]_._index.js"],
  })),
];

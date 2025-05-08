import { route } from "@react-router/dev/routes";
import { flatRoutes } from "@react-router/fs-routes";

export default [
  route("*", "routes/[404]_._index.js"),
  ...(await flatRoutes({
    ignoredRouteFiles: ["routes/\\[404\\]_._index.js"],
  })),
];

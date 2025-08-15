import { route } from "@react-router/dev/routes";
import { flatRoutes } from "@react-router/fs-routes";

export default [
  ...(await flatRoutes({
    ignoredRouteFiles: ["routes/\\[404\\]._index.jsx"],
  })),
  route("*", "routes/[404]._index.jsx"),
];

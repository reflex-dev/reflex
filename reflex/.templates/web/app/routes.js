import { route } from "@react-router/dev/routes";
import { flatRoutes } from "@react-router/fs-routes";

export default [
  route("404", "routes/[404]._index.jsx", { id: "404" }),
  ...(await flatRoutes({
    ignoredRouteFiles: ["routes/\\[404\\]._index.jsx"],
  })),
  route("*", "routes/[404]._index.jsx"),
];

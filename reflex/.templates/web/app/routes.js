import { flatRoutes } from "@react-router/fs-routes";

export default [...(await flatRoutes())];

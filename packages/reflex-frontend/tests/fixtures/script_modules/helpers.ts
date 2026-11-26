import dayjs from "dayjs";
import { format } from "./lib/format.js";

export const describe = (text: string) => dayjs(text).format(format);
export const helper = () => 1;

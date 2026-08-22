import { describe, expect, test } from "vitest";

import {
  configureReflexRuntime,
  getEnv,
  runtimeConfig,
} from "@reflex-dev/reflex-base/runtime";

describe("runtime registry", () => {
  test("getEnv throws a descriptive error before configuration", () => {
    expect(() => getEnv()).toThrow(/Reflex runtime is not configured/);
  });

  test("configureReflexRuntime applies only defined keys", () => {
    configureReflexRuntime({
      env: { EVENT: "http://localhost:8000/_event" },
      state_name: "state",
      unknown_key: "ignored",
    });
    expect(getEnv()).toEqual({ EVENT: "http://localhost:8000/_event" });
    expect(runtimeConfig.state_name).toBe("state");
    expect(runtimeConfig).not.toHaveProperty("unknown_key");
    // Undefined values do not clobber existing configuration.
    configureReflexRuntime({ env: undefined, state_name: "other" });
    expect(getEnv()).toEqual({ EVENT: "http://localhost:8000/_event" });
    expect(runtimeConfig.state_name).toBe("other");
  });

  test("defaults are inert callables and empty state", () => {
    expect(runtimeConfig.initialEvents()).toEqual([]);
    expect(runtimeConfig.onLoadInternalEvent()).toEqual([]);
    expect(runtimeConfig.initialState).toEqual({});
    expect(runtimeConfig.exception_state_name).toBeUndefined();
  });
});

import { describe, expect, it } from "vitest";
import { APP_NAME, API_VERSION } from "@rasoi/shared";

describe("placeholder scaffold test", () => {
  it("exposes the shared app name", () => {
    expect(APP_NAME).toBe("Rasoi Radar");
  });

  it("exposes the API version prefix", () => {
    expect(API_VERSION).toBe("api/v1");
  });
});

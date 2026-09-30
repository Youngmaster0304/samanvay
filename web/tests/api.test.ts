import { describe, expect, it } from "vitest";

import { API_BASE, readyzUrl } from "../src/lib/api";

describe("api urls", () => {
  it("targets the published API port by default", () => {
    expect(API_BASE).toBe("http://localhost:8000");
  });

  it("builds the readiness endpoint under the configured base", () => {
    expect(readyzUrl()).toBe("http://localhost:8000/readyz");
    expect(readyzUrl("http://api:8000/")).toBe("http://api:8000/readyz");
  });
});

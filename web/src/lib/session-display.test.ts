import { describe, expect, it } from "vitest";

import {
  chatControlStateLabel,
  configuredModelLabel,
  sessionModelLabel,
  sessionSourceLabel,
} from "./session-display";

describe("truthful session display labels", () => {
  it("never invents a local source for missing session provenance", () => {
    expect(sessionSourceLabel(null)).toBe("source not recorded");
    expect(sessionSourceLabel("telegram")).toBe("telegram");
  });

  it("separates missing session metadata from runtime model readiness", () => {
    expect(sessionModelLabel(null)).toBe("model not recorded");
    expect(configuredModelLabel(null)).toBe("model not observed");
    expect(configuredModelLabel("openai/gpt-5.5")).toBe("gpt-5.5");
  });

  it("names the auxiliary connection instead of implying gateway health", () => {
    expect(chatControlStateLabel("closed")).toBe("chat controls: closed");
    expect(chatControlStateLabel("open")).toBe("chat controls: live");
  });
});

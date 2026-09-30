import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

const here = dirname(fileURLToPath(import.meta.url));
const srcDir = resolve(here, "../src");
const css = readFileSync(resolve(srcDir, "app/globals.css"), "utf8");

function hexValues(source: string): string[] {
  return [...source.matchAll(/#[0-9a-fA-F]{3,8}\b/g)].map((match) => match[0].toLowerCase());
}

/** A colour counts as blue/purple when blue is strictly its strongest channel. */
function isBlueOrPurple(hex: string): boolean {
  const value = hex.slice(1);
  const full =
    value.length === 3
      ? value
          .split("")
          .map((c) => c + c)
          .join("")
      : value.slice(0, 6);
  const r = parseInt(full.slice(0, 2), 16);
  const g = parseInt(full.slice(2, 4), 16);
  const b = parseInt(full.slice(4, 6), 16);
  return b > r && b > g;
}

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (/\.(ts|tsx)$/.test(entry)) out.push(full);
  }
  return out;
}

const sourceFiles = walk(srcDir);

describe("design tokens", () => {
  it("defines the palette from docs/design.md section 3.1", () => {
    const required: Record<string, string> = {
      "--paper-50": "#fbf8f1",
      "--paper-100": "#f4eee1",
      "--surface": "#fffdf7",
      "--ink-900": "#1a1712",
      "--marigold-500": "#f26a1b",
      "--marigold-700": "#933b08",
      "--paddy-600": "#1f7a3e",
      "--turmeric-500": "#e7a400",
      "--chilli-600": "#c4183c",
      "--rani-500": "#d9327a",
    };

    for (const [token, hex] of Object.entries(required)) {
      expect(css, `${token} must be ${hex}`).toContain(`${token}: ${hex}`);
    }
  });

  it("declares the map layer palette from docs/design.md section 3.3", () => {
    const layers: Record<string, string> = {
      "--layer-drone": "#f26a1b",
      "--layer-cadastral": "#1a1712",
      "--layer-revenue": "#d9327a",
      "--layer-municipal": "#8fbf00",
      "--layer-utility": "#e7a400",
      "--layer-canonical": "#1f7a3e",
      "--layer-conflict": "#c4183c",
    };

    for (const [token, hex] of Object.entries(layers)) {
      expect(css, `${token} must be ${hex}`).toContain(`${token}: ${hex}`);
    }
  });

  it("declares the confidence grade ramp from docs/design.md section 3.4", () => {
    const grades: Record<string, string> = {
      "--grade-a": "#1f7a3e",
      "--grade-b": "#8fae2a",
      "--grade-c": "#e7a400",
      "--grade-d": "#e8791f",
      "--grade-e": "#c4183c",
    };

    for (const [token, hex] of Object.entries(grades)) {
      expect(css, `${token} must be ${hex}`).toContain(`${token}: ${hex}`);
    }
  });

  it("declares status fills, spacing, radius and motion from docs/design.md 3.5 and 5.1", () => {
    const required = [
      "--status-auto-resolved",
      "--status-accepted",
      "--status-needs-review",
      "--status-dispute",
      "--status-rejected",
      "--space-1: 4px",
      "--space-4: 16px",
      "--space-8: 32px",
      "--radius-control: 4px",
      "--radius-panel: 6px",
      "--radius-dialog: 8px",
      "--shadow-popover",
      "--motion-fly-to",
      "--grade-cb-3",
      "--casing-light",
    ];

    for (const token of required) {
      expect(css, `missing token ${token}`).toContain(token);
    }
  });

  it("keeps primary button labels dark, never white on marigold-500", () => {
    expect(css).toContain("--on-primary: var(--ink-900)");
    expect(css).not.toMatch(/--on-primary:\s*#ffffff/i);
  });

  it("uses no blue or purple anywhere", () => {
    const offenders = hexValues(css).filter(isBlueOrPurple);
    expect(offenders, `blue/purple hexes found: ${offenders.join(", ")}`).toEqual([]);
  });

  it("ships the night theme and honours reduced motion", () => {
    expect(css).toContain(':root[data-theme="night"]');
    expect(css).toContain("prefers-reduced-motion: reduce");
  });

  it("gives :focus-visible a visible two-tone ring", () => {
    const rule = css.match(/:focus-visible\s*\{[^}]*\}/)?.[0];
    expect(rule, ":focus-visible rule missing").toBeTruthy();
    expect(rule).toContain("box-shadow");
    expect(rule).toContain("var(--focus)");
    expect(rule).toContain("var(--surface)");
  });
});

describe("component source", () => {
  it("uses no blue or purple hex in any component, page or map style", () => {
    const offenders: string[] = [];
    for (const file of sourceFiles) {
      if (file.endsWith("globals.css")) continue;
      for (const hex of hexValues(readFileSync(file, "utf8"))) {
        if (isBlueOrPurple(hex)) offenders.push(`${file}: ${hex}`);
      }
    }
    expect(offenders, offenders.join("\n")).toEqual([]);
  });

  it("never renders a skeleton or pulse placeholder", () => {
    const offenders = sourceFiles.filter((file) =>
      /animate-pulse|skeleton|Skeleton/i.test(readFileSync(file, "utf8")),
    );
    expect(offenders, `skeleton placeholders in: ${offenders.join(", ")}`).toEqual([]);
  });

  it("keeps map data colours inside the docs/design.md palette", () => {
    const allowed = new Set([
      "#fbf8f1",
      "#fffdf7",
      "#f4eee1",
      "#e8dfcc",
      "#1a1712",
      "#26221a",
      "#f26a1b",
      "#8fbf00",
      "#e7a400",
      "#1f7a3e",
      "#c4183c",
      "#d9327a",
      "#ff8a3d",
      "#933b08",
      "#b8480a",
      "#8a5f00",
      "#6b6252",
      "#857a67",
      "#f3ede0",
      "#b5aa94",
      "#3a3428",
      "#8f846f",
      "#ffffff",
    ]);
    const offenders: string[] = [];
    for (const file of sourceFiles) {
      if (file.endsWith("globals.css")) continue;
      for (const hex of hexValues(readFileSync(file, "utf8"))) {
        if (!allowed.has(hex)) offenders.push(`${file}: ${hex}`);
      }
    }
    expect(offenders, `off-palette colours:\n${offenders.join("\n")}`).toEqual([]);
  });
});

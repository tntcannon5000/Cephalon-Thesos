import { describe, expect, it } from "vitest";

import { themes } from "./themes";

describe("theme registry", () => {
  it("keeps every theme id unique", () => {
    expect(new Set(themes.map((theme) => theme.id)).size).toBe(themes.length);
    expect(themes).toHaveLength(9);
  });

  it("defines the Star Chart as a darkened image-backed environment", () => {
    const starChart = themes.find((theme) => theme.id === "star-chart");

    expect(starChart?.colorScheme).toBe("dark");
    expect(starChart?.backdrop?.image).toContain("star-chart.png");
    expect(starChart?.backdrop?.overlay).toContain("0.64");
    expect(starChart?.backdrop?.position).toBe("center center");
  });

  it("contains the two new light environments", () => {
    expect(themes.filter((theme) => theme.colorScheme === "light").map((theme) => theme.id)).toEqual([
      "zariman-residuum",
      "vallis-survey",
    ]);
  });

  it("preserves true black for the OLED theme shell", () => {
    const oled = themes.find((theme) => theme.id === "sentient-eclipse");

    expect(oled?.palette.background).toBe("#000000");
    expect(oled?.palette.sidebar).toContain("0, 0, 0");
    expect(oled?.scene.background).toBe(0x000000);
  });

  it("keeps every persistent Void Darkness surface at OLED black", () => {
    const voidTheme = themes.find((theme) => theme.id === "void-darkness");

    expect(voidTheme?.colorScheme).toBe("dark");
    expect(voidTheme?.scene.profile).toBe("void");
    expect([
      voidTheme?.palette.background,
      voidTheme?.palette.surface,
      voidTheme?.palette.surfaceSolid,
      voidTheme?.palette.surfaceRaised,
      voidTheme?.palette.surfaceHover,
      voidTheme?.palette.sidebar,
      voidTheme?.palette.header,
      voidTheme?.palette.userBubble,
    ]).toEqual(Array.from({ length: 8 }, () => "#000000"));
    expect(voidTheme?.scene.background).toBe(0x000000);
    expect(voidTheme?.scene.fog).toBe(0x000000);
  });
});

import { describe, expect, it } from "vitest";

import { themes } from "./themes";

describe("theme registry", () => {
  it("keeps every theme id unique", () => {
    expect(new Set(themes.map((theme) => theme.id)).size).toBe(themes.length);
    expect(themes).toHaveLength(8);
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

  it("includes a darker blue Void environment", () => {
    const voidTheme = themes.find((theme) => theme.id === "void-darkness");

    expect(voidTheme?.colorScheme).toBe("dark");
    expect(voidTheme?.scene.profile).toBe("void");
    expect(voidTheme?.palette.background).toBe("#010207");
  });
});

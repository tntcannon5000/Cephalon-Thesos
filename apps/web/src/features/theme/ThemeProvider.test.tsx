import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { useTheme } from "./ThemeContext";
import { ThemeProvider } from "./ThemeProvider";

function ThemeProbe() {
  const { themeId, setThemeId } = useTheme();
  return (
    <>
      <output>{themeId}</output>
      <button type="button" onClick={() => setThemeId("corpus-relay")}>Corpus</button>
      <button type="button" onClick={() => setThemeId("vallis-survey")}>Vallis</button>
    </>
  );
}

describe("ThemeProvider", () => {
  beforeEach(() => {
    localStorage.clear();
    delete document.documentElement.dataset.theme;
  });

  it("defaults to the Murmur theme and remembers a selection", () => {
    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    );

    expect(screen.getByText("murmur-labyrinth")).toBeInTheDocument();
    expect(document.documentElement.dataset.theme).toBe("murmur-labyrinth");

    fireEvent.click(screen.getByRole("button", { name: "Corpus" }));

    expect(screen.getByText("corpus-relay")).toBeInTheDocument();
    expect(localStorage.getItem("thesos.theme.v1")).toBe("corpus-relay");
    expect(document.documentElement.dataset.activityMotion).toBe("signal");
  });

  it("applies browser color-scheme semantics for light themes", () => {
    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Vallis" }));

    expect(document.documentElement.dataset.colorScheme).toBe("light");
    expect(document.documentElement.style.colorScheme).toBe("light");
    expect(document.documentElement.style.getPropertyValue("--background")).toBe("#e8f0f2");
  });
});

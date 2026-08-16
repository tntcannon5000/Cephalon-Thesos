import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DeveloperPanel } from "./DeveloperPanel";

const mocks = vi.hoisted(() => ({ clear: vi.fn() }));

vi.mock("../features/developer/useDeveloperLogs", () => ({
  useDeveloperLogs: () => ({
    clear: mocks.clear,
    connection: "live",
    logs: [
      {
        id: "frontend-1",
        sequence: 1,
        timestamp: "2026-08-15T12:00:00.000Z",
        layer: "frontend",
        level: "info",
        logger: "transport.runs",
        message: "Agent run accepted",
      },
      {
        id: "ai-2",
        sequence: 2,
        timestamp: "2026-08-15T12:00:01.000Z",
        layer: "ai",
        level: "error",
        logger: "veris_api.agent",
        message: "Provider request failed",
      },
    ],
  }),
}));

describe("DeveloperPanel", () => {
  it("filters output by application layer", () => {
    render(<DeveloperPanel onClose={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "AI" }));

    expect(screen.getByText("Provider request failed")).toBeInTheDocument();
    expect(screen.queryByText("Agent run accepted")).not.toBeInTheDocument();
  });

  it("supports pause, clear, and close controls", () => {
    const onClose = vi.fn();
    render(<DeveloperPanel onClose={onClose} />);

    fireEvent.click(screen.getByRole("button", { name: "Pause developer console" }));
    expect(screen.getByRole("button", { name: "Resume developer console" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Clear developer console" }));
    expect(mocks.clear).toHaveBeenCalledOnce();

    fireEvent.click(screen.getByRole("button", { name: "Close developer console" }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Header } from "./Header";

describe("Header", () => {
  it("enables the developer console from the header toggle", () => {
    const onDeveloperModeChange = vi.fn();
    render(
      <Header
        conversation={null}
        developerMode={false}
        onDeveloperModeChange={onDeveloperModeChange}
        onOpenMenu={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("checkbox", { name: "Developer mode" }));

    expect(onDeveloperModeChange).toHaveBeenCalledWith(true);
    expect(screen.getByRole("button", { name: "Log in" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign up" })).toBeInTheDocument();
    expect(screen.queryByText("Sample data")).not.toBeInTheDocument();
  });

  it("shows the prompt until a generated title arrives", async () => {
    const { rerender } = render(
      <Header
        conversation={{
          id: "conversation-1",
          title: "How do Void relics work?",
          titleState: "pending",
          pinned: false,
          messages: [],
          updatedAt: new Date().toISOString(),
          terminated: false,
        }}
        developerMode={false}
        onDeveloperModeChange={vi.fn()}
        onOpenMenu={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "How do Void relics work?" })).toHaveClass(
      "is-pending",
    );

    rerender(
      <Header
        conversation={{
          id: "conversation-1",
          title: "Void Relic Rewards",
          titleState: "generated",
          pinned: false,
          messages: [],
          updatedAt: new Date().toISOString(),
          terminated: false,
        }}
        developerMode={false}
        onDeveloperModeChange={vi.fn()}
        onOpenMenu={vi.fn()}
      />,
    );

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Void Relic Rewards" })).not.toHaveClass(
        "is-pending",
      ),
    );
  });
});

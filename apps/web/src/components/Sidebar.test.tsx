import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Conversation } from "../features/chat/types";
import { Sidebar } from "./Sidebar";

function transmission(id: string, title: string, pinned: boolean): Conversation {
  return {
    id,
    title,
    titleState: "generated",
    pinned,
    messages: [],
    updatedAt: new Date().toISOString(),
    terminated: false,
  };
}

function renderSidebar(conversations: Conversation[]) {
  const onDelete = vi.fn();
  const onOpenThemes = vi.fn();
  const onTogglePinned = vi.fn();
  render(
    <Sidebar
      conversations={conversations}
      activeId={null}
      open
      onClose={vi.fn()}
      onNewChat={vi.fn()}
      onSelect={vi.fn()}
      onDelete={onDelete}
      onTogglePinned={onTogglePinned}
      onOpenThemes={onOpenThemes}
      width={254}
      onWidthChange={vi.fn()}
      onWidthReset={vi.fn()}
    />,
  );
  return { onDelete, onOpenThemes, onTogglePinned };
}

describe("Sidebar transmissions", () => {
  it("shows pinned and recent transmissions in separate sections", () => {
    renderSidebar([
      transmission("pinned", "Pinned topic", true),
      transmission("recent", "Recent topic", false),
    ]);

    expect(screen.getByText("Pinned topic")).toBeInTheDocument();
    expect(screen.getByText("Recent topic")).toBeInTheDocument();
    expect(screen.queryByText(/Right click a transmission/)).not.toBeInTheDocument();
  });

  it("offers pin, disabled share, and delete in a custom context menu", () => {
    const { onDelete, onTogglePinned } = renderSidebar([
      transmission("recent", "Recent topic", false),
    ]);
    const entry = screen.getByText("Recent topic").closest("button");
    expect(entry).not.toBeNull();

    fireEvent.contextMenu(entry as HTMLButtonElement, { clientX: 40, clientY: 60 });
    expect(screen.getByRole("menuitem", { name: "Share" })).toBeDisabled();
    fireEvent.click(screen.getByRole("menuitem", { name: "Pin" }));
    expect(onTogglePinned).toHaveBeenCalledWith("recent");

    fireEvent.contextMenu(entry as HTMLButtonElement, { clientX: 40, clientY: 60 });
    fireEvent.click(screen.getByRole("menuitem", { name: "Delete" }));
    expect(onDelete).toHaveBeenCalledWith("recent");
  });

  it("explains how to populate an empty pinned section", () => {
    renderSidebar([]);

    expect(
      screen.getByText("Right click a transmission and pin it to keep it here for your convenience."),
    ).toBeInTheDocument();
  });

  it("opens theme selection from above settings", () => {
    const { onOpenThemes } = renderSidebar([]);

    fireEvent.click(screen.getByRole("button", { name: "Theme" }));

    expect(onOpenThemes).toHaveBeenCalledOnce();
    const theme = screen.getByRole("button", { name: "Theme" });
    const settings = screen.getByRole("button", { name: "Settings" });
    expect(theme.compareDocumentPosition(settings) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

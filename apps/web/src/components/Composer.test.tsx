import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Composer } from "./Composer";

const defaults = {
  draft: "",
  editing: false,
  landing: false,
  running: false,
  terminated: false,
  onDraftChange: vi.fn(),
  onSubmit: vi.fn(),
  onStop: vi.fn(),
  onCancelEdit: vi.fn(),
  onNewChat: vi.fn(),
};

describe("Composer", () => {
  it("replaces the input with a termination banner", () => {
    render(<Composer {...defaults} terminated />);
    expect(screen.getByText("This conversation has been terminated.")).toBeInTheDocument();
    expect(screen.queryByLabelText("Message Thesos")).not.toBeInTheDocument();
  });

  it("submits a populated prompt", () => {
    const onSubmit = vi.fn();
    render(<Composer {...defaults} draft="Where does this drop?" onSubmit={onSubmit} />);
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    expect(onSubmit).toHaveBeenCalledOnce();
  });

  it("submits with Enter and keeps Shift+Enter for a new line", () => {
    const onSubmit = vi.fn();
    render(<Composer {...defaults} draft="Question" onSubmit={onSubmit} />);
    const input = screen.getByRole("textbox", { name: "Message Thesos" });

    fireEvent.keyDown(input, { key: "Enter", shiftKey: true });
    expect(onSubmit).not.toHaveBeenCalled();

    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSubmit).toHaveBeenCalledOnce();
  });

  it("focuses the message input from the surrounding composer surface", () => {
    render(<Composer {...defaults} />);

    fireEvent.pointerDown(screen.getByRole("form", { name: "Message composer" }));

    expect(screen.getByRole("textbox", { name: "Message Thesos" })).toHaveFocus();
    expect(screen.getByText("Ask Thesos...")).toHaveAttribute("aria-hidden", "true");
  });
});

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { IntroSequence } from "./IntroSequence";

describe("IntroSequence", () => {
  it("offers account access without asking for a name while logged out", () => {
    const onLogin = vi.fn();
    const onRegister = vi.fn();

    render(
      <IntroSequence
        mode="auth"
        skipTyping
        onLogin={onLogin}
        onRegister={onRegister}
      />,
    );

    expect(screen.queryByLabelText("How should I address you?")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
    fireEvent.click(screen.getByRole("button", { name: "Register" }));
    expect(onLogin).toHaveBeenCalledOnce();
    expect(onRegister).toHaveBeenCalledOnce();
  });

  it("normalizes the name before entering the archive", () => {
    const onComplete = vi.fn();
    render(<IntroSequence skipTyping onComplete={onComplete} />);

    fireEvent.change(screen.getByLabelText("How should I address you?"), {
      target: { value: "  Nyx Prime  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Enter the Archives" }));
    expect(onComplete).toHaveBeenCalledWith("Nyx Prime");
  });
});

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { suggestions } from "../features/chat/suggestions";
import { SuggestionRail } from "./SuggestionRail";

describe("SuggestionRail", () => {
  it("sends the selected prompt", () => {
    const onSelect = vi.fn();
    render(<SuggestionRail suggestions={suggestions} onSelect={onSelect} />);
    fireEvent.click(screen.getByText(suggestions[0]?.prompt ?? ""));
    expect(onSelect).toHaveBeenCalledWith(suggestions[0]?.prompt);
  });
});

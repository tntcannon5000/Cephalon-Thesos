import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { MetricPoint } from "../transport/admin";
import { CostEstimateChart, TokenVolumeChart } from "./AdminCharts";

const points: MetricPoint[] = [
  {
    started_at: "2026-08-17T12:00:00Z",
    attempts: 2,
    runs: 1,
    request_tokens: 900,
    response_tokens: 300,
    total_tokens: 1200,
    estimated_cost_usd: "0.0042",
  },
];

describe("AdminCharts", () => {
  it("renders accessible token and cost timelines", () => {
    render(
      <>
        <TokenVolumeChart points={points} period="hour" />
        <CostEstimateChart points={points} period="hour" />
      </>,
    );

    expect(screen.getByRole("img", { name: "Token volume over time" })).toBeInTheDocument();
    expect(
      screen.getByRole("img", { name: "Estimated provider cost over time" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/1,200 tokens/)).toBeInTheDocument();
    expect(screen.getByText(/\$0.004200/)).toBeInTheDocument();
  });
});

import type { MetricPoint, MetricsPeriod } from "../transport/admin";

interface ChartProps {
  points: MetricPoint[];
  period: MetricsPeriod;
}

const WIDTH = 960;
const HEIGHT = 220;
const LEFT = 54;
const RIGHT = 18;
const TOP = 18;
const BOTTOM = 34;

function bucketLabel(value: string, period: MetricsPeriod): string {
  const date = new Date(value);
  if (period === "year") return date.toLocaleDateString(undefined, { month: "short" });
  if (period === "week" || period === "month") {
    return date.toLocaleDateString(undefined, { day: "numeric", month: "short" });
  }
  return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function selectedLabel(index: number, length: number): boolean {
  if (length <= 7) return true;
  const interval = Math.max(1, Math.ceil(length / 6));
  return index === 0 || index === length - 1 || index % interval === 0;
}

function compact(value: number): string {
  return Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export function TokenVolumeChart({ points, period }: ChartProps) {
  const plotWidth = WIDTH - LEFT - RIGHT;
  const plotHeight = HEIGHT - TOP - BOTTOM;
  const maximum = Math.max(1, ...points.map((point) => point.total_tokens));
  const slot = plotWidth / Math.max(1, points.length);
  const barWidth = Math.max(3, slot * 0.62);

  return (
    <div className="admin-chart-frame">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Token volume over time">
        {[0, 0.5, 1].map((ratio) => {
          const y = TOP + plotHeight * ratio;
          return <line className="chart-grid" key={ratio} x1={LEFT} x2={WIDTH - RIGHT} y1={y} y2={y} />;
        })}
        <text className="chart-axis-value" x={LEFT - 8} y={TOP + 4}>{compact(maximum)}</text>
        <text className="chart-axis-value" x={LEFT - 8} y={TOP + plotHeight + 4}>0</text>
        {points.map((point, index) => {
          const height = (point.total_tokens / maximum) * plotHeight;
          const x = LEFT + slot * index + (slot - barWidth) / 2;
          const y = TOP + plotHeight - height;
          return (
            <g key={point.started_at}>
              <rect className="chart-bar" x={x} y={y} width={barWidth} height={Math.max(height, point.total_tokens ? 2 : 0)}>
                <title>{bucketLabel(point.started_at, period)}: {point.total_tokens.toLocaleString()} tokens</title>
              </rect>
              {selectedLabel(index, points.length) ? <text className="chart-label" x={x + barWidth / 2} y={HEIGHT - 10}>{bucketLabel(point.started_at, period)}</text> : null}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function CostEstimateChart({ points, period }: ChartProps) {
  const plotWidth = WIDTH - LEFT - RIGHT;
  const plotHeight = HEIGHT - TOP - BOTTOM;
  const values = points.map((point) => Number(point.estimated_cost_usd));
  const maximum = Math.max(0.000001, ...values);
  const slot = plotWidth / Math.max(1, points.length);
  const coordinates = values.map((value, index) => ({
    x: LEFT + slot * index + slot / 2,
    y: TOP + plotHeight - (value / maximum) * plotHeight,
  }));
  const path = coordinates.map((point, index) => `${index ? "L" : "M"}${point.x},${point.y}`).join(" ");

  return (
    <div className="admin-chart-frame">
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Estimated provider cost over time">
        {[0, 0.5, 1].map((ratio) => {
          const y = TOP + plotHeight * ratio;
          return <line className="chart-grid" key={ratio} x1={LEFT} x2={WIDTH - RIGHT} y1={y} y2={y} />;
        })}
        <text className="chart-axis-value" x={LEFT - 8} y={TOP + 4}>${maximum.toFixed(4)}</text>
        <text className="chart-axis-value" x={LEFT - 8} y={TOP + plotHeight + 4}>$0</text>
        <path className="chart-line" d={path} />
        {coordinates.map((coordinate, index) => {
          const point = points[index];
          const value = values[index];
          if (!point || value === undefined) return null;
          return (
            <g key={point.started_at}>
              <circle className="chart-point" cx={coordinate.x} cy={coordinate.y} r={3}>
                <title>{bucketLabel(point.started_at, period)}: ${value.toFixed(6)}</title>
              </circle>
              {selectedLabel(index, points.length) ? <text className="chart-label" x={coordinate.x} y={HEIGHT - 10}>{bucketLabel(point.started_at, period)}</text> : null}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

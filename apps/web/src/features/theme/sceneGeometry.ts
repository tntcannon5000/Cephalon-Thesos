import { Vector3 } from "three";

import type { SceneTheme } from "./themes";

export function railPoints(index: number, theme: SceneTheme): Vector3[] {
  const y = -4.8 + index * (9.6 / Math.max(theme.railCount - 1, 1));
  const direction = index % 2 === 0 ? 1 : -1;

  if (theme.profile === "labyrinth") {
    return [
      new Vector3(-10, y, -5),
      new Vector3(-7.2, y, -4.2),
      new Vector3(-6.5, y + 0.2 * direction, -3.8),
      new Vector3(-3.8, y + 0.2 * direction, -3.2),
      new Vector3(-3.2, y, -3),
      new Vector3(3.2, y, -3),
      new Vector3(3.8, y - 0.2 * direction, -3.2),
      new Vector3(6.5, y - 0.2 * direction, -3.8),
      new Vector3(7.2, y, -4.2),
      new Vector3(10, y, -5),
    ];
  }

  if (theme.profile === "relay") {
    return [
      new Vector3(-10, y, -5),
      new Vector3(-6.2, y, -3.9),
      new Vector3(-5.6, y + 0.12 * direction, -3.5),
      new Vector3(-4.9, y, -3.2),
      new Vector3(4.9, y, -3.2),
      new Vector3(5.6, y - 0.12 * direction, -3.5),
      new Vector3(6.2, y, -3.9),
      new Vector3(10, y, -5),
    ];
  }

  if (theme.profile === "zariman") {
    const fracture = index % 3 === 1 ? 0.24 * direction : 0;
    return [
      new Vector3(-10, y, -5),
      new Vector3(-7.4, y, -4.1),
      new Vector3(-6.4, y + fracture, -3.6),
      new Vector3(-2.8, y + fracture, -3.1),
      new Vector3(2.8, y - fracture, -3.1),
      new Vector3(6.4, y - fracture, -3.6),
      new Vector3(7.4, y, -4.1),
      new Vector3(10, y, -5),
    ];
  }

  if (theme.profile === "vallis") {
    const points: Vector3[] = [];
    for (let step = 0; step <= 18; step += 1) {
      const x = -10 + step * (20 / 18);
      const contour =
        Math.sin(step * 0.68 + index * 0.82) * (0.16 + index * 0.008) +
        Math.sin(step * 0.19 + index) * 0.08;
      points.push(new Vector3(x, y + contour, -4.8 + Math.abs(x) * 0.12));
    }
    return points;
  }

  if (theme.profile === "deimos") {
    const side = index % 2 === 0 ? -1 : 1;
    return [
      new Vector3(side * 10, y, -5),
      new Vector3(side * 8.1, y + 0.25 * direction, -4.2),
      new Vector3(side * 6.9, y - 0.18 * direction, -3.7),
      new Vector3(side * 5.8, y + 0.08 * direction, -3.3),
    ];
  }

  if (theme.profile === "sentient") {
    const leftInset = 1.4 + (index % 3) * 0.8;
    return index % 2 === 0
      ? [
          new Vector3(-10, y, -5),
          new Vector3(-8.2, y + 0.18, -4.1),
          new Vector3(-6.9, y - 0.13, -3.6),
          new Vector3(-leftInset - 4.2, y + 0.1, -3.3),
        ]
      : [
          new Vector3(10, y, -5),
          new Vector3(7.6, y - 0.15, -4.1),
          new Vector3(6.5, y + 0.2, -3.6),
          new Vector3(leftInset + 3.7, y, -3.3),
        ];
  }

  if (theme.profile === "void") {
    const offset = 0.18 + (index % 3) * 0.13;
    return index % 2 === 0
      ? [
          new Vector3(-10, y, -5),
          new Vector3(-7.4, y + offset, -4.2),
          new Vector3(-5.2, y - offset * 0.4, -3.6),
          new Vector3(-2.1, y + offset * 0.7, -3.15),
        ]
      : [
          new Vector3(10, y, -5),
          new Vector3(7.4, y - offset, -4.2),
          new Vector3(5.2, y + offset * 0.4, -3.6),
          new Vector3(2.1, y - offset * 0.7, -3.15),
        ];
  }

  return [
    new Vector3(-10, y, -5),
    new Vector3(-4.4, y, -3.2),
    new Vector3(4.4, y, -3.2),
    new Vector3(10, y, -5),
  ];
}

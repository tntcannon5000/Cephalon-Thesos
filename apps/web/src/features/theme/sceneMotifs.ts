import {
  BufferAttribute,
  BufferGeometry,
  CatmullRomCurve3,
  EllipseCurve,
  Group,
  Line,
  LineBasicMaterial,
  LineSegments,
  Points,
  PointsMaterial,
  Vector3,
  type Material,
} from "three";

import type { SceneTheme } from "./themes";

export interface SceneMotif {
  group: Group;
  update: (elapsed: number) => void;
  dispose: () => void;
}

interface MotifResources {
  geometries: BufferGeometry[];
  materials: Material[];
}

function createResources(): MotifResources {
  return { geometries: [], materials: [] };
}

function addLine(
  group: Group,
  points: Vector3[],
  color: number,
  opacity: number,
  resources: MotifResources,
) {
  const geometry = new BufferGeometry().setFromPoints(points);
  const material = new LineBasicMaterial({ color, opacity, transparent: true });
  resources.geometries.push(geometry);
  resources.materials.push(material);
  const line = new Line(geometry, material);
  group.add(line);
  return { line, material };
}

function finishMotif(
  group: Group,
  resources: MotifResources,
  update: (elapsed: number) => void,
): SceneMotif {
  return {
    group,
    update,
    dispose: () => {
      resources.geometries.forEach((geometry) => geometry.dispose());
      resources.materials.forEach((material) => material.dispose());
    },
  };
}

function createZarimanMotif(theme: SceneTheme): SceneMotif {
  const group = new Group();
  const resources = createResources();
  const fractureMaterials: LineBasicMaterial[] = [];

  const arcs = [
    { x: -5.7, y: 2.9, rx: 4.6, ry: 2.1, start: -0.08, end: 1.2 },
    { x: 5.5, y: -2.6, rx: 4.1, ry: 1.8, start: 0.48, end: 1.74 },
    { x: -6.1, y: -3.7, rx: 3.2, ry: 1.2, start: 0.02, end: 1.08 },
    { x: 6.4, y: 3.8, rx: 3.5, ry: 1.25, start: 0.55, end: 1.75 },
  ];
  arcs.forEach(({ x, y, rx, ry, start, end }) => {
    const curve = new EllipseCurve(x, y, rx, ry, start * Math.PI, end * Math.PI);
    const points = curve.getPoints(48).map((point) => new Vector3(point.x, point.y, -3.35));
    addLine(group, points, theme.rails, 0.15, resources);
  });

  const fractures = [
    [
      new Vector3(-10, 3.35, -2.8),
      new Vector3(-8.7, 3.1, -2.8),
      new Vector3(-7.9, 3.48, -2.8),
      new Vector3(-7.2, 2.92, -2.8),
      new Vector3(-6.2, 3.08, -2.8),
      new Vector3(-5.25, 2.52, -2.8),
    ],
    [
      new Vector3(-7.9, 3.48, -2.8),
      new Vector3(-7.65, 4.18, -2.8),
      new Vector3(-7.05, 4.55, -2.8),
    ],
    [
      new Vector3(10, -2.72, -2.7),
      new Vector3(8.8, -2.45, -2.7),
      new Vector3(8.2, -2.87, -2.7),
      new Vector3(7.4, -2.35, -2.7),
      new Vector3(6.3, -2.64, -2.7),
      new Vector3(5.45, -2.08, -2.7),
    ],
    [
      new Vector3(8.2, -2.87, -2.7),
      new Vector3(8.05, -3.62, -2.7),
      new Vector3(7.4, -4.04, -2.7),
    ],
  ];
  fractures.forEach((points) => {
    const { material } = addLine(group, points, theme.particleSecondary, 0.2, resources);
    fractureMaterials.push(material);
  });

  return finishMotif(group, resources, (elapsed) => {
    group.rotation.z = Math.sin(elapsed * 0.055) * 0.0025;
    const shimmer = Math.pow(Math.max(0, Math.sin(elapsed * 0.47 - 1.8)), 8);
    fractureMaterials.forEach((material, index) => {
      material.opacity = 0.13 + shimmer * (index % 2 === 0 ? 0.34 : 0.22);
    });
  });
}

function createVallisMotif(theme: SceneTheme, densityScale: number): SceneMotif {
  const group = new Group();
  const resources = createResources();
  const snowCount = Math.max(32, Math.round(74 * densityScale));
  const snowPositions = new Float32Array(snowCount * 6);
  const snowSpeeds = new Float32Array(snowCount);

  for (let index = 0; index < snowCount; index += 1) {
    const offset = index * 6;
    const x = (Math.random() - 0.5) * 22;
    const y = (Math.random() - 0.5) * 13;
    const z = -1.8 - Math.random() * 5;
    const length = 0.07 + Math.random() * 0.16;
    snowPositions[offset] = x;
    snowPositions[offset + 1] = y;
    snowPositions[offset + 2] = z;
    snowPositions[offset + 3] = x + length * 0.42;
    snowPositions[offset + 4] = y - length;
    snowPositions[offset + 5] = z;
    snowSpeeds[index] = 0.16 + Math.random() * 0.28;
  }

  const snowGeometry = new BufferGeometry();
  const snowAttribute = new BufferAttribute(snowPositions, 3);
  snowGeometry.setAttribute("position", snowAttribute);
  const snowMaterial = new LineBasicMaterial({
    color: theme.particlePrimary,
    opacity: 0.17,
    transparent: true,
  });
  resources.geometries.push(snowGeometry);
  resources.materials.push(snowMaterial);
  group.add(new LineSegments(snowGeometry, snowMaterial));

  const beaconMaterials: LineBasicMaterial[] = [];
  [-8.4, -5.9, 6.7, 8.7].forEach((x, index) => {
    const height = 0.72 + (index % 2) * 0.38;
    const y = index < 2 ? -3.3 + index * 1.3 : 2.4 - index * 0.52;
    const points = [
      new Vector3(x, y, -2.75),
      new Vector3(x, y + height, -2.75),
      new Vector3(x - 0.22, y + height - 0.2, -2.75),
      new Vector3(x + 0.22, y + height - 0.2, -2.75),
      new Vector3(x, y + height, -2.75),
    ];
    const { material } = addLine(group, points, theme.particleSecondary, 0.2, resources);
    beaconMaterials.push(material);
  });

  const thermalBand = addLine(
    group,
    [new Vector3(-10, -4.15, -3), new Vector3(10, -4.15, -3)],
    theme.particleSecondary,
    0.1,
    resources,
  ).material;

  let previousElapsed = 0;
  return finishMotif(group, resources, (elapsed) => {
    const delta = Math.min(Math.max(elapsed - previousElapsed, 0), 0.05);
    previousElapsed = elapsed;
    for (let index = 0; index < snowCount; index += 1) {
      const offset = index * 6;
      const movementY = (snowSpeeds[index] ?? 0.2) * delta;
      const movementX = movementY * 0.42;
      const startX = (snowPositions[offset] ?? 0) + movementX;
      const startY = (snowPositions[offset + 1] ?? 0) - movementY;
      const endX = (snowPositions[offset + 3] ?? 0) + movementX;
      const endY = (snowPositions[offset + 4] ?? 0) - movementY;
      snowPositions[offset] = startX;
      snowPositions[offset + 1] = startY;
      snowPositions[offset + 3] = endX;
      snowPositions[offset + 4] = endY;
      if (startY < -6.5 || startX > 11) {
        const x = -11 + Math.random() * 18;
        const y = 6.4 + Math.random() * 0.5;
        const length = endX - startX;
        snowPositions[offset] = x;
        snowPositions[offset + 1] = y;
        snowPositions[offset + 3] = x + length;
        snowPositions[offset + 4] = y - Math.abs(length * 2.4);
      }
    }
    snowAttribute.needsUpdate = true;
    const sweep = (Math.sin(elapsed * 0.42) + 1) / 2;
    thermalBand.opacity = 0.06 + sweep * 0.11;
    beaconMaterials.forEach((material, index) => {
      material.opacity = 0.1 + Math.pow(Math.max(0, Math.sin(elapsed * 0.9 - index)), 6) * 0.34;
    });
  });
}

function createDeimosMotif(theme: SceneTheme): SceneMotif {
  const group = new Group();
  const resources = createResources();
  const vomeMaterials: LineBasicMaterial[] = [];
  const fassMaterials: LineBasicMaterial[] = [];

  for (let index = 0; index < 10; index += 1) {
    const left = index % 2 === 0;
    const side = left ? -1 : 1;
    const row = Math.floor(index / 2);
    const startY = -4.6 + row * 2.2;
    const points = [
      new Vector3(side * 10.5, startY, -4.3),
      new Vector3(side * (8.8 - row * 0.12), startY + (left ? 0.65 : -0.52), -3.8),
      new Vector3(side * (7.4 + row * 0.08), startY + (left ? 0.08 : 0.34), -3.2),
      new Vector3(side * (4.45 + row * 0.1), startY + (left ? 0.42 : -0.18), -2.8),
      new Vector3(side * (2.85 + row * 0.1), startY + 0.05, -2.65),
    ];
    const curve = new CatmullRomCurve3(points);
    const materialList = left ? vomeMaterials : fassMaterials;
    const { material } = addLine(
      group,
      curve.getPoints(42),
      left ? theme.particlePrimary : theme.particleSecondary,
      0.24,
      resources,
    );
    materialList.push(material);

    if (row % 2 === 0) {
      const bone = curve
        .getPoints(8)
        .filter((_, pointIndex) => pointIndex > 1 && pointIndex < 7);
      addLine(group, bone, theme.rails, 0.15, resources);
    }
  }

  return finishMotif(group, resources, (elapsed) => {
    const breath = (Math.sin(elapsed * 0.29) + 1) / 2;
    group.scale.setScalar(0.994 + breath * 0.012);
    vomeMaterials.forEach((material, index) => {
      material.opacity = 0.17 + breath * 0.29 + (index % 2) * 0.025;
    });
    fassMaterials.forEach((material, index) => {
      material.opacity = 0.17 + (1 - breath) * 0.29 + (index % 2) * 0.025;
    });
  });
}

interface SentientSegment {
  pivot: Group;
  material: LineBasicMaterial;
  baseRotation: number;
  index: number;
}

function createSentientMotif(theme: SceneTheme): SceneMotif {
  const group = new Group();
  const resources = createResources();
  const segments: SentientSegment[] = [];
  const jointPositions: number[] = [];

  const addChain = (
    originX: number,
    originY: number,
    direction: number,
    count: number,
    phaseOffset: number,
  ) => {
    let x = originX;
    let y = originY;
    for (let index = 0; index < count; index += 1) {
      const length = 0.72 + (index % 3) * 0.2;
      const rise = (index % 2 === 0 ? 0.2 : -0.28) * (phaseOffset % 2 === 0 ? 1 : -1);
      const pivot = new Group();
      pivot.position.set(x, y, -2.8 - index * 0.08);
      const geometry = new BufferGeometry().setFromPoints([
        new Vector3(0, 0, 0),
        new Vector3(direction * length, rise, 0),
      ]);
      const material = new LineBasicMaterial({
        color: index % 4 === 2 ? theme.particleSecondary : theme.particlePrimary,
        opacity: 0.28,
        transparent: true,
      });
      resources.geometries.push(geometry);
      resources.materials.push(material);
      pivot.add(new Line(geometry, material));
      group.add(pivot);
      segments.push({
        pivot,
        material,
        baseRotation: (index % 2 === 0 ? 1 : -1) * 0.025,
        index: index + phaseOffset,
      });
      jointPositions.push(x, y, -2.78 - index * 0.08);
      x += direction * length;
      y += rise;
    }
  };

  addChain(-8.6, 3.8, 1, 7, 0);
  addChain(8.9, -3.2, -1, 6, 3);
  addChain(-8.25, -2.5, 1, 5, 6);
  addChain(8.55, 4.35, -1, 5, 9);

  const jointGeometry = new BufferGeometry();
  jointGeometry.setAttribute("position", new BufferAttribute(new Float32Array(jointPositions), 3));
  const jointMaterial = new PointsMaterial({
    color: theme.particleSecondary,
    opacity: 0.54,
    size: 0.052,
    sizeAttenuation: true,
    transparent: true,
  });
  resources.geometries.push(jointGeometry);
  resources.materials.push(jointMaterial);
  group.add(new Points(jointGeometry, jointMaterial));

  return finishMotif(group, resources, (elapsed) => {
    const cycle = elapsed % 14;
    const awake = cycle < 4.8 ? Math.sin((cycle / 4.8) * Math.PI) : 0;
    segments.forEach(({ pivot, material, baseRotation, index }) => {
      const response = Math.max(0, awake - index * 0.035);
      pivot.rotation.z = baseRotation + Math.sin(elapsed * 1.25 - index * 0.48) * 0.055 * response;
      const pulseDistance = Math.abs(cycle * 2.3 - (index % 11));
      material.opacity = 0.18 + response * 0.18 + Math.max(0, 1 - pulseDistance) * 0.56;
    });
    jointMaterial.opacity = 0.3 + awake * 0.42;
  });
}

function createVoidMotif(theme: SceneTheme): SceneMotif {
  const group = new Group();
  const resources = createResources();
  const ringMaterials: LineBasicMaterial[] = [];

  [1.2, 2.1, 3.1].forEach((radius, index) => {
    const curve = new EllipseCurve(
      0,
      0,
      radius,
      radius * 0.58,
      Math.PI * (0.08 + index * 0.04),
      Math.PI * (1.72 - index * 0.03),
    );
    const points = curve
      .getPoints(72)
      .map((point) => new Vector3(point.x, point.y, -3 + index * 0.12));
    const { material } = addLine(
      group,
      points,
      index === 1 ? theme.particleSecondary : theme.particlePrimary,
      0.1 + index * 0.025,
      resources,
    );
    ringMaterials.push(material);
  });

  const horizon = addLine(
    group,
    [new Vector3(-4.2, 0, -3.05), new Vector3(4.2, 0, -3.05)],
    theme.rails,
    0.08,
    resources,
  ).material;

  return finishMotif(group, resources, (elapsed) => {
    group.rotation.z = Math.sin(elapsed * 0.11) * 0.018;
    ringMaterials.forEach((material, index) => {
      const pulse = (Math.sin(elapsed * 0.42 - index * 0.72) + 1) / 2;
      material.opacity = 0.055 + pulse * (0.12 + index * 0.025);
    });
    horizon.opacity = 0.045 + Math.pow(Math.max(0, Math.sin(elapsed * 0.3)), 5) * 0.16;
  });
}

export function createSceneMotif(theme: SceneTheme, densityScale = 1): SceneMotif {
  if (theme.profile === "zariman") return createZarimanMotif(theme);
  if (theme.profile === "vallis") return createVallisMotif(theme, densityScale);
  if (theme.profile === "deimos") return createDeimosMotif(theme);
  if (theme.profile === "void") return createVoidMotif(theme);
  if (theme.profile === "sentient") return createSentientMotif(theme);

  const resources = createResources();
  return finishMotif(new Group(), resources, () => undefined);
}

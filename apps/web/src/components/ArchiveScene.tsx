import { useEffect, useRef } from "react";
import {
  BufferAttribute,
  BufferGeometry,
  Color,
  FogExp2,
  Group,
  Line,
  LineBasicMaterial,
  PerspectiveCamera,
  Points,
  PointsMaterial,
  Scene,
  SRGBColorSpace,
  WebGLRenderer,
} from "three";

import { railPoints } from "../features/theme/sceneGeometry";
import { createSceneMotif } from "../features/theme/sceneMotifs";
import { useTheme } from "../features/theme/ThemeContext";

export function ArchiveScene() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { theme } = useTheme();

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const densityScale = window.matchMedia("(max-width: 820px)").matches ? 0.64 : 1;
    const renderer = new WebGLRenderer({ canvas, alpha: true, antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.5));
    renderer.outputColorSpace = SRGBColorSpace;
    renderer.setClearColor(theme.scene.background, 0);

    const scene = new Scene();
    scene.fog = new FogExp2(theme.scene.fog, theme.scene.fogDensity);
    const camera = new PerspectiveCamera(46, 1, 0.1, 100);
    camera.position.set(0, 0, 9);

    const particlePrimary = new Color(theme.scene.particlePrimary);
    const particleSecondary = new Color(theme.scene.particleSecondary);

    const particleCount = Math.round(theme.scene.particleCount * densityScale);
    const positions = new Float32Array(particleCount * 3);
    const colors = new Float32Array(particleCount * 3);
    for (let index = 0; index < particleCount; index += 1) {
      const offset = index * 3;
      positions[offset] = (Math.random() - 0.5) * 22;
      positions[offset + 1] = (Math.random() - 0.5) * 13;
      positions[offset + 2] = (Math.random() - 0.5) * 10 - 2;
      const color = index % 7 === 0 ? particleSecondary : particlePrimary;
      colors[offset] = color.r;
      colors[offset + 1] = color.g;
      colors[offset + 2] = color.b;
    }
    const particleGeometry = new BufferGeometry();
    particleGeometry.setAttribute("position", new BufferAttribute(positions, 3));
    particleGeometry.setAttribute("color", new BufferAttribute(colors, 3));
    const particleMaterial = new PointsMaterial({
      size: theme.scene.particleSize,
      transparent: true,
      opacity: theme.scene.particleOpacity,
      sizeAttenuation: true,
      vertexColors: true,
    });
    const particles = new Points(particleGeometry, particleMaterial);
    scene.add(particles);

    const rails = new Group();
    const railGeometries: BufferGeometry[] = [];
    const railMaterial = new LineBasicMaterial({
      color: theme.scene.rails,
      transparent: true,
      opacity: theme.scene.railOpacity,
    });
    for (let index = 0; index < theme.scene.railCount; index += 1) {
      const geometry = new BufferGeometry().setFromPoints(railPoints(index, theme.scene));
      railGeometries.push(geometry);
      rails.add(new Line(geometry, railMaterial));
    }
    scene.add(rails);

    const motif = createSceneMotif(theme.scene, densityScale);
    scene.add(motif.group);

    let pointerX = 0;
    let pointerY = 0;
    const onPointerMove = (event: PointerEvent) => {
      pointerX = event.clientX / window.innerWidth - 0.5;
      pointerY = event.clientY / window.innerHeight - 0.5;
    };
    window.addEventListener("pointermove", onPointerMove, { passive: true });

    const resize = () => {
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      renderer.setSize(width, height, false);
      camera.aspect = width / Math.max(height, 1);
      camera.updateProjectionMatrix();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    resize();

    const startedAt = performance.now();
    const render = (timestamp = performance.now()) => {
      const elapsed = (timestamp - startedAt) / 1000;
      particles.rotation.y = reducedMotion ? 0 : elapsed * theme.scene.driftSpeed;
      particles.position.y =
        reducedMotion || theme.scene.profile !== "deimos"
          ? 0
          : Math.sin(elapsed * 0.16) * 0.08;
      rails.position.x = reducedMotion
        ? 0
        : Math.sin(elapsed * 0.09) * theme.scene.railAmplitude;
      motif.update(elapsed);
      camera.position.x += (pointerX * 0.22 - camera.position.x) * 0.02;
      camera.position.y += (-pointerY * 0.14 - camera.position.y) * 0.02;
      camera.lookAt(0, 0, 0);
      renderer.render(scene, camera);
    };
    if (reducedMotion) {
      render();
    } else {
      renderer.setAnimationLoop(render);
    }

    const onVisibilityChange = () => {
      if (reducedMotion) return;
      renderer.setAnimationLoop(document.hidden ? null : render);
    };
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      renderer.setAnimationLoop(null);
      observer.disconnect();
      window.removeEventListener("pointermove", onPointerMove);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      particleGeometry.dispose();
      particleMaterial.dispose();
      railGeometries.forEach((geometry) => geometry.dispose());
      railMaterial.dispose();
      motif.dispose();
      renderer.dispose();
    };
  }, [theme]);

  return <canvas className="archive-scene" ref={canvasRef} aria-hidden="true" />;
}

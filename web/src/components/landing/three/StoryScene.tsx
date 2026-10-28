"use client";

import { Environment, Float, Lightformer } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import type { MotionValue } from "motion/react";
import { useRef } from "react";
import * as THREE from "three";
import { Headphones, Laptop, Smartphone, TShirt } from "./models";

export const STEPS = 5; // 0 hero · 1-4 products · 5 outro

type Pose = { cluster: [number, number, number]; clusterScale: number; focusScale: number; tilt: [number, number] };

// Index i + 1 is the scroll step at which product i is in focus.
const PRODUCTS: { Model: () => React.JSX.Element; pose: Pose }[] = [
  { Model: Headphones, pose: { cluster: [0.75, 0.85, 0], clusterScale: 0.48, focusScale: 0.78, tilt: [0.15, -0.5] } },
  { Model: Smartphone, pose: { cluster: [2.15, -0.05, 0.3], clusterScale: 0.5, focusScale: 0.9, tilt: [0.05, -0.35] } },
  { Model: Laptop, pose: { cluster: [0.85, -0.95, -0.4], clusterScale: 0.38, focusScale: 0.62, tilt: [0.4, -0.55] } },
  { Model: TShirt, pose: { cluster: [2.3, 1.15, -0.8], clusterScale: 0.36, focusScale: 0.8, tilt: [0.05, -0.3] } },
];

const smooth = (x: number) => {
  const t = Math.min(1, Math.max(0, x));
  return t * t * (3 - 2 * t);
};

function Product({ index, progress, compact }: { index: number; progress: MotionValue<number>; compact: boolean }) {
  const ref = useRef<THREE.Group>(null);
  const { Model, pose } = PRODUCTS[index];
  const step = index + 1;

  useFrame((state, dt) => {
    const g = ref.current;
    if (!g) return;
    const s = progress.get() * STEPS;
    const focus = smooth(1 - Math.abs(s - step));
    let other = 0;
    PRODUCTS.forEach((_, j) => {
      if (j !== index) other = Math.max(other, smooth(1 - Math.abs(s - (j + 1))));
    });

    // On phones the visible area is narrow and the text takes the lower half, so products
    // sit smaller in the band above it (y between ~0.4 and ~1.6 at this camera distance).
    const [cx, cy, cz] = compact
      ? [(pose.cluster[0] - 1.5) * 0.62, pose.cluster[1] * 0.55 + 1.0, pose.cluster[2]]
      : pose.cluster;
    const [fx, fy] = compact ? [0, 1.0] : [1.4, 0];
    const clusterScale = pose.clusterScale * (compact ? 0.6 : 1);
    const focusScale = pose.focusScale * (compact ? 0.55 : 1);

    // Cluster -> parked (shrunk away) while another product is in focus -> focus position.
    const tx = THREE.MathUtils.lerp(THREE.MathUtils.lerp(cx, cx * 1.6, other), fx, focus);
    const ty = THREE.MathUtils.lerp(THREE.MathUtils.lerp(cy, cy * 1.6, other), fy, focus);
    const tz = THREE.MathUtils.lerp(THREE.MathUtils.lerp(cz, cz - 4, other), 0.6, focus);
    const ts = THREE.MathUtils.lerp(THREE.MathUtils.lerp(clusterScale, 0.0001, other), focusScale, focus);

    const t = state.clock.elapsedTime;
    const idle = Math.sin(t * 0.4 + index) * 0.25;
    // While in focus the product turns with the scroll, like a turntable under your thumb.
    const ry = pose.tilt[1] + idle * (1 - focus) + focus * (s - step) * 1.6;
    const rx = pose.tilt[0] + Math.sin(t * 0.5 + index * 2) * 0.05 * (1 - focus);

    const k = 6;
    g.position.set(
      THREE.MathUtils.damp(g.position.x, tx, k, dt),
      THREE.MathUtils.damp(g.position.y, ty, k, dt),
      THREE.MathUtils.damp(g.position.z, tz, k, dt),
    );
    g.scale.setScalar(THREE.MathUtils.damp(g.scale.x, ts, k, dt));
    g.rotation.y = THREE.MathUtils.damp(g.rotation.y, ry, k, dt);
    g.rotation.x = THREE.MathUtils.damp(g.rotation.x, rx, k, dt);
    g.visible = g.scale.x > 0.01;
  });

  return (
    <group ref={ref} scale={0.0001}>
      <Float speed={1.2} rotationIntensity={0} floatIntensity={0.35}>
        <Model />
      </Float>
    </group>
  );
}

export default function StoryScene({ progress, compact, active }: { progress: MotionValue<number>; compact: boolean; active: boolean }) {
  return (
    <Canvas
      dpr={[1, compact ? 1.5 : 1.75]}
      camera={{ position: [0, 0, 6.2], fov: 35 }}
      frameloop={active ? "always" : "never"}
      gl={{ antialias: true, powerPreference: "high-performance" }}
      aria-hidden="true"
    >
      <ambientLight intensity={0.25} />
      <directionalLight position={[4, 5, 6]} intensity={1.6} />
      <directionalLight position={[-5, -2, 3]} intensity={0.35} />
      {/* Studio lighting from soft area lights; no downloaded HDR images. */}
      <Environment resolution={256}>
        <Lightformer intensity={2.2} position={[0, 4, 4]} scale={[8, 2, 1]} />
        <Lightformer intensity={1.2} position={[-5, 1, 2]} scale={[2, 6, 1]} />
        <Lightformer intensity={1.2} position={[5, 1, 2]} scale={[2, 6, 1]} />
        <Lightformer intensity={0.6} position={[0, -4, 3]} scale={[8, 1, 1]} />
      </Environment>
      {PRODUCTS.map((_, i) => (
        <Product key={i} index={i} progress={progress} compact={compact} />
      ))}
    </Canvas>
  );
}

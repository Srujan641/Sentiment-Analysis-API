"use client";

// Product models built from geometry primitives: no downloaded assets, no licensing.
import { RoundedBox } from "@react-three/drei";
import { useMemo } from "react";
import * as THREE from "three";

/* ------------------------------------------------------------------ shared */
function useScreenTexture(draw: (ctx: CanvasRenderingContext2D, w: number, h: number) => void, w: number, h: number) {
  return useMemo(() => {
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d")!;
    draw(ctx, w, h);
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 4;
    return tex;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [w, h]);
}

const INK = "#e8e8ea";
const MUTED = "#8a8a92";
const POS = "#4ade80";
const NEG = "#f87171";

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
}

/* ------------------------------------------------------------------ headphones */
export function Headphones() {
  const band = useMemo(() => new THREE.TorusGeometry(1, 0.075, 20, 96, Math.PI), []);
  const pad = useMemo(() => new THREE.TorusGeometry(0.93, 0.06, 16, 80, Math.PI * 0.7), []);
  // Ear cup: a lathe profile gives a soft, rounded shell.
  const cup = useMemo(() => {
    const pts = [
      new THREE.Vector2(0, -0.2),
      new THREE.Vector2(0.36, -0.2),
      new THREE.Vector2(0.47, -0.12),
      new THREE.Vector2(0.5, 0),
      new THREE.Vector2(0.47, 0.12),
      new THREE.Vector2(0.36, 0.2),
      new THREE.Vector2(0, 0.2),
    ];
    return new THREE.LatheGeometry(pts, 64);
  }, []);
  const cushion = useMemo(() => new THREE.TorusGeometry(0.34, 0.12, 20, 64), []);

  const shell = <meshPhysicalMaterial color="#c9c9cc" metalness={0.55} roughness={0.32} clearcoat={0.6} clearcoatRoughness={0.25} />;
  const fabric = <meshStandardMaterial color="#2a2a2e" roughness={0.95} />;
  const metal = <meshStandardMaterial color="#d6d6da" metalness={1} roughness={0.22} />;

  return (
    <group>
      <mesh geometry={band}>{metal}</mesh>
      <mesh geometry={pad} rotation={[0, 0, Math.PI * 0.15]} position={[0, -0.05, 0]}>
        {fabric}
      </mesh>
      {[-1, 1].map((side) => (
        <group key={side} position={[side * 1.0, -0.62, 0]}>
          {/* arm from band to cup */}
          <mesh position={[0, 0.36, 0]}>
            <cylinderGeometry args={[0.035, 0.035, 0.55, 16]} />
            {metal}
          </mesh>
          <group rotation={[0, 0, Math.PI / 2]}>
            <mesh geometry={cup} scale={[1, 0.9, 1.15]}>
              {shell}
            </mesh>
            <mesh geometry={cushion} rotation={[Math.PI / 2, 0, 0]} position={[0, side * -0.22, 0]} scale={[1, 1.15, 1]}>
              {fabric}
            </mesh>
          </group>
        </group>
      ))}
    </group>
  );
}

/* ------------------------------------------------------------------ smartphone */
export function Smartphone() {
  const screen = useScreenTexture(
    (ctx, w, h) => {
      ctx.fillStyle = "#0e0e10";
      ctx.fillRect(0, 0, w, h);
      ctx.fillStyle = INK;
      ctx.font = "600 34px Inter, system-ui, sans-serif";
      ctx.fillText("Reviews", 40, 110);
      ctx.fillStyle = MUTED;
      ctx.font = "24px Inter, system-ui, sans-serif";
      ctx.fillText("What to fix first", 40, 150);
      const rows: [string, number, string][] = [
        ["Heats up while gaming", 0.82, NEG],
        ["Camera in low light", 0.58, NEG],
        ["Charger in the box", 0.36, NEG],
        ["Display brightness", 0.74, POS],
      ];
      rows.forEach(([label, v, color], i) => {
        const y = 220 + i * 120;
        ctx.fillStyle = INK;
        ctx.font = "500 26px Inter, system-ui, sans-serif";
        ctx.fillText(label, 40, y);
        ctx.fillStyle = "#26262b";
        roundRect(ctx, 40, y + 22, w - 80, 14, 7);
        ctx.fill();
        ctx.fillStyle = color;
        roundRect(ctx, 40, y + 22, (w - 80) * v, 14, 7);
        ctx.fill();
      });
    },
    512,
    1040,
  );

  return (
    <group>
      <RoundedBox args={[0.92, 1.9, 0.09]} radius={0.075} smoothness={6}>
        <meshPhysicalMaterial color="#1b1b1f" metalness={0.6} roughness={0.25} clearcoat={1} clearcoatRoughness={0.08} />
      </RoundedBox>
      <mesh position={[0, 0, 0.0465]}>
        <planeGeometry args={[0.84, 1.8]} />
        <meshPhysicalMaterial map={screen} emissive="#ffffff" emissiveMap={screen} emissiveIntensity={0.55} roughness={0.08} clearcoat={1} />
      </mesh>
      {/* camera bump */}
      <group position={[-0.22, 0.68, -0.05]}>
        <RoundedBox args={[0.36, 0.36, 0.035]} radius={0.06} smoothness={4}>
          <meshPhysicalMaterial color="#2a2a30" metalness={0.5} roughness={0.3} clearcoat={1} />
        </RoundedBox>
        {[
          [-0.08, 0.08],
          [0.08, 0.08],
          [-0.08, -0.08],
        ].map(([x, y]) => (
          <mesh key={`${x}${y}`} position={[x, y, -0.02]} rotation={[Math.PI / 2, 0, 0]}>
            <cylinderGeometry args={[0.055, 0.055, 0.03, 32]} />
            <meshPhysicalMaterial color="#0a0a0c" metalness={0.9} roughness={0.1} clearcoat={1} />
          </mesh>
        ))}
      </group>
    </group>
  );
}

/* ------------------------------------------------------------------ laptop */
export function Laptop() {
  const screen = useScreenTexture(
    (ctx, w, h) => {
      ctx.fillStyle = "#0e0e10";
      ctx.fillRect(0, 0, w, h);
      ctx.fillStyle = INK;
      ctx.font = "600 30px Inter, system-ui, sans-serif";
      ctx.fillText("Insights · Laptop 14", 36, 64);
      // weekly complaint chart
      ctx.strokeStyle = "#2a2a30";
      ctx.lineWidth = 2;
      for (let i = 0; i < 4; i++) {
        ctx.beginPath();
        ctx.moveTo(36, 140 + i * 60);
        ctx.lineTo(w - 36, 140 + i * 60);
        ctx.stroke();
      }
      const pts = [0.62, 0.66, 0.6, 0.7, 0.68, 0.72, 0.4, 0.34, 0.3, 0.28, 0.3, 0.26];
      ctx.strokeStyle = INK;
      ctx.lineWidth = 4;
      ctx.beginPath();
      pts.forEach((v, i) => {
        const x = 36 + (i * (w - 72)) / (pts.length - 1);
        const y = 320 - v * 220;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
      ctx.setLineDash([8, 10]);
      ctx.strokeStyle = MUTED;
      ctx.lineWidth = 2;
      const cx = 36 + (5.5 * (w - 72)) / (pts.length - 1);
      ctx.beginPath();
      ctx.moveTo(cx, 110);
      ctx.lineTo(cx, 330);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = POS;
      roundRect(ctx, 36, 370, 250, 46, 10);
      ctx.fill();
      ctx.fillStyle = "#0e0e10";
      ctx.font = "600 24px Inter, system-ui, sans-serif";
      ctx.fillText("Fan noise −41%", 52, 401);
    },
    1024,
    640,
  );

  return (
    <group>
      {/* base */}
      <RoundedBox args={[2.3, 0.07, 1.55]} radius={0.035} smoothness={4} position={[0, 0, 0]}>
        <meshStandardMaterial color="#b9bcc2" metalness={0.85} roughness={0.32} />
      </RoundedBox>
      <mesh position={[0, 0.037, -0.12]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[1.95, 0.8]} />
        <meshStandardMaterial color="#1c1c20" roughness={0.6} />
      </mesh>
      <mesh position={[0, 0.037, 0.5]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[0.8, 0.42]} />
        <meshStandardMaterial color="#a9acb2" metalness={0.8} roughness={0.25} />
      </mesh>
      {/* lid, hinged at the back edge */}
      <group position={[0, 0.035, -0.77]} rotation={[-0.22, 0, 0]}>
        <RoundedBox args={[2.3, 1.48, 0.045]} radius={0.03} smoothness={4} position={[0, 0.74, 0]}>
          <meshStandardMaterial color="#b9bcc2" metalness={0.85} roughness={0.32} />
        </RoundedBox>
        <mesh position={[0, 0.76, 0.024]}>
          <planeGeometry args={[2.16, 1.32]} />
          <meshPhysicalMaterial map={screen} emissive="#ffffff" emissiveMap={screen} emissiveIntensity={0.5} roughness={0.15} clearcoat={0.6} />
        </mesh>
      </group>
    </group>
  );
}

/* ------------------------------------------------------------------ t-shirt */
export function TShirt() {
  const body = useMemo(() => {
    const s = new THREE.Shape();
    s.moveTo(-0.38, 0.95); // neck left
    s.quadraticCurveTo(0, 0.72, 0.38, 0.95); // neckline
    s.lineTo(0.78, 0.86); // shoulder
    s.lineTo(1.25, 0.42); // sleeve top
    s.lineTo(1.0, 0.15); // sleeve end
    s.lineTo(0.72, 0.36); // armpit
    s.lineTo(0.7, -0.98); // hem right
    s.quadraticCurveTo(0, -1.04, -0.7, -0.98); // hem
    s.lineTo(-0.72, 0.36);
    s.lineTo(-1.0, 0.15);
    s.lineTo(-1.25, 0.42);
    s.lineTo(-0.78, 0.86);
    s.closePath();
    const g = new THREE.ExtrudeGeometry(s, {
      depth: 0.12,
      bevelEnabled: true,
      bevelThickness: 0.06,
      bevelSize: 0.05,
      bevelSegments: 6,
      curveSegments: 24,
    });
    g.center();
    return g;
  }, []);
  const collar = useMemo(() => new THREE.TorusGeometry(0.4, 0.035, 12, 48, Math.PI), []);

  return (
    <group>
      <mesh geometry={body}>
        <meshPhysicalMaterial color="#3d5a80" roughness={0.9} sheen={1} sheenColor="#8fb3e0" sheenRoughness={0.6} />
      </mesh>
      <mesh geometry={collar} position={[0, 0.98, 0.07]} rotation={[0, 0, Math.PI]} scale={[0.95, 0.6, 1]}>
        <meshStandardMaterial color="#2f4866" roughness={0.9} />
      </mesh>
    </group>
  );
}

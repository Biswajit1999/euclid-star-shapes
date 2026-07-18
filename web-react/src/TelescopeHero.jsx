import { useEffect, useRef, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';

function useReducedMotion() {
  const [reduced, setReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(query.matches);
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);

  return reduced;
}

function FrameClock({ active }) {
  const invalidate = useThree((state) => state.invalidate);

  useEffect(() => {
    invalidate();
    if (!active) return undefined;
    const frame = window.setInterval(invalidate, 1000 / 24);
    return () => window.clearInterval(frame);
  }, [active, invalidate]);

  return null;
}

function SolarPanel() {
  const cells = [];
  for (let row = 0; row < 3; row += 1) {
    for (let column = 0; column < 5; column += 1) {
      cells.push(
        <mesh key={`${row}-${column}`} position={[-2.02 + column * 0.36, -0.52, -0.43 + row * 0.38]}>
          <boxGeometry args={[0.32, 0.035, 0.34]} />
          <meshStandardMaterial color="#332264" metalness={0.55} roughness={0.38} />
        </mesh>,
      );
    }
  }
  return <group>{cells}</group>;
}

function EuclidOptics({ animate }) {
  const model = useRef(null);

  useFrame(({ clock }) => {
    if (!model.current || !animate) return;
    const elapsed = clock.getElapsedTime();
    model.current.rotation.y = -0.35 + elapsed * 0.11;
    model.current.position.y = Math.sin(elapsed * 0.7) * 0.08;
  });

  return (
    <group ref={model} rotation={[0.15, -0.35, -0.08]} scale={0.92}>
      <mesh position={[0.35, -0.22, 0]}>
        <boxGeometry args={[1.35, 1.15, 1.25]} />
        <meshStandardMaterial color="#d9d8e5" metalness={0.44} roughness={0.5} />
      </mesh>
      <mesh position={[0.35, -0.83, 0]}>
        <boxGeometry args={[1.48, 0.08, 1.38]} />
        <meshStandardMaterial color="#9c7845" metalness={0.65} roughness={0.34} />
      </mesh>
      <group position={[0.62, 0.82, 0]} rotation={[0, 0, -0.13]}>
        <mesh>
          <cylinderGeometry args={[0.47, 0.62, 1.55, 18]} />
          <meshStandardMaterial color="#312553" metalness={0.48} roughness={0.36} />
        </mesh>
        <mesh position={[0, 0.78, 0]}>
          <cylinderGeometry args={[0.49, 0.49, 0.08, 24]} />
          <meshStandardMaterial color="#b79765" metalness={0.82} roughness={0.22} />
        </mesh>
        <mesh position={[0, 0.835, 0]}>
          <torusGeometry args={[0.39, 0.035, 8, 24]} />
          <meshStandardMaterial color="#ded5bd" metalness={0.72} roughness={0.25} />
        </mesh>
        <mesh position={[0, -0.48, 0]}>
          <torusGeometry args={[0.55, 0.045, 8, 24]} />
          <meshStandardMaterial color="#8472a9" metalness={0.62} roughness={0.3} />
        </mesh>
      </group>
      <mesh position={[-0.5, -0.5, 0]}>
        <boxGeometry args={[0.48, 0.07, 0.08]} />
        <meshStandardMaterial color="#aaa5ba" metalness={0.65} roughness={0.3} />
      </mesh>
      <SolarPanel />
      <mesh position={[-1.13, -0.22, 0]}>
        <boxGeometry args={[0.22, 0.16, 0.22]} />
        <meshStandardMaterial color="#74678f" metalness={0.58} roughness={0.32} />
      </mesh>
    </group>
  );
}

export default function TelescopeHero() {
  const reducedMotion = useReducedMotion();

  return (
    <div className="hero-canvas-wrap" role="img" aria-label="Procedural low-poly illustration of a Euclid-like space telescope">
      <Canvas
        camera={{ position: [4.7, 2.7, 5.4], fov: 38 }}
        dpr={[1, 1.4]}
        frameloop="demand"
        gl={{ antialias: true, alpha: true, powerPreference: 'low-power' }}
      >
        <ambientLight intensity={1.5} />
        <directionalLight position={[4, 5, 4]} intensity={2.7} color="#f3edff" />
        <pointLight position={[-4, -1, 3]} intensity={14} color="#8060db" />
        <EuclidOptics animate={!reducedMotion} />
        <FrameClock active={!reducedMotion} />
      </Canvas>
    </div>
  );
}

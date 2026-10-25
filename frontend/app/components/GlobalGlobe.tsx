'use client';

import { useEffect, useRef, useState } from 'react';
import Globe from 'react-globe.gl';

type GlobePoint = {
  lat: number;
  lng: number;
  label: string;
  value?: number;
};

type GlobalGlobeProps = {
  points?: GlobePoint[];
  onPointClick?: (point: GlobePoint) => void;
};

export default function GlobalGlobe({
  points = [],
  onPointClick,
}: GlobalGlobeProps) {
  const globeRef = useRef<any>(null);
  const [dimensions, setDimensions] = useState({ width: 640, height: 520 });

  useEffect(() => {
    const resize = () => {
      setDimensions({
        width: Math.max(300, window.innerWidth - (window.innerWidth > 700 ? 48 : 24)),
        height: Math.max(360, window.innerHeight - 180),
      });
    };

    resize();
    window.addEventListener('resize', resize);

    const timer = window.setTimeout(() => {
      const controls = globeRef.current?.controls();
      if (controls) {
        controls.autoRotate = true;
        controls.autoRotateSpeed = 0.35;
        controls.enableDamping = true;
        controls.dampingFactor = 0.08;
      }

      globeRef.current?.pointOfView({ lat: 28, lng: -12, altitude: 2.25 }, 1000);
    }, 500);

    return () => {
      window.removeEventListener('resize', resize);
      window.clearTimeout(timer);
    };
  }, []);

  return (
    <div className="global-globe-stage">
      <div className="global-globe-halo" />
      <Globe
        ref={globeRef}
        width={dimensions.width}
        height={dimensions.height}
        backgroundColor="rgba(0,0,0,0)"
        globeImageUrl="//unpkg.com/three-globe/example/img/earth-blue-marble.jpg"
        bumpImageUrl="//unpkg.com/three-globe/example/img/earth-topology.png"
        backgroundImageUrl="//unpkg.com/three-globe/example/img/night-sky.png"
        showAtmosphere
        atmosphereColor="#55dca1"
        atmosphereAltitude={0.16}
        pointsData={points}
        pointLat="lat"
        pointLng="lng"
        pointLabel="label"
        pointColor={() => '#9dfc8b'}
        pointAltitude={0.025}
        pointRadius={0.45}
        onPointClick={(point: object) => onPointClick?.(point as GlobePoint)}
        animateIn
      />
      <div className="global-globe-caption">
        <span className="global-live-dot" />
        EARTH OBSERVATION
      </div>
    </div>
  );
}

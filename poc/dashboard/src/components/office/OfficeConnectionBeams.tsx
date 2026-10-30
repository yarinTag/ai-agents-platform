import type { useOfficeCanvas } from './useOfficeCanvas';

export function OfficeConnectionBeams({ model }: { model: ReturnType<typeof useOfficeCanvas> }) {
  const {
    lastDispatchedDept, brainPos, DEPARTMENTS, getDeptStats,
  } = model;
  return (<>
{/* SVG Interconnecting Walkways & Real-Time Animated Particle Beams */}
        <svg
          style={{
            position: 'absolute',
            inset: 0,
            width: '100%',
            height: '100%',
            overflow: 'visible',
            pointerEvents: 'none',
          }}
        >
          <defs>
            <filter id="walkway-shadow" x="-10%" y="-10%" width="120%" height="120%">
              <feDropShadow dx="0" dy="6" stdDeviation="4" floodColor="#000000" floodOpacity="0.08" />
            </filter>
            <linearGradient id="brainPulseGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#059669" stopOpacity="0.2" />
            </linearGradient>
          </defs>

          {/* Isometric Walkways connecting Brain to Department Platforms */}
          {DEPARTMENTS.map((dept) => {
            const stats = getDeptStats(dept.key);
            const isDeptActive = stats.doing > 0 || lastDispatchedDept === dept.key;

            return (
              <g key={`bridge-${dept.key}`}>
                {/* Wide Walkway shadow */}
                <line
                  x1={brainPos.x}
                  y1={brainPos.y + 4}
                  x2={dept.posX}
                  y2={dept.posY + 4}
                  stroke="#d6d3c8"
                  strokeWidth="18"
                  strokeLinecap="round"
                />
                {/* Walkway body */}
                <line
                  x1={brainPos.x}
                  y1={brainPos.y}
                  x2={dept.posX}
                  y2={dept.posY}
                  stroke={isDeptActive ? '#dcfce7' : '#eae7dd'}
                  strokeWidth="16"
                  strokeLinecap="round"
                />
                {/* Walkway center guide rail */}
                <line
                  x1={brainPos.x}
                  y1={brainPos.y}
                  x2={dept.posX}
                  y2={dept.posY}
                  stroke={isDeptActive ? '#10b981' : '#d1cebf'}
                  strokeWidth="1.5"
                  strokeDasharray={isDeptActive ? '6 6' : '4 4'}
                />

                {/* Animated Glowing Signal Dotted Stream (Only when active) */}
                {isDeptActive && (
                  <line
                    x1={brainPos.x}
                    y1={brainPos.y}
                    x2={dept.posX}
                    y2={dept.posY}
                    stroke={dept.dotColor}
                    strokeWidth="3"
                    strokeDasharray="6 8"
                    strokeOpacity={1}
                  >
                    <animate
                      attributeName="stroke-dashoffset"
                      from="28"
                      to="0"
                      dur="0.9s"
                      repeatCount="indefinite"
                    />
                  </line>
                )}

                {/* Dynamic Energy Particle Packet Moving Along Corridor When Active */}
                {isDeptActive && (
                  <circle r="5" fill={dept.dotColor}>
                    <animateMotion
                      path={`M ${dept.posX} ${dept.posY} L ${brainPos.x} ${brainPos.y}`}
                      dur="1.3s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}
              </g>
            );
          })}
        </svg>
  </>);
}

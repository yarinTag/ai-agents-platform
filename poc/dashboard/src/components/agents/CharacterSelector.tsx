import React, { useRef, useEffect } from 'react';
import { Card, Tag } from 'antd';

export interface CharacterPreset {
  id: string;
  name: string;
  role: string;
  department: string;
  shirtColor: string;
  hairColor: string;
  hasCrown?: boolean;
  hasStar?: boolean;
  hasHeadphones?: boolean;
  description: string;
}

export const CHARACTER_PRESETS: CharacterPreset[] = [
  {
    id: 'executive',
    name: 'Executive Lead',
    role: 'ROOT_ORCHESTRATOR',
    department: 'HQ',
    shirtColor: '#8b5cf6',
    hairColor: '#f59e0b',
    hasCrown: true,
    description: 'Autonomous enterprise orchestrator with executive authority',
  },
  {
    id: 'manager',
    name: 'Team Manager',
    role: 'MANAGER',
    department: 'Engineering',
    shirtColor: '#f59e0b',
    hairColor: '#475569',
    hasStar: true,
    description: 'Coordinates subtasks, enforces concurrency and aggregates outcomes',
  },
  {
    id: 'frontend_dev',
    name: 'UI / Frontend Engineer',
    role: 'WORKER',
    department: 'Engineering',
    shirtColor: '#06b6d4',
    hairColor: '#92400e',
    hasHeadphones: true,
    description: 'React, TypeScript, Canvas and responsive UI specialist',
  },
  {
    id: 'backend_dev',
    name: 'Backend & Systems Dev',
    role: 'WORKER',
    department: 'Engineering',
    shirtColor: '#10b981',
    hairColor: '#1e293b',
    description: 'Python, FastAPI, SQLite and streaming architecture expert',
  },
  {
    id: 'qa_auditor',
    name: 'QA & Security Auditor',
    role: 'SPECIALIST',
    department: 'QA & Testing',
    shirtColor: '#e11d48',
    hairColor: '#334155',
    description: 'Regression tests, OWASP vulnerability scanner and code auditor',
  },
  {
    id: 'researcher',
    name: 'AI Research Scientist',
    role: 'SPECIALIST',
    department: 'Research & Ops',
    shirtColor: '#d946ef',
    hairColor: '#78350f',
    description: 'Prompt evaluation, model selection and benchmark analysis',
  },
];

interface CharacterSelectorProps {
  value?: string;
  onChange?: (val: string) => void;
}

export const CharacterSelector: React.FC<CharacterSelectorProps> = ({
  value = 'frontend_dev',
  onChange,
}) => {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
      {CHARACTER_PRESETS.map((preset) => {
        const isSelected = value === preset.id;
        return (
          <Card
            key={preset.id}
            size="small"
            hoverable
            onClick={() => onChange?.(preset.id)}
            style={{
              background: isSelected ? 'rgba(56, 189, 248, 0.1)' : '#1e293b',
              border: isSelected ? '2px solid #38bdf8' : '1px solid #334155',
              borderRadius: '10px',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', textAlign: 'center' }}>
              {/* Mini Pixel Avatar Canvas */}
              <PixelAvatarPreview preset={preset} isSelected={isSelected} />

              <div>
                <div style={{ fontWeight: 700, fontSize: '12px', color: '#f8fafc' }}>
                  {preset.name}
                </div>
                <Tag
                  color={
                    preset.role === 'ROOT_ORCHESTRATOR'
                      ? 'purple'
                      : preset.role === 'MANAGER'
                      ? 'gold'
                      : preset.role === 'SPECIALIST'
                      ? 'magenta'
                      : 'cyan'
                  }
                  style={{ fontSize: '9px', marginTop: '4px' }}
                >
                  {preset.role}
                </Tag>
              </div>

              <div style={{ fontSize: '10px', color: '#94a3b8', lineHeight: '1.3' }}>
                {preset.description}
              </div>
            </div>
          </Card>
        );
      })}
    </div>
  );
};

const PixelAvatarPreview: React.FC<{ preset: CharacterPreset; isSelected: boolean }> = ({
  preset,
  isSelected,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let tick = 0;
    let animId: number;

    const render = () => {
      tick++;
      ctx.clearRect(0, 0, 48, 48);
      ctx.imageSmoothingEnabled = false;

      // Subtle breathing bob
      const bob = Math.sin(tick * 0.08) * 1.5;
      const cy = 20 + bob;

      // Shadow
      ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
      ctx.beginPath();
      ctx.ellipse(24, 40, 14, 5, 0, 0, Math.PI * 2);
      ctx.fill();

      // Body / Shirt
      ctx.fillStyle = preset.shirtColor;
      ctx.fillRect(16, cy + 8, 16, 12);

      // Head
      ctx.fillStyle = '#fde047'; // skin tone
      ctx.fillRect(18, cy, 12, 10);

      // Hair
      ctx.fillStyle = preset.hairColor;
      ctx.fillRect(17, cy - 3, 14, 4);

      // Eyes
      ctx.fillStyle = '#0f172a';
      ctx.fillRect(20, cy + 3, 2, 2);
      ctx.fillRect(26, cy + 3, 2, 2);

      // Role accessories
      if (preset.hasCrown) {
        ctx.fillStyle = '#fbbf24';
        ctx.fillRect(17, cy - 6, 14, 3);
        ctx.fillRect(17, cy - 8, 3, 2);
        ctx.fillRect(23, cy - 9, 3, 3);
        ctx.fillRect(28, cy - 8, 3, 2);
      } else if (preset.hasStar) {
        ctx.fillStyle = '#f59e0b';
        ctx.font = 'bold 10px sans-serif';
        ctx.fillText('★', 20, cy - 4);
      } else if (preset.hasHeadphones) {
        ctx.fillStyle = '#e2e8f0';
        ctx.fillRect(16, cy + 1, 2, 6);
        ctx.fillRect(30, cy + 1, 2, 6);
        ctx.fillRect(18, cy - 4, 12, 1);
      }

      animId = requestAnimationFrame(render);
    };

    animId = requestAnimationFrame(render);
    return () => cancelAnimationFrame(animId);
  }, [preset]);

  return (
    <canvas
      ref={canvasRef}
      width={48}
      height={48}
      style={{
        display: 'block',
        background: isSelected ? '#0f172a' : '#111827',
        borderRadius: '50%',
        border: isSelected ? '2px solid #38bdf8' : '1px solid #334155',
      }}
    />
  );
};

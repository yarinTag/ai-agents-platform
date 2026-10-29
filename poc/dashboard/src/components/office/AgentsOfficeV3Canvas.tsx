import type { AgentsOfficeV3CanvasProps } from './officeCanvasTypes';
import React from 'react';

import { PlusOutlined, MinusOutlined, HomeOutlined, ThunderboltFilled } from '@ant-design/icons';

import { useOfficeCanvas } from './useOfficeCanvas';
import { OfficeDepartmentPlatforms } from './OfficeDepartmentPlatforms';
import { OfficeConnectionBeams } from './OfficeConnectionBeams';

export const AgentsOfficeV3Canvas: React.FC<AgentsOfficeV3CanvasProps> = (props) => {
  const model = useOfficeCanvas(props);
  const {
    agents, zoom, setZoom, pan, setPan,
    isDragging, brainPos, DEPARTMENTS, activeTaskAny, totalDoing,
    handleMouseDown, handleMouseMove, handleMouseUp, handleWheel,
  } = model;
  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        height: 'calc(100vh - 52px)',
        minHeight: '750px',
        backgroundColor: '#f7f6f2',
        overflow: 'hidden',
        userSelect: 'none',
        cursor: isDragging ? 'grabbing' : 'grab',
      }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onWheel={handleWheel}
    >

      {/* Zoom / Pan Container */}
      <div
        style={{
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
          transformOrigin: 'center center',
          transition: isDragging ? 'none' : 'transform 0.15s ease-out',
          width: '1280px',
          height: '1000px',
          margin: '0 auto',
          position: 'relative',
        }}
      >
        <OfficeConnectionBeams model={model} />

        <OfficeDepartmentPlatforms model={model} />

        {/* Empty State Banner if 0 Departments Defined */}
        {DEPARTMENTS.length === 0 && (
          <div
            style={{
              position: 'absolute',
              left: `${brainPos.x}px`,
              top: `${brainPos.y - 120}px`,
              transform: 'translateX(-50%)',
              background: '#ffffff',
              borderRadius: '16px',
              border: '1.5px dashed #cbd5e1',
              padding: '16px 24px',
              textAlign: 'center',
              boxShadow: '0 8px 24px rgba(0,0,0,0.06)',
              zIndex: 10,
              maxWidth: '380px',
            }}
          >
            <div style={{ fontSize: '13px', fontWeight: 800, color: '#1c1917', marginBottom: '4px' }}>
              🏢 NO DEPARTMENTS DEFINED
            </div>
            <div style={{ fontSize: '11px', color: '#64748b', lineHeight: '1.5' }}>
              Create an agent in the Agents page and assign a department name to construct your office suites.
            </div>
          </div>
        )}

        {/* Central Hub: CENTRAL DISPATCH */}
        <div
          style={{
            position: 'absolute',
            left: `${brainPos.x}px`,
            top: `${brainPos.y}px`,
            transform: 'translate(-50%, -50%)',
            zIndex: 5,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
          }}
        >
          {/* Hexagonal Central Platform */}
          <div
            style={{
              width: '130px',
              height: '90px',
              background: totalDoing > 0 ? '#ecfdf5' : '#f8fafc',
              borderRadius: '20px',
              border: totalDoing > 0 ? '2.5px solid #10b981' : '1.5px solid #cbd5e1',
              boxShadow: totalDoing > 0
                ? '0 0 35px rgba(16, 185, 129, 0.4), 0 12px 30px rgba(5, 150, 105, 0.25)'
                : '0 8px 24px rgba(0, 0, 0, 0.08)',
              transform: 'perspective(600px) rotateX(25deg)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative',
              transition: 'all 0.3s ease',
            }}
          >
            {/* Holographic Network Node in Center */}
            <div
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '50%',
                background: totalDoing > 0 ? 'rgba(16, 185, 129, 0.25)' : 'rgba(148, 163, 184, 0.15)',
                border: totalDoing > 0 ? '2px solid #10b981' : '1.5px dashed #94a3b8',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: totalDoing > 0 ? '0 0 20px #10b981' : 'none',
              }}
            >
              <ThunderboltFilled
                style={{
                  fontSize: '22px',
                  color: totalDoing > 0 ? '#10b981' : '#94a3b8',
                  animation: totalDoing > 0 ? 'spin 3s linear infinite' : 'none',
                }}
              />
            </div>
          </div>

          {/* Floating Pill: CENTRAL DISPATCH */}
          <div
            style={{
              position: 'absolute',
              top: '-32px',
              background: '#ffffff',
              border: totalDoing > 0 ? '1.5px solid #10b981' : '1.5px solid #e2e8f0',
              borderRadius: '20px',
              padding: '4px 14px',
              boxShadow: '0 8px 16px rgba(0,0,0,0.08)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              whiteSpace: 'nowrap',
            }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: totalDoing > 0 ? '#10b981' : '#94a3b8',
                boxShadow: totalDoing > 0 ? '0 0 8px #10b981' : 'none',
              }}
            />
            <span style={{ fontSize: '11px', fontWeight: 800, color: totalDoing > 0 ? '#065f46' : '#475569', letterSpacing: '0.5px' }}>
              CENTRAL DISPATCH
            </span>
            <span style={{ fontSize: '11px', fontWeight: 800, color: '#1c1917' }}>
              {totalDoing > 0 ? `${totalDoing} ACTIVE` : `${agents.length} AGENTS`}
            </span>
          </div>

          {/* Active Status Bubble */}
          <div
            style={{
              position: 'absolute',
              bottom: '-28px',
              background: totalDoing > 0 ? 'rgba(255, 255, 255, 0.98)' : 'rgba(248, 250, 252, 0.95)',
              border: totalDoing > 0 ? '1.5px solid #10b981' : '1px solid #cbd5e1',
              borderRadius: '12px',
              padding: '3px 12px',
              fontSize: '10px',
              fontWeight: 700,
              color: totalDoing > 0 ? '#059669' : '#64748b',
              boxShadow: totalDoing > 0 ? '0 4px 12px rgba(16, 185, 129, 0.18)' : '0 2px 6px rgba(0,0,0,0.05)',
              whiteSpace: 'nowrap',
              maxWidth: '240px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {activeTaskAny
              ? `⚡ ${((activeTaskAny.input_data as any)?.task || (activeTaskAny as any)?.prompt || 'EXECUTING MISSION').slice(0, 24)}...`
              : DEPARTMENTS.length === 0
              ? '💤 STANDBY • NO DEPARTMENTS'
              : `💤 STANDBY • ${DEPARTMENTS.length} DEPT${DEPARTMENTS.length === 1 ? '' : 'S'} READY`}
          </div>
        </div>
      </div>

      {/* Floating Zoom & Pan Controls (Bottom Right - Exactly like in screenshot) */}
      <div
        style={{
          position: 'absolute',
          bottom: '24px',
          right: '24px',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
          zIndex: 10,
        }}
      >
        <button
          onClick={() => setZoom((z) => Math.min(1.6, z + 0.1))}
          style={{
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            background: '#ffffff',
            border: '1px solid #e5e2d8',
            boxShadow: '0 4px 10px rgba(0,0,0,0.08)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '16px',
            color: '#44403c',
          }}
          title="Zoom In"
        >
          <PlusOutlined />
        </button>
        <button
          onClick={() => setZoom((z) => Math.max(0.6, z - 0.1))}
          style={{
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            background: '#ffffff',
            border: '1px solid #e5e2d8',
            boxShadow: '0 4px 10px rgba(0,0,0,0.08)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '16px',
            color: '#44403c',
          }}
          title="Zoom Out"
        >
          <MinusOutlined />
        </button>
        <button
          onClick={() => {
            setZoom(1);
            setPan({ x: 0, y: 0 });
          }}
          style={{
            width: '36px',
            height: '36px',
            borderRadius: '50%',
            background: '#ffffff',
            border: '1px solid #e5e2d8',
            boxShadow: '0 4px 10px rgba(0,0,0,0.08)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '15px',
            color: '#44403c',
          }}
          title="Reset View"
        >
          <HomeOutlined />
        </button>
      </div>
    </div>
  );
};

export default AgentsOfficeV3Canvas;

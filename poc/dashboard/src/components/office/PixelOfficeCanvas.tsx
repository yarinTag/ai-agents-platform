/**
 * PixelOfficeCanvas: React component embedding the PixelRenderer HTML5 Canvas.
 * Supports interactive dragging, zoom controls, agent selection, and real-time visual updates.
 */

import React, { useRef, useEffect } from 'react';
import { Button, Tooltip, Badge } from 'antd';
import {
  PlusOutlined,
  MinusOutlined,
  HomeOutlined,
  ThunderboltFilled,
  SyncOutlined,
} from '@ant-design/icons';
import { Agent } from '../../types/agent';
import { Task } from '../../types/task';
import { PixelRenderer } from '../../engine/PixelRenderer';
import { ConnectionStatus } from '../../services/eventStream';

interface PixelOfficeCanvasProps {
  agents: Agent[];
  tasks: Task[];
  connectionStatus?: ConnectionStatus;
  onSelectAgent: (agent: Agent) => void;
  onTaskCreated?: () => void;
}

export const PixelOfficeCanvas: React.FC<PixelOfficeCanvasProps> = ({
  agents,
  tasks,
  connectionStatus = 'connected',
  onSelectAgent,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<PixelRenderer | null>(null);

  const isDraggingRef = useRef<boolean>(false);
  const dragStartRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    // Initialize renderer
    const renderer = new PixelRenderer(canvas);
    rendererRef.current = renderer;

    const updateSize = () => {
      if (container && canvas) {
        renderer.resize(container.clientWidth, container.clientHeight);
      }
    };

    updateSize();
    window.addEventListener('resize', updateSize);

    renderer.setOnSelectAgent(onSelectAgent);
    renderer.updateData(agents, tasks);
    renderer.start();

    return () => {
      window.removeEventListener('resize', updateSize);
      renderer.stop();
    };
  }, []);

  // Synchronize dynamic agents & tasks on change
  useEffect(() => {
    if (rendererRef.current) {
      rendererRef.current.updateData(agents, tasks);
    }
  }, [agents, tasks]);

  // Mouse pan & zoom handlers
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button === 0) {
      isDraggingRef.current = true;
      dragStartRef.current = {
        x: e.clientX - (rendererRef.current?.panX || 0),
        y: e.clientY - (rendererRef.current?.panY || 0),
      };
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    if (isDraggingRef.current && rendererRef.current) {
      rendererRef.current.panX = e.clientX - dragStartRef.current.x;
      rendererRef.current.panY = e.clientY - dragStartRef.current.y;
    } else if (rendererRef.current) {
      rendererRef.current.handleCanvasMouseMove(mouseX, mouseY);
    }
  };

  const handleMouseUp = (e: React.MouseEvent) => {
    if (isDraggingRef.current) {
      const rect = canvasRef.current?.getBoundingClientRect();
      const dist = Math.hypot(
        e.clientX - (rendererRef.current?.panX || 0) - dragStartRef.current.x,
        e.clientY - (rendererRef.current?.panY || 0) - dragStartRef.current.y
      );

      // If drag distance was negligible, treat as click
      if (dist < 5 && rect && rendererRef.current) {
        rendererRef.current.handleCanvasClick(e.clientX - rect.left, e.clientY - rect.top);
      }
    }
    isDraggingRef.current = false;
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    if (!rendererRef.current) return;
    const zoomDelta = e.deltaY < 0 ? 0.1 : -0.1;
    rendererRef.current.zoom = Math.max(0.5, Math.min(2.5, rendererRef.current.zoom + zoomDelta));
  };

  const handleZoomIn = () => {
    if (rendererRef.current) {
      rendererRef.current.zoom = Math.min(2.5, rendererRef.current.zoom + 0.2);
    }
  };

  const handleZoomOut = () => {
    if (rendererRef.current) {
      rendererRef.current.zoom = Math.max(0.5, rendererRef.current.zoom - 0.2);
    }
  };

  const handleResetView = () => {
    if (rendererRef.current && containerRef.current) {
      rendererRef.current.zoom = 1.0;
      rendererRef.current.panX = containerRef.current.clientWidth / 2;
      rendererRef.current.panY = 160;
    }
  };

  const activeTaskCount = tasks.filter((t) => t.status === 'running').length;

  return (
    <div
      ref={containerRef}
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        userSelect: 'none',
        background: '#0f172a',
      }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onWheel={handleWheel}
    >
      <canvas
        ref={canvasRef}
        style={{
          display: 'block',
          width: '100%',
          height: '100%',
          cursor: isDraggingRef.current ? 'grabbing' : 'grab',
        }}
      />



      {/* View Navigation & Zoom Widget */}
      <div
        style={{
          position: 'absolute',
          bottom: '24px',
          left: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
          background: 'rgba(15, 23, 42, 0.85)',
          padding: '6px',
          borderRadius: '10px',
          border: '1px solid #334155',
          backdropFilter: 'blur(8px)',
          zIndex: 10,
        }}
      >
        <Tooltip title="Zoom In" placement="right">
          <Button
            type="text"
            icon={<PlusOutlined />}
            onClick={handleZoomIn}
            style={{ color: '#94a3b8', width: '32px', height: '32px' }}
          />
        </Tooltip>
        <Tooltip title="Zoom Out" placement="right">
          <Button
            type="text"
            icon={<MinusOutlined />}
            onClick={handleZoomOut}
            style={{ color: '#94a3b8', width: '32px', height: '32px' }}
          />
        </Tooltip>
        <Tooltip title="Reset View" placement="right">
          <Button
            type="text"
            icon={<HomeOutlined />}
            onClick={handleResetView}
            style={{ color: '#94a3b8', width: '32px', height: '32px' }}
          />
        </Tooltip>
      </div>

      {/* Instructions footer */}
      <div
        style={{
          position: 'absolute',
          bottom: '12px',
          right: '20px',
          color: '#64748b',
          fontSize: '11px',
          pointerEvents: 'none',
        }}
      >
        Drag to pan • Scroll to zoom • Click any agent to inspect & delegate
      </div>
    </div>
  );
};

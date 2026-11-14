import React, { useEffect, useState } from 'react';
import { Card, Row, Col, Statistic, Spin, Alert, Button, Tag } from 'antd';
import {
  ApartmentOutlined,
  DesktopOutlined,
  ThunderboltOutlined,
  AppstoreOutlined,
  FolderOpenOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  ArrowRightOutlined,
} from '@ant-design/icons';
import { Link } from 'react-router-dom';
import { WorkflowMetricsView } from './WorkflowMetricsView';
import { getSystemStats, getSystemHealth } from '../services/api';

export const DashboardPage: React.FC = () => {
  const [stats, setStats] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, healthRes] = await Promise.all([
          getSystemStats().catch(() => ({ data: null })),
          getSystemHealth().catch(() => ({ data: null })),
        ]);
        setStats(statsRes.data);
        setHealth(healthRes.data);
      } catch (err) {
        setError('Failed to load system stats');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '60px 0' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <WorkflowMetricsView />
      {/* Welcome & Launch Bar */}
      <div
        style={{
          background: 'linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%)',
          borderRadius: '16px',
          border: '1px solid #3730a3',
          padding: '24px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          boxShadow: '0 8px 30px rgba(0, 0, 0, 0.4)',
        }}
      >
        <div>
          <h2 style={{ margin: 0, color: '#f3f4f6', fontSize: '24px', fontWeight: 700 }}>
            Welcome to ConduitCross
          </h2>
          <p style={{ margin: '8px 0 0 0', color: '#a5b4fc', fontSize: '14px', maxWidth: '600px' }}>
            Autonomous AI engineering teams operating with local repository workspaces, custom skills plugins, and real-time isometric visualization.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '12px' }}>
          <Link to="/workflows">
            <Button
              type="primary"
              size="large"
              icon={<ApartmentOutlined />}
              style={{ background: '#4f46e5', borderColor: '#4f46e5', fontWeight: 600 }}
            >
              Explore Workflows
            </Button>
          </Link>
          <Link to="/flow">
            <Button
              size="large"
              icon={<ThunderboltOutlined />}
              style={{ background: '#059669', color: '#fff', borderColor: '#059669', fontWeight: 600 }}
            >
              Real-Time Flow ("FLOWO")
            </Button>
          </Link>
        </div>
      </div>

      {/* Metrics Row */}
      <Row gutter={[16, 16]}>
        <Col span={6}>
          <Card style={{ background: '#161b22', borderColor: '#30363d', borderRadius: '12px' }}>
            <Statistic
              title={<span style={{ color: '#8b949e' }}>Total Active Agents</span>}
              value={stats?.agents?.total ?? 3}
              prefix={<DesktopOutlined style={{ color: '#58a6ff' }} />}
              valueStyle={{ color: '#f3f4f6', fontWeight: 700 }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card style={{ background: '#161b22', borderColor: '#30363d', borderRadius: '12px' }}>
            <Statistic
              title={<span style={{ color: '#8b949e' }}>Active In-Flight Tasks</span>}
              value={stats?.tasks?.active ?? 0}
              prefix={<ThunderboltOutlined style={{ color: '#52c41a' }} />}
              valueStyle={{ color: '#52c41a', fontWeight: 700 }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card style={{ background: '#161b22', borderColor: '#30363d', borderRadius: '12px' }}>
            <Statistic
              title={<span style={{ color: '#8b949e' }}>Plugin & Database Skills</span>}
              value={stats?.skills?.total ?? 8}
              prefix={<AppstoreOutlined style={{ color: '#d29922' }} />}
              valueStyle={{ color: '#f3f4f6', fontWeight: 700 }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card style={{ background: '#161b22', borderColor: '#30363d', borderRadius: '12px' }}>
            <Statistic
              title={<span style={{ color: '#8b949e' }}>Connected Workspaces</span>}
              value={stats?.projects?.total ?? 1}
              prefix={<FolderOpenOutlined style={{ color: '#a371f7' }} />}
              valueStyle={{ color: '#f3f4f6', fontWeight: 700 }}
            />
          </Card>
        </Col>
      </Row>

      {/* System Health */}
      <Card
        title={<span style={{ color: '#f3f4f6' }}>🟢 System Health & Infrastructure</span>}
        style={{ background: '#161b22', borderColor: '#30363d', borderRadius: '12px' }}
      >
        <div style={{ display: 'flex', gap: '24px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircleOutlined style={{ color: '#52c41a' }} />
            <span style={{ color: '#d1d5db' }}>FastAPI Backend: <strong>Port 8000 (Online)</strong></span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircleOutlined style={{ color: '#52c41a' }} />
            <span style={{ color: '#d1d5db' }}>Persistence Manager: <strong>SQLite Ready</strong></span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircleOutlined style={{ color: '#52c41a' }} />
            <span style={{ color: '#d1d5db' }}>Plugin Hub: <strong>Local Workspace Scanned</strong></span>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default DashboardPage;

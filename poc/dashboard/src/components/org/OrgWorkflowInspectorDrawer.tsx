import React from 'react';
import { Drawer, Tabs, Tag, Button, Space, Descriptions, Empty, message } from 'antd';
import {
  ApartmentOutlined,
  CodeOutlined,
  FileSearchOutlined,
  ExportOutlined,
  CopyOutlined,
  RobotOutlined,
  ToolOutlined,
  GithubOutlined,
  SendOutlined,
  SlackOutlined,
  BranchesOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { EnrichedWorkflowNode } from './orgWorkflowsCanvasModel';
import { OrgWorkflowsCanvasText } from '../../i18n/orgWorkflowsCanvas';
import { WorkflowCanvasGraph } from '../workflows/WorkflowCanvasGraph';

export interface OrgWorkflowInspectorDrawerProps {
  node: EnrichedWorkflowNode | null;
  departmentName?: string;
  activeTab: 'overview' | 'dag' | 'yaml';
  onTabChange: (tab: 'overview' | 'dag' | 'yaml') => void;
  onClose: () => void;
  onOpenLogs: (workflowId: string) => void;
  onOpenHub: () => void;
  text: OrgWorkflowsCanvasText;
}

export const OrgWorkflowInspectorDrawer: React.FC<OrgWorkflowInspectorDrawerProps> = ({
  node,
  departmentName,
  activeTab,
  onTabChange,
  onClose,
  onOpenLogs,
  onOpenHub,
  text,
}) => {
  if (!node) return null;
  const { workflow, runnerAgentId, triggers, steps, mcpServers, repositories, skills, channels } = node;

  const rawDefinition =
    workflow.definition_yaml ||
    (workflow.definition_json
      ? (() => {
          try {
            return JSON.stringify(JSON.parse(workflow.definition_json), null, 2);
          } catch {
            return workflow.definition_json;
          }
        })()
      : '');

  const handleCopy = () => {
    navigator.clipboard.writeText(rawDefinition);
    message.success('Playbook definition copied to clipboard');
  };

  return (
    <Drawer
      title={
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <ApartmentOutlined style={{ color: '#a855f7', fontSize: 18 }} />
            <div>
              <div style={{ color: '#f0f6fc', fontWeight: 700, fontSize: 15 }}>
                {workflow.name}
              </div>
              <div style={{ color: '#8b949e', fontSize: 11, fontWeight: 400 }}>
                {text.drawerTitle} • ID: <code>{workflow.id}</code>
              </div>
            </div>
          </div>
          <Space size={8}>
            <Button
              size="small"
              icon={<FileSearchOutlined />}
              onClick={() => onOpenLogs(workflow.id)}
              style={{ background: '#161b22', borderColor: '#30363d', color: '#c9d1d9' }}
            >
              {text.openLogs}
            </Button>
            <Button
              size="small"
              type="primary"
              icon={<ExportOutlined />}
              onClick={onOpenHub}
              style={{ background: '#8b5cf6', borderColor: '#8b5cf6' }}
            >
              {text.openHub}
            </Button>
          </Space>
        </div>
      }
      open={Boolean(node)}
      onClose={onClose}
      width={920}
      styles={{
        header: { background: '#0d1117', borderBottom: '1px solid #30363d' },
        body: { background: '#0a0d12', padding: '16px 24px' },
      }}
    >
      <Tabs
        activeKey={activeTab}
        onChange={(k) => onTabChange(k as 'overview' | 'dag' | 'yaml')}
        items={[
          {
            key: 'dag',
            label: (
              <span style={{ fontWeight: 600 }}>
                <ApartmentOutlined style={{ marginRight: 6 }} />
                {text.drawerDagTab} ({steps.length})
              </span>
            ),
            children: (
              <WorkflowCanvasGraph
                workflowName={workflow.name}
                steps={steps}
                channelBinding={workflow.channel_binding}
                skills={skills.map((s) => ({ id: s, name: s }))}
                allowedMcps={mcpServers}
                height={500}
              />
            ),
          },
          {
            key: 'overview',
            label: (
              <span style={{ fontWeight: 600 }}>
                <BranchesOutlined style={{ marginRight: 6 }} />
                {text.drawerOverviewTab}
              </span>
            ),
            children: (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <Descriptions
                  bordered
                  size="small"
                  column={2}
                  styles={{
                    label: { background: '#161b22', color: '#8b949e', width: 170 },
                    content: { background: '#0d1117', color: '#f0f6fc' },
                  }}
                >
                  <Descriptions.Item label={text.legendDepartment}>
                    <Tag color="blue">{departmentName || text.unassignedDept}</Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label="Status">
                    <Tag color={workflow.is_active ? 'success' : 'default'}>
                      {workflow.is_active ? text.activeBadge : text.inactiveBadge}
                    </Tag>
                    {workflow.revision && <Tag style={{ marginLeft: 6 }}>v{workflow.revision}</Tag>}
                  </Descriptions.Item>
                  <Descriptions.Item label={text.runnerAgent} span={2}>
                    <Tag color="cyan">
                      <RobotOutlined style={{ marginRight: 4 }} />
                      {runnerAgentId}
                    </Tag>
                  </Descriptions.Item>
                  <Descriptions.Item label={text.triggersLabel} span={2}>
                    <Space size={6} wrap>
                      {triggers.map((tr, i) => (
                        <Tag key={i} color="geekblue">
                          {tr.type === 'cron' ? <ClockCircleOutlined /> : <ThunderboltOutlined />}{' '}
                          {tr.label}
                        </Tag>
                      ))}
                    </Space>
                  </Descriptions.Item>
                  <Descriptions.Item label={text.repositories} span={2}>
                    {repositories.length > 0 ? (
                      <Space size={6} wrap>
                        {repositories.map((r) => (
                          <Tag key={r} color="purple">
                            <GithubOutlined style={{ marginRight: 4 }} />
                            {r}
                          </Tag>
                        ))}
                      </Space>
                    ) : (
                      <span style={{ color: '#6e7681' }}>—</span>
                    )}
                  </Descriptions.Item>
                  <Descriptions.Item label={text.mcpConnectors} span={2}>
                    {mcpServers.length > 0 ? (
                      <Space size={6} wrap>
                        {mcpServers.map((m) => (
                          <Tag key={m} color="cyan">
                            <ToolOutlined style={{ marginRight: 4 }} />
                            {m}
                          </Tag>
                        ))}
                      </Space>
                    ) : (
                      <span style={{ color: '#6e7681' }}>—</span>
                    )}
                  </Descriptions.Item>
                  <Descriptions.Item label={text.skills} span={2}>
                    {skills.length > 0 ? (
                      <Space size={6} wrap>
                        {skills.map((s) => (
                          <Tag key={s} color="gold">
                            {s}
                          </Tag>
                        ))}
                      </Space>
                    ) : (
                      <span style={{ color: '#6e7681' }}>—</span>
                    )}
                  </Descriptions.Item>
                  <Descriptions.Item label={text.deliveryChannels} span={2}>
                    {channels.length > 0 ? (
                      <Space size={6} wrap>
                        {channels.map((ch, idx) => (
                          <Tag key={idx} color={ch.provider === 'telegram' ? 'blue' : 'orange'}>
                            {ch.provider === 'telegram' ? <SendOutlined /> : <SlackOutlined />}{' '}
                            {ch.provider.toUpperCase()}: {ch.channelName || ch.channelId}
                          </Tag>
                        ))}
                      </Space>
                    ) : (
                      <span style={{ color: '#6e7681' }}>—</span>
                    )}
                  </Descriptions.Item>
                </Descriptions>
              </div>
            ),
          },
          {
            key: 'yaml',
            label: (
              <span style={{ fontWeight: 600 }}>
                <CodeOutlined style={{ marginRight: 6 }} />
                {text.drawerYamlTab}
              </span>
            ),
            children: rawDefinition ? (
              <div>
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
                  <Button size="small" icon={<CopyOutlined />} onClick={handleCopy}>
                    Copy Definition
                  </Button>
                </div>
                <pre
                  style={{
                    background: '#0d1117',
                    border: '1px solid #30363d',
                    color: '#7ee787',
                    padding: 16,
                    borderRadius: 8,
                    fontSize: 12,
                    fontFamily: 'monospace',
                    maxHeight: 500,
                    overflow: 'auto',
                  }}
                >
                  {rawDefinition}
                </pre>
              </div>
            ) : (
              <Empty description="No definition found" />
            ),
          },
        ]}
      />
    </Drawer>
  );
};

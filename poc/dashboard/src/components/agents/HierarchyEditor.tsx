import { usePermissions } from '../../hooks/usePermissions';
import React, { useEffect, useState } from 'react';
import { Card, Tag, Button, Tree, Modal, Form, Select, InputNumber, message, Spin, Tooltip, Badge } from 'antd';
import {
  BranchesOutlined,
  UserOutlined,
  CrownOutlined,
  StarOutlined,
  EditOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import { Agent, AgentRole } from '../../types/agent';
import { getEntireHierarchyTree, updateAgent, getAgents } from '../../services/api';

interface HierarchyEditorProps {
  onHierarchyUpdated?: () => void;
}

export const HierarchyEditor: React.FC<HierarchyEditorProps> = ({ onHierarchyUpdated }) => {
  const { canManage } = usePermissions();
  const [treeData, setTreeData] = useState<any[]>([]);
  const [allAgents, setAllAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // Edit node modal state
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);
  const [modalVisible, setModalVisible] = useState<boolean>(false);
  const [form] = Form.useForm();
  const [saving, setSaving] = useState<boolean>(false);

  const loadHierarchy = async () => {
    try {
      setLoading(true);
      const [treeRes, agentsRes] = await Promise.all([getEntireHierarchyTree(), getAgents()]);
      setTreeData(treeRes.data || []);
      setAllAgents(agentsRes.data || []);
    } catch (err) {
      console.error(err);
      message.error('Failed to load hierarchy tree');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHierarchy();
  }, []);

  const handleEditAgent = (agent: Agent) => {
    setEditingAgent(agent);
    form.resetFields();
    form.setFieldsValue({
      role_type: agent.role_type || 'WORKER',
      parent_id: agent.parent_id || null,
      max_concurrent_children: agent.max_concurrent_children || 3,
    });
    setModalVisible(true);
  };

  const handleSave = async () => {
    if (!editingAgent) return;
    try {
      const values = await form.validateFields();
      setSaving(true);

      await updateAgent(editingAgent.id, {
        role_type: values.role_type,
        parent_id: values.parent_id || null,
        max_concurrent_children: values.max_concurrent_children,
      });

      message.success(`Hierarchy updated for "${editingAgent.name}"`);
      setModalVisible(false);
      loadHierarchy();
      if (onHierarchyUpdated) onHierarchyUpdated();
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to update hierarchy';
      message.error(detail);
    } finally {
      setSaving(false);
    }
  };

  // Convert raw hierarchy forest into Ant Design Tree nodes
  const buildTreeNodes = (nodes: any[]): any[] => {
    return nodes.map((node) => {
      const role = (node.role_type || 'WORKER').toUpperCase();
      const isRoot = role === 'ROOT_ORCHESTRATOR';
      const isManager = role === 'MANAGER';
      const childCount = node.children ? node.children.length : 0;

      return {
        key: node.id,
        title: (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '6px 12px',
              background: isRoot ? '#2e1065' : isManager ? '#451a03' : '#1e293b',
              border: isRoot ? '1px solid #7c3aed' : isManager ? '1px solid #d97706' : '1px solid #334155',
              borderRadius: '8px',
              color: '#f8fafc',
              minWidth: '280px',
              maxWidth: '500px',
            }}
          >
            {isRoot ? (
              <CrownOutlined style={{ color: '#fbbf24', fontSize: '15px' }} />
            ) : isManager ? (
              <StarOutlined style={{ color: '#f59e0b', fontSize: '14px' }} />
            ) : (
              <UserOutlined style={{ color: '#38bdf8', fontSize: '13px' }} />
            )}

            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span>{node.name}</span>
                <Tag
                  color={isRoot ? 'purple' : isManager ? 'gold' : 'cyan'}
                  style={{ fontSize: '10px', padding: '0 4px', margin: 0 }}
                >
                  {role}
                </Tag>
              </div>
              <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                Dept: {node.department || 'Engineering'}
                {isManager && ` • Max Concurrency: ${node.max_concurrent_children || 3} • Subordinates: ${childCount}`}
              </div>
            </div>

            <Button
              size="small"
              type="text"
              disabled={!canManage} icon={<EditOutlined style={{ color: '#94a3b8' }} />}
              onClick={(e) => {
                e.stopPropagation();
                handleEditAgent(node);
              }}
            />
          </div>
        ),
        children: node.children ? buildTreeNodes(node.children) : [],
      };
    });
  };

  // Available managers that editingAgent can report to (excluding self and current children)
  const availableParents = allAgents.filter((a) => {
    if (!editingAgent) return false;
    if (a.id === editingAgent.id) return false;
    const r = (a.role_type || '').toUpperCase();
    return r === 'MANAGER' || r === 'ROOT_ORCHESTRATOR';
  });

  return (
    <div>
      <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ margin: 0, color: '#f8fafc', fontSize: '18px', fontWeight: 700 }}>
            🌲 Organizational Reporting & Delegation Tree
          </h3>
          <span style={{ color: '#94a3b8', fontSize: '13px' }}>
            Structured reporting lines enforcing delegation boundaries, cycle detection, and concurrency gates.
          </span>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin size="large" />
        </div>
      ) : treeData.length === 0 ? (
        <Card style={{ background: '#1e293b', border: '1px solid #334155', color: '#94a3b8', textAlign: 'center' }}>
          No hierarchical relationships configured yet. Assign managers or instantiate from templates.
        </Card>
      ) : (
        <Card style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '12px' }}>
          <Tree
            showLine
            defaultExpandAll
            treeData={buildTreeNodes(treeData)}
            style={{ background: 'transparent', color: '#f8fafc' }}
          />
        </Card>
      )}

      {/* Edit Hierarchy Modal */}
      <Modal
        title={`Configure Hierarchy: ${editingAgent?.name}`}
        open={modalVisible}
        onOk={handleSave}
        onCancel={() => setModalVisible(false)}
        confirmLoading={saving}
        okText="Update Hierarchy"
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="role_type"
            label="Agent Role"
            rules={[{ required: true, message: 'Please select a role' }]}
          >
            <Select>
              <Select.Option value="ROOT_ORCHESTRATOR">ROOT_ORCHESTRATOR (Top-level Executive)</Select.Option>
              <Select.Option value="MANAGER">MANAGER (Can supervise workers & delegate)</Select.Option>
              <Select.Option value="WORKER">WORKER (Standard task executor)</Select.Option>
              <Select.Option value="SPECIALIST">SPECIALIST (Domain expert executor)</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            noStyle
            shouldUpdate={(prev, curr) => prev.role_type !== curr.role_type}
          >
            {({ getFieldValue }) => {
              const currentRole = getFieldValue('role_type');
              if (currentRole === 'ROOT_ORCHESTRATOR') {
                return (
                  <div style={{ color: '#94a3b8', fontSize: '12px', marginBottom: '16px' }}>
                    ℹ️ A Root Orchestrator cannot have a parent supervisor.
                  </div>
                );
              }
              return (
                <Form.Item
                  name="parent_id"
                  label="Reports To (Supervisor)"
                  help="Select the manager supervising this agent. Circular references are automatically rejected."
                >
                  <Select placeholder="None (Independent agent)" allowClear>
                    {availableParents.map((mgr) => (
                      <Select.Option key={mgr.id} value={mgr.id}>
                        ⭐ {mgr.name} ({mgr.role_type})
                      </Select.Option>
                    ))}
                  </Select>
                </Form.Item>
              );
            }}
          </Form.Item>

          <Form.Item
            noStyle
            shouldUpdate={(prev, curr) => prev.role_type !== curr.role_type}
          >
            {({ getFieldValue }) => {
              const currentRole = getFieldValue('role_type');
              if (currentRole === 'MANAGER' || currentRole === 'ROOT_ORCHESTRATOR') {
                return (
                  <Form.Item
                    name="max_concurrent_children"
                    label="Max Concurrent Subtasks"
                    help="Maximum number of active subtasks this manager can execute in parallel"
                  >
                    <InputNumber min={1} max={20} style={{ width: '100%' }} />
                  </Form.Item>
                );
              }
              return null;
            }}
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

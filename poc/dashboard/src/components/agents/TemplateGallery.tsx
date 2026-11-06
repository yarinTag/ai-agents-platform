import { usePermissions } from '../../hooks/usePermissions';
import React, { useEffect, useState } from 'react';
import { Card, Button, Tag, Modal, Form, Input, Select, message, Spin, Space } from 'antd';
import { ThunderboltOutlined, UserAddOutlined, BranchesOutlined, CheckCircleOutlined, FolderOpenOutlined } from '@ant-design/icons';
import { Agent, AgentTemplate, TemplateInstantiateDto } from '../../types/agent';
import { getTemplates, instantiateTemplate } from '../../services/api';
import FolderPickerModal from '../common/FolderPickerModal';
import { useAuth } from '../../context/AuthContext';

interface TemplateGalleryProps {
  agents: Agent[];
  onAgentInstantiated?: () => void;
}

export const TemplateGallery: React.FC<TemplateGalleryProps> = ({
  agents,
  onAgentInstantiated,
}) => {
  const { canManage } = usePermissions();
  const { departments, activeDepartmentId } = useAuth();
  const [templates, setTemplates] = useState<AgentTemplate[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedTemplate, setSelectedTemplate] = useState<AgentTemplate | null>(null);
  const [modalVisible, setModalVisible] = useState<boolean>(false);
  const [folderPickerVisible, setFolderPickerVisible] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [form] = Form.useForm();

  const loadTemplates = async () => {
    try {
      setLoading(true);
      const res = await getTemplates();
      setTemplates(res.data || []);
    } catch (err) {
      console.error(err);
      message.error('Failed to load agent templates');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTemplates();
  }, []);

  const handleOpenInstantiate = (template: AgentTemplate) => {
    setSelectedTemplate(template);
    form.resetFields();
    const activeDept = departments.find((d) => d.id === activeDepartmentId) || departments[0];
    form.setFieldsValue({
      name: `${template.name} (Unit)`,
      department: activeDept ? activeDept.name : (template.category || 'Engineering'),
      model_override: template.model || 'default',
    });
    setModalVisible(true);
  };

  const handleInstantiateSubmit = async () => {
    if (!selectedTemplate) return;
    try {
      const values = await form.validateFields();
      setSubmitting(true);

      const payload: TemplateInstantiateDto = {
        name: values.name,
        parent_id: values.parent_id || null,
        department: values.department,
        repo_path: values.repo_path || null,
        github_url: values.github_url || null,
        system_prompt_override: values.system_prompt_override || undefined,
        model_override: values.model_override || undefined,
      };

      await instantiateTemplate(selectedTemplate.id, payload);
      message.success(`Agent "${values.name}" instantiated from template!`);
      setModalVisible(false);
      if (onAgentInstantiated) onAgentInstantiated();
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to instantiate agent';
      message.error(detail);
    } finally {
      setSubmitting(false);
    }
  };

  // Potential managers who can be parents
  const availableManagers = agents.filter(
    (a) =>
      (a.role_type || '').toUpperCase() === 'MANAGER' ||
      (a.role_type || '').toUpperCase() === 'ROOT_ORCHESTRATOR'
  );

  return (
    <div>
      <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h3 style={{ margin: 0, color: '#f8fafc', fontSize: '18px', fontWeight: 700 }}>
            📚 Reusable Agent Templates
          </h3>
          <span style={{ color: '#94a3b8', fontSize: '13px' }}>
            Instant, battle-tested blueprints for rapid multi-agent team assembly.
          </span>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin size="large" />
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
          {templates.map((tpl) => (
            <Card
              key={tpl.id}
              style={{
                background: '#1e293b',
                border: '1px solid #334155',
                borderRadius: '12px',
                color: '#f8fafc',
              }}
              actions={[
                <Button
                  type="primary"
                  icon={<UserAddOutlined />}
                  disabled={!canManage} onClick={() => handleOpenInstantiate(tpl)}
                  style={{ background: '#0284c7', borderColor: '#0284c7', borderRadius: '6px' }}
                >
                  Instantiate Agent
                </Button>,
              ]}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                <span style={{ fontWeight: 700, fontSize: '15px', color: '#f8fafc' }}>
                  {tpl.name}
                </span>
                <Tag
                  color={
                    tpl.role === 'MANAGER'
                      ? 'gold'
                      : tpl.role === 'ROOT_ORCHESTRATOR'
                      ? 'purple'
                      : tpl.role === 'SPECIALIST'
                      ? 'magenta'
                      : 'cyan'
                  }
                >
                  {tpl.role}
                </Tag>
              </div>

              <p style={{ color: '#94a3b8', fontSize: '12px', minHeight: '36px', marginBottom: '12px' }}>
                {tpl.description}
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '11px' }}>
                <div>
                  <span style={{ color: '#64748b' }}>Category: </span>
                  <Tag color="blue">{tpl.category}</Tag>
                </div>

                {tpl.tools && tpl.tools.length > 0 && (
                  <div>
                    <span style={{ color: '#64748b' }}>Allowed Tools: </span>
                    <Space size={[0, 4]} wrap>
                      {tpl.tools.map((tool) => (
                        <Tag key={tool} color="geekblue" style={{ fontSize: '10px' }}>
                          {tool}
                        </Tag>
                      ))}
                    </Space>
                  </div>
                )}

                {tpl.suggested_children && tpl.suggested_children.length > 0 && (
                  <div>
                    <span style={{ color: '#64748b' }}>Delegation Subordinates: </span>
                    <Space size={[0, 4]} wrap>
                      {tpl.suggested_children.map((child) => (
                        <Tag key={child} color="purple" style={{ fontSize: '10px' }}>
                          {child}
                        </Tag>
                      ))}
                    </Space>
                  </div>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Instantiation Modal */}
      <Modal
        title={`Instantiate: ${selectedTemplate?.name}`}
        open={modalVisible}
        onOk={handleInstantiateSubmit}
        onCancel={() => setModalVisible(false)}
        confirmLoading={submitting}
        okText="Deploy Agent"
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="Agent Name"
            rules={[{ required: true, message: 'Please provide an agent name' }]}
          >
            <Input placeholder="e.g. Architecture Lead" />
          </Form.Item>

          <Form.Item name="department" label="Department">
            {departments && departments.length > 0 ? (
              <Select
                placeholder="Select Department"
                options={departments.map((d) => ({
                  value: d.name,
                  label: `📁 ${d.name}`,
                }))}
              />
            ) : (
              <Input placeholder="Engineering, Architecture, QA & Testing, etc." />
            )}
          </Form.Item>

          {selectedTemplate?.role !== 'ROOT_ORCHESTRATOR' && (
            <Form.Item
              name="parent_id"
              label="Reports To (Parent Manager)"
              help="Select an existing Manager or Root Orchestrator to supervise this agent"
            >
              <Select placeholder="Select parent supervisor (Optional)" allowClear>
                {availableManagers.map((mgr) => (
                  <Select.Option key={mgr.id} value={mgr.id}>
                    ⭐ {mgr.name} ({mgr.role_type})
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>
          )}

          <Form.Item name="repo_path" label="Local Repository Path">
            <Input
              placeholder="Optional local folder path for file-system access"
              addonAfter={
                <Button
                  type="link"
                  size="small"
                  icon={<FolderOpenOutlined />}
                  disabled onClick={() => setFolderPickerVisible(true)}
                  style={{ padding: '0 6px', color: '#38bdf8' }}
                >
                  Browse...
                </Button>
              }
            />
          </Form.Item>

          <Form.Item name="system_prompt_override" label="Custom Instructions (Override)">
            <Input.TextArea
              rows={3}
              placeholder={`Leave empty to inherit default:\n${selectedTemplate?.system_prompt}`}
            />
          </Form.Item>
        </Form>
      </Modal>

      <FolderPickerModal
        open={folderPickerVisible}
        onClose={() => setFolderPickerVisible(false)}
        onSelect={(path) => form.setFieldsValue({ repo_path: path })}
        title="📁 Select Template Local Repository Folder"
      />
    </div>
  );
};

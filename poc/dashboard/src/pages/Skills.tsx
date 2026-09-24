import React, { useEffect, useState, useRef } from 'react';
import {
  Table,
  Form,
  Input,
  Button,
  Modal,
  Tag,
  Tabs,
  message,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  AppstoreOutlined,
  FolderOpenOutlined,
  FileTextOutlined,
  SyncOutlined,
  ThunderboltOutlined,
  CopyOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import { Skill, PluginPackage } from '../types/skill';
import { getSkills, createSkill, updateSkill, deleteSkill, scanPlugins, getPluginSkillContent } from '../services/api';


export const SkillsPage: React.FC = () => {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [plugins, setPlugins] = useState<PluginPackage[]>([]);
  const [marketplacePath, setMarketplacePath] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [scanning, setScanning] = useState<boolean>(false);
  const [visible, setVisible] = useState<boolean>(false);
  const [form] = Form.useForm();
  const [editingKey, setEditingKey] = useState<string>('');
  const [selectedPluginSkill, setSelectedPluginSkill] = useState<any>(null);
  const [skillContent, setSkillContent] = useState<string>('');
  const [loadingContent, setLoadingContent] = useState<boolean>(false);
  const hasScannedRef = useRef<boolean>(false);

  const fetchSkills = async () => {
    try {
      setLoading(true);
      const res = await getSkills();
      setSkills(res.data || []);
    } catch (err) {
      console.error(err);
      message.error('Failed to load registered skills');
    } finally {
      setLoading(false);
    }
  };

  const handleScanPlugins = async (isManual: boolean = false) => {
    try {
      setScanning(true);
      const res = await scanPlugins();
      if (res.data && res.data.plugins) {
        setPlugins(res.data.plugins);
        setMarketplacePath(res.data.marketplace_path || '');
        if (isManual) {
          message.success(`Discovered ${res.data.total_skills} skills across ${res.data.plugins.length} plugin packages!`);
        }
      }
    } catch (err: any) {
      console.error('Plugin scan failed', err);
      if (isManual) {
        message.error(`Plugin scan failed: ${err?.message || 'Unable to scan plugins'}`);
      }
      setPlugins([]);
    } finally {
      setScanning(false);
    }
  };

  const handleSelectSkill = async (skill: any) => {
    setSelectedPluginSkill(skill);
    setSkillContent(skill.content_preview || '');
    try {
      setLoadingContent(true);
      const res = await getPluginSkillContent(skill.path);
      if (res.data?.content) {
        setSkillContent(res.data.content);
      }
    } catch (err) {
      // Keep preview
    } finally {
      setLoadingContent(false);
    }
  };

  useEffect(() => {
    fetchSkills();
    if (!hasScannedRef.current) {
      hasScannedRef.current = true;
      handleScanPlugins(false);
    }
  }, []);

  const handleCreate = () => {
    form.resetFields();
    setEditingKey('');
    setVisible(true);
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      if (editingKey) {
        await updateSkill(editingKey, values);
        message.success('Skill updated successfully');
      } else {
        await createSkill(values);
        message.success('Skill registered successfully');
      }
      setVisible(false);
      fetchSkills();
    } catch (err) {
      message.error('Failed to save skill');
      console.error(err);
    }
  };

  const columns = [
    {
      title: 'Skill Name',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => (
        <span style={{ fontWeight: 600, color: '#f3f4f6' }}>
          ⚡ {text}
        </span>
      ),
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      render: (text: string) => <span style={{ color: '#9ca3af' }}>{text || 'No description'}</span>,
    },
    {
      title: 'Scope',
      dataIndex: 'project_id',
      key: 'project_id',
      render: (projId: string | null) => (
        <Tag color={projId ? 'purple' : 'blue'}>
          {projId ? `Project: ${projId}` : 'Global Skill'}
        </Tag>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: Skill) => (
        <div style={{ display: 'flex', gap: '8px' }}>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => {
              form.setFieldsValue({
                name: record.name,
                description: record.description,
                content: record.content,
              });
              setEditingKey(record.id);
              setVisible(true);
            }}
          >
            Edit
          </Button>
          <Button
            size="small"
            danger
            icon={<DeleteOutlined />}
            onClick={() => {
              deleteSkill(record.id)
                .then(() => {
                  message.success('Skill removed');
                  fetchSkills();
                })
                .catch((err) => {
                  message.error('Failed to delete skill');
                  console.error(err);
                });
            }}
          >
            Delete
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h2 style={{ margin: 0, color: '#f3f4f6', fontSize: '22px', fontWeight: 700 }}>
            🧩 Skills & Plugins Ecosystem
          </h2>
          <span style={{ color: '#9ca3af', fontSize: '13px' }}>
            Local workspace plugins, custom agent skills, and modular capability extensions
          </span>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <Button
            icon={<SyncOutlined spin={scanning} />}
            onClick={() => handleScanPlugins(true)}
            style={{ background: '#21262d', color: '#c9d1d9', borderColor: '#30363d' }}
          >
            Rescan Local Plugins
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate} style={{ background: '#238636', borderColor: '#238636' }}>
            Create Custom Skill
          </Button>
        </div>
      </div>

      <Tabs
        defaultActiveKey="plugins"
        items={[
          {
            key: 'plugins',
            label: (
              <span>
                <AppstoreOutlined /> Skills Repository Hub ({plugins.reduce((acc, p) => acc + p.skills_count, 0)} Skills)
              </span>
            ),
            children: (
              <div>
                <div
                  style={{
                    background: '#161b22',
                    padding: '14px 18px',
                    borderRadius: '8px',
                    border: '1px solid #30363d',
                    marginBottom: '20px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: '10px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <CheckCircleOutlined style={{ color: '#52c41a', fontSize: '18px' }} />
                    <div>
                      <span style={{ color: '#f3f4f6', fontWeight: 600, fontSize: '13px' }}>
                        Connected Skills Repository:
                      </span>{' '}
                      <code style={{ color: '#58a6ff', background: '#0d1117', padding: '2px 8px', borderRadius: '4px', fontSize: '12px' }}>
                        {marketplacePath || 'Local Skills Marketplace'}
                      </code>
                    </div>
                  </div>
                  <Tag color="green" style={{ margin: 0, padding: '2px 10px', fontSize: '12px' }}>
                    {plugins.reduce((acc, p) => acc + p.skills_count, 0)} Production Skills Active
                  </Tag>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {plugins.map((plugin) => (
                    <div
                      key={plugin.name}
                      style={{
                        background: '#0d1117',
                        border: '1px solid #30363d',
                        borderRadius: '12px',
                        padding: '18px 20px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                          <FolderOpenOutlined style={{ color: '#e3b341', fontSize: '18px' }} />
                          <span style={{ fontSize: '16px', fontWeight: 700, color: '#f3f4f6' }}>
                            {plugin.display_name || plugin.name.toUpperCase()}
                          </span>
                          {plugin.version && <Tag color="blue">v{plugin.version}</Tag>}
                          {plugin.domain && <Tag color="purple">{plugin.domain}</Tag>}
                          <Tag color="cyan">{plugin.skills_count} Skills</Tag>
                        </div>
                        <span style={{ fontSize: '11px', color: '#6e7681', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {plugin.path}
                        </span>
                      </div>

                      {plugin.description && (
                        <div style={{ fontSize: '12px', color: '#8b949e', marginBottom: '14px', lineHeight: '1.4' }}>
                          {plugin.description}
                        </div>
                      )}

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(290px, 1fr))', gap: '12px' }}>
                        {plugin.skills.map((skill) => (
                          <div
                            key={skill.id}
                            onClick={() => handleSelectSkill(skill)}
                            style={{
                              background: '#161b22',
                              border: '1px solid #30363d',
                              borderRadius: '8px',
                              padding: '12px',
                              cursor: 'pointer',
                              transition: 'all 0.2s ease',
                              display: 'flex',
                              flexDirection: 'column',
                              justifyContent: 'space-between',
                            }}
                            onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#58a6ff')}
                            onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#30363d')}
                          >
                            <div>
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600, color: '#58a6ff', fontSize: '13px' }}>
                                  <ThunderboltOutlined /> {skill.name}
                                </div>
                              </div>
                              <code style={{ fontSize: '11px', color: '#79c0ff', background: '#0d1117', padding: '1px 5px', borderRadius: '3px' }}>
                                {skill.id}
                              </code>
                              <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '6px', lineHeight: '1.4', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                                {skill.description}
                              </div>
                            </div>
                            <div style={{ marginTop: '10px', fontSize: '10px', color: '#6e7681', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                              <span><FileTextOutlined /> {skill.filename}</span>
                              {skill.domain && <Tag color="default" style={{ margin: 0, fontSize: '9px', padding: '0 4px' }}>{skill.domain}</Tag>}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ),
          },
          {
            key: 'registered',
            label: (
              <span>
                <FileTextOutlined /> Custom Registered Skills ({skills.length})
              </span>
            ),
            children: (
              <Table
                loading={loading}
                rowKey="id"
                columns={columns}
                dataSource={skills}
                pagination={{ pageSize: 10 }}
              />
            ),
          },
        ]}
      />

      {/* Skill Modal */}
      <Modal
        title={editingKey ? 'Edit Skill' : 'Create Custom Skill'}
        open={visible}
        onOk={handleOk}
        onCancel={() => setVisible(false)}
      >
        <Form form={form} layout="vertical">
          <Form.Item label="Name" name="name" rules={[{ required: true, message: 'Please input skill name!' }]}>
            <Input placeholder="e.g., Code Reviewer" />
          </Form.Item>
          <Form.Item label="Description" name="description">
            <Input placeholder="Brief overview of capability" />
          </Form.Item>
          <Form.Item label="Instructions / Skill Markdown" name="content" rules={[{ required: true, message: 'Content required' }]}>
            <Input.TextArea rows={6} placeholder="# Skill Instructions\n\n1. Analyze code..." />
          </Form.Item>
        </Form>
      </Modal>

      {/* Plugin Skill Detail Modal */}
      <Modal
        title={selectedPluginSkill ? `⚡ ${selectedPluginSkill.name}` : ''}
        open={!!selectedPluginSkill}
        onCancel={() => setSelectedPluginSkill(null)}
        width={720}
        footer={[
          <Button
            key="copy"
            icon={<CopyOutlined />}
            onClick={() => {
              if (selectedPluginSkill) {
                navigator.clipboard.writeText(selectedPluginSkill.id);
                message.success(`Copied skill ID: ${selectedPluginSkill.id}`);
              }
            }}
          >
            Copy Skill ID
          </Button>,
          <Button key="close" type="primary" onClick={() => setSelectedPluginSkill(null)}>
            Close
          </Button>,
        ]}
      >
        {selectedPluginSkill && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
              <span style={{ color: '#8b949e', fontSize: '12px' }}>Skill ID:</span>
              <code style={{ color: '#58a6ff', background: '#161b22', padding: '2px 8px', borderRadius: '4px', fontSize: '13px' }}>
                {selectedPluginSkill.id}
              </code>
              <Tag color="blue">Plugin: {selectedPluginSkill.plugin}</Tag>
              {selectedPluginSkill.domain && <Tag color="purple">{selectedPluginSkill.domain}</Tag>}
              {selectedPluginSkill.version && <Tag color="cyan">v{selectedPluginSkill.version}</Tag>}
            </div>

            <div>
              <span style={{ color: '#8b949e', fontSize: '12px', fontWeight: 600 }}>Description:</span>
              <div style={{ color: '#e6edf3', fontSize: '13px', marginTop: '4px', lineHeight: '1.5' }}>
                {selectedPluginSkill.description}
              </div>
            </div>

            <div>
              <span style={{ color: '#8b949e', fontSize: '12px', fontWeight: 600 }}>File Location:</span>
              <div style={{ marginTop: '4px' }}>
                <code style={{ fontSize: '11px', color: '#79c0ff', wordBreak: 'break-all' }}>
                  {selectedPluginSkill.path}
                </code>
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                <span style={{ color: '#8b949e', fontSize: '12px', fontWeight: 600 }}>
                  Skill Instructions & Rules (SKILL.md):
                </span>
                {loadingContent && <span style={{ color: '#58a6ff', fontSize: '11px' }}>Loading full instructions...</span>}
              </div>
              <div
                style={{
                  background: '#0d1117',
                  border: '1px solid #30363d',
                  borderRadius: '6px',
                  padding: '12px',
                  maxHeight: '280px',
                  overflowY: 'auto',
                  fontFamily: 'monospace',
                  fontSize: '12px',
                  color: '#c9d1d9',
                  whiteSpace: 'pre-wrap',
                  lineHeight: '1.5',
                }}
              >
                {skillContent || 'No instructions found in SKILL.md'}
              </div>
            </div>

            <div style={{ background: '#161b22', padding: '10px 14px', borderRadius: '6px', border: '1px solid #30363d', fontSize: '12px', color: '#8b949e' }}>
              💡 <strong>How to equip:</strong> Open <strong>Agents Roster</strong> or click an agent desk in the <strong>Virtual Office</strong> and add <code>{selectedPluginSkill.id}</code> to <strong>Equipped Skills</strong>.
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default SkillsPage;

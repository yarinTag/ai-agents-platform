import React, { useEffect, useState } from 'react';
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
} from '@ant-design/icons';
import { Skill, PluginPackage } from '../types/skill';
import { getSkills, createSkill, updateSkill, deleteSkill, scanPlugins } from '../services/api';


export const SkillsPage: React.FC = () => {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [plugins, setPlugins] = useState<PluginPackage[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [scanning, setScanning] = useState<boolean>(false);
  const [visible, setVisible] = useState<boolean>(false);
  const [form] = Form.useForm();
  const [editingKey, setEditingKey] = useState<string>('');
  const [selectedPluginSkill, setSelectedPluginSkill] = useState<any>(null);

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

  const handleScanPlugins = async () => {
    try {
      setScanning(true);
      const res = await scanPlugins();
      if (res.data && res.data.plugins) {
        setPlugins(res.data.plugins);
        message.success(`Discovered ${res.data.total_skills} skills across ${res.data.plugins.length} plugin packages!`);
      }
    } catch (err: any) {
      console.error('Plugin scan failed', err);
      message.error(`Plugin scan failed: ${err?.message || 'Unable to scan plugins'}`);
      setPlugins([]);
    } finally {
      setScanning(false);
    }
  };

  useEffect(() => {
    fetchSkills();
    handleScanPlugins();
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
            Connected to <code>C:\Users\taguo\OneDrive\Desktop\Projects\test</code> & <code>p-skills</code>
          </span>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <Button
            icon={<SyncOutlined spin={scanning} />}
            onClick={handleScanPlugins}
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
                <AppstoreOutlined /> Local Plugins Hub ({plugins.reduce((acc, p) => acc + p.skills_count, 0)} Skills)
              </span>
            ),
            children: (
              <div>
                <div
                  style={{
                    background: '#161b22',
                    padding: '12px 16px',
                    borderRadius: '8px',
                    border: '1px solid #30363d',
                    marginBottom: '16px',
                    color: '#8b949e',
                    fontSize: '12px',
                  }}
                >
                  📁 Scanned plugin repositories located in your local project workspace. Agents can be equipped with any of these capabilities directly from their desks.
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {plugins.map((plugin) => (
                    <div
                      key={plugin.name}
                      style={{
                        background: '#0d1117',
                        border: '1px solid #30363d',
                        borderRadius: '12px',
                        padding: '16px 20px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <FolderOpenOutlined style={{ color: '#e3b341', fontSize: '18px' }} />
                          <span style={{ fontSize: '16px', fontWeight: 600, color: '#f3f4f6' }}>
                            plugin: {plugin.name}
                          </span>
                          <Tag color="cyan">{plugin.skills_count} Skills</Tag>
                        </div>
                        <span style={{ fontSize: '11px', color: '#6e7681' }}>{plugin.path}</span>
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px' }}>
                        {plugin.skills.map((skill) => (
                          <div
                            key={skill.id}
                            onClick={() => setSelectedPluginSkill(skill)}
                            style={{
                              background: '#161b22',
                              border: '1px solid #30363d',
                              borderRadius: '8px',
                              padding: '12px',
                              cursor: 'pointer',
                              transition: 'all 0.2s ease',
                            }}
                            onMouseEnter={(e) => (e.currentTarget.style.borderColor = '#58a6ff')}
                            onMouseLeave={(e) => (e.currentTarget.style.borderColor = '#30363d')}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600, color: '#58a6ff', fontSize: '13px' }}>
                              <ThunderboltOutlined /> {skill.name}
                            </div>
                            <div style={{ fontSize: '11px', color: '#8b949e', marginTop: '4px', lineHeight: '1.4' }}>
                              {skill.description}
                            </div>
                            <div style={{ marginTop: '8px', fontSize: '10px', color: '#6e7681', display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <FileTextOutlined /> {skill.filename}
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
                <FileTextOutlined /> Registered Skills ({skills.length})
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
        title={selectedPluginSkill ? `Plugin Skill: ${selectedPluginSkill.name}` : ''}
        open={!!selectedPluginSkill}
        onCancel={() => setSelectedPluginSkill(null)}
        footer={[
          <Button key="close" onClick={() => setSelectedPluginSkill(null)}>
            Close
          </Button>,
        ]}
      >
        {selectedPluginSkill && (
          <div>
            <p><strong>Plugin:</strong> <Tag color="blue">{selectedPluginSkill.plugin}</Tag></p>
            <p><strong>Path:</strong> <code>{selectedPluginSkill.path}</code></p>
            <p><strong>Description:</strong> {selectedPluginSkill.description}</p>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default SkillsPage;

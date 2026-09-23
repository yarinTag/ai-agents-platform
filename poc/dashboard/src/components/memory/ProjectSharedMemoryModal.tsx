import React, { useState, useEffect } from 'react';
import {
  Modal,
  Tabs,
  Card,
  Button,
  Input,
  Select,
  Tag,
  List,
  Typography,
  Space,
  Popconfirm,
  message as antMessage,
  Spin,
  Alert,
  Divider,
} from 'antd';
import {
  BulbOutlined,
  DeleteOutlined,
  PlusOutlined,
  CodeOutlined,
  BookOutlined,
  CopyOutlined,
  CheckOutlined,
} from '@ant-design/icons';
import {
  getProjectMemories,
  createProjectMemory,
  deleteProjectMemory,
  getProjectContextPrompt,
  getProjects,
} from '../../services/api';
import { ProjectMemory, MemoryCategory } from '../../types/collab';

const { Text, Title, Paragraph } = Typography;
const { TextArea } = Input;
const { Option } = Select;

interface ProjectSharedMemoryModalProps {
  open: boolean;
  onClose: () => void;
  defaultProjectId?: string;
}

export const ProjectSharedMemoryModal: React.FC<ProjectSharedMemoryModalProps> = ({
  open,
  onClose,
  defaultProjectId,
}) => {
  const [projects, setProjects] = useState<any[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>(defaultProjectId || '');
  const [memories, setMemories] = useState<ProjectMemory[]>([]);
  const [loading, setLoading] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState<string>('ALL');

  // New Memory Form
  const [showAddForm, setShowAddForm] = useState(false);
  const [category, setCategory] = useState<MemoryCategory>('ADR');
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [tagsStr, setTagsStr] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Context Prompt Preview
  const [contextPrompt, setContextPrompt] = useState<string>('');
  const [showPromptPreview, setShowPromptPreview] = useState(false);
  const [copied, setCopied] = useState(false);

  const fetchProjects = async () => {
    try {
      const res = await getProjects();
      setProjects(res.data);
      if (!selectedProjectId && res.data.length > 0) {
        setSelectedProjectId(res.data[0].id);
      }
    } catch (err) {
      antMessage.error('Failed to load projects');
    }
  };

  const fetchMemories = async () => {
    if (!selectedProjectId) return;
    try {
      setLoading(true);
      const cat = categoryFilter === 'ALL' ? undefined : categoryFilter;
      const res = await getProjectMemories(selectedProjectId, cat);
      setMemories(res.data);
    } catch (err) {
      antMessage.error('Failed to load project memories');
    } finally {
      setLoading(false);
    }
  };

  const fetchPromptPreview = async () => {
    if (!selectedProjectId) return;
    try {
      const res = await getProjectContextPrompt(selectedProjectId);
      setContextPrompt(res.data.context_prompt);
      setShowPromptPreview(true);
    } catch (err) {
      antMessage.error('Failed to generate prompt preview');
    }
  };

  useEffect(() => {
    if (open) {
      fetchProjects();
    }
  }, [open]);

  useEffect(() => {
    if (selectedProjectId) {
      fetchMemories();
    }
  }, [selectedProjectId, categoryFilter]);

  const handleCreate = async () => {
    if (!title.trim() || !content.trim()) {
      antMessage.warning('Title and content are required');
      return;
    }
    try {
      setSubmitting(true);
      const tags = tagsStr
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean);
      await createProjectMemory(selectedProjectId, {
        category,
        title: title.trim(),
        content: content.trim(),
        tags,
      });
      antMessage.success('Knowledge memory recorded!');
      setTitle('');
      setContent('');
      setTagsStr('');
      setShowAddForm(false);
      await fetchMemories();
    } catch (err) {
      antMessage.error('Failed to record memory');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteProjectMemory(selectedProjectId, id);
      antMessage.success('Memory deleted');
      await fetchMemories();
    } catch (err) {
      antMessage.error('Failed to delete memory');
    }
  };

  const copyPromptToClipboard = () => {
    navigator.clipboard.writeText(contextPrompt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getCategoryColor = (cat: MemoryCategory) => {
    switch (cat) {
      case 'ADR':
        return 'purple';
      case 'CONVENTION':
        return 'blue';
      case 'INSIGHT':
        return 'green';
      case 'LESSON':
        return 'gold';
      default:
        return 'default';
    }
  };

  return (
    <Modal
      open={open}
      onCancel={onClose}
      width={900}
      footer={null}
      title={
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingRight: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <BookOutlined style={{ color: '#10b981', fontSize: '20px' }} />
            <span>Project Shared Knowledge Base & Conventions</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Select
              style={{ width: '180px' }}
              value={selectedProjectId}
              onChange={setSelectedProjectId}
              placeholder="Select Project"
            >
              {projects.map((p) => (
                <Option key={p.id} value={p.id}>
                  📁 {p.name || p.id}
                </Option>
              ))}
            </Select>

            <Button
              icon={<CodeOutlined />}
              onClick={fetchPromptPreview}
              style={{ borderColor: '#6366f1', color: '#6366f1' }}
            >
              Prompt Preview
            </Button>
          </div>
        </div>
      }
    >
      <div style={{ minHeight: '480px', maxHeight: '70vh', overflowY: 'auto', padding: '4px' }}>
        {/* Top bar controls */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <Tabs
            activeKey={categoryFilter}
            onChange={setCategoryFilter}
            items={[
              { key: 'ALL', label: 'All Knowledge' },
              { key: 'ADR', label: '🏛️ Architecture Decisions (ADR)' },
              { key: 'CONVENTION', label: '📏 Code Conventions' },
              { key: 'INSIGHT', label: '💡 Insights' },
              { key: 'LESSON', label: '📝 Lessons Learned' },
            ]}
            style={{ marginBottom: 0 }}
          />

          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setShowAddForm(!showAddForm)}
            style={{ background: '#10b981', borderColor: '#10b981' }}
          >
            {showAddForm ? 'Cancel' : 'Add Memory'}
          </Button>
        </div>

        {/* Add Memory Card */}
        {showAddForm && (
          <Card
            title="Record New Architecture Decision or Project Knowledge"
            style={{ marginBottom: '16px', border: '1px solid #a7f3d0', background: '#f0fdf4' }}
            size="small"
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '180px 1fr', gap: '10px' }}>
                <Select value={category} onChange={(val) => setCategory(val as MemoryCategory)}>
                  <Option value="ADR">🏛️ ADR (Decision)</Option>
                  <Option value="CONVENTION">📏 Convention</Option>
                  <Option value="INSIGHT">💡 Insight</Option>
                  <Option value="LESSON">📝 Lesson</Option>
                </Select>
                <Input
                  placeholder="Title (e.g., Mandatory UUIDv4 for all primary keys)"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </div>

              <TextArea
                rows={3}
                placeholder="Full context, rationale, guidelines, or consequences..."
                value={content}
                onChange={(e) => setContent(e.target.value)}
              />

              <Input
                placeholder="Tags comma separated (e.g. database, sqlite, security)"
                value={tagsStr}
                onChange={(e) => setTagsStr(e.target.value)}
              />

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                <Button onClick={() => setShowAddForm(false)}>Cancel</Button>
                <Button
                  type="primary"
                  loading={submitting}
                  onClick={handleCreate}
                  style={{ background: '#10b981', borderColor: '#10b981' }}
                >
                  Save Knowledge Memory
                </Button>
              </div>
            </div>
          </Card>
        )}

        {/* Prompt Preview Modal */}
        {showPromptPreview && (
          <Card
            title={
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Space>
                  <CodeOutlined style={{ color: '#6366f1' }} />
                  <Text strong>LLM System Prompt Injection Preview</Text>
                </Space>
                <Button
                  size="small"
                  icon={copied ? <CheckOutlined /> : <CopyOutlined />}
                  onClick={copyPromptToClipboard}
                >
                  {copied ? 'Copied' : 'Copy Prompt'}
                </Button>
              </div>
            }
            style={{ marginBottom: '16px', background: '#f8fafc', border: '1px solid #cbd5e1' }}
            size="small"
          >
            <Paragraph type="secondary" style={{ fontSize: '12px' }}>
              This markdown block is automatically injected into every agent prompt running on project <b>{selectedProjectId}</b>:
            </Paragraph>
            <pre
              style={{
                background: '#1e293b',
                color: '#e2e8f0',
                padding: '12px',
                borderRadius: '6px',
                fontSize: '12px',
                maxHeight: '220px',
                overflowY: 'auto',
              }}
            >
              {contextPrompt || 'No memories found for this project.'}
            </pre>
            <div style={{ textAlign: 'right', marginTop: '6px' }}>
              <Button size="small" onClick={() => setShowPromptPreview(false)}>
                Dismiss
              </Button>
            </div>
          </Card>
        )}

        {/* Memories List */}
        {loading ? (
          <div style={{ textAlign: 'center', padding: '60px' }}>
            <Spin size="large" />
          </div>
        ) : memories.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px', color: '#9ca3af' }}>
            <BookOutlined style={{ fontSize: '32px', marginBottom: '8px' }} />
            <div>No shared knowledge items recorded yet for this category.</div>
          </div>
        ) : (
          <List
            grid={{ gutter: 12, column: 1 }}
            dataSource={memories}
            renderItem={(item) => (
              <List.Item>
                <Card
                  size="small"
                  style={{
                    borderRadius: '8px',
                    border: '1px solid #e2e8f0',
                    boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
                  }}
                  title={
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <Space>
                        <Tag color={getCategoryColor(item.category)}>{item.category}</Tag>
                        <Text strong style={{ fontSize: '14px' }}>
                          {item.title}
                        </Text>
                      </Space>
                      <Popconfirm
                        title="Delete this knowledge item?"
                        onConfirm={() => handleDelete(item.id)}
                        okText="Delete"
                        cancelText="Cancel"
                      >
                        <Button type="text" danger icon={<DeleteOutlined />} size="small" />
                      </Popconfirm>
                    </div>
                  }
                >
                  <div style={{ fontSize: '13px', color: '#334155', whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>
                    {item.content}
                  </div>
                  {item.tags && item.tags.length > 0 && (
                    <div style={{ marginTop: '10px', display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                      {item.tags.map((tag) => (
                        <Tag key={tag} style={{ fontSize: '11px', background: '#f1f5f9' }}>
                          #{tag}
                        </Tag>
                      ))}
                    </div>
                  )}
                  <div style={{ marginTop: '8px', fontSize: '11px', color: '#94a3b8', textAlign: 'right' }}>
                    Saved on {new Date(item.created_at).toLocaleDateString()}
                  </div>
                </Card>
              </List.Item>
            )}
          />
        )}
      </div>
    </Modal>
  );
};

export default ProjectSharedMemoryModal;

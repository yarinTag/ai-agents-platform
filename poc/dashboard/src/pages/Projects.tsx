import React, { useEffect, useState } from 'react';
import {
  Table,
  Form,
  Input,
  Button,
  Modal,
  message,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, FolderOpenOutlined } from '@ant-design/icons';
import { Project } from '../types/project';
import { getProjects, createProject, updateProject, deleteProject } from '../services/api';
import ProjectSharedMemoryModal from '../components/memory/ProjectSharedMemoryModal';

export const ProjectsPage: React.FC = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [visible, setVisible] = useState<boolean>(false);
  const [form] = Form.useForm();
  const [editingKey, setEditingKey] = useState<string>('');
  const [selectedMemoryProject, setSelectedMemoryProject] = useState<string>('');
  const [memoryModalVisible, setMemoryModalVisible] = useState<boolean>(false);

  const fetchProjects = async () => {
    try {
      setLoading(true);
      const response = await getProjects();
      setProjects(response.data || []);
    } catch (err) {
      console.error(err);
      message.error('Failed to load projects');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
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
        await updateProject(editingKey, values);
        message.success('Project updated successfully');
      } else {
        await createProject(values);
        message.success('Project created successfully');
      }
      setVisible(false);
      fetchProjects();
    } catch (err) {
      message.error('Failed to save project');
      console.error(err);
    }
  };

  const columns = [
    {
      title: 'Project Name',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => (
        <span style={{ fontWeight: 600, color: '#f3f4f6' }}>
          📁 {name}
        </span>
      ),
    },
    {
      title: 'Working Directory',
      dataIndex: 'working_directory',
      key: 'working_directory',
      render: (dir: string) => (
        <span style={{ color: '#58a6ff', fontSize: '12px' }}>
          <FolderOpenOutlined style={{ marginRight: '6px' }} />
          {dir || 'Default'}
        </span>
      ),
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      render: (desc: string) => <span style={{ color: '#8b949e' }}>{desc || 'N/A'}</span>,
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, record: Project) => (
        <div style={{ display: 'flex', gap: '8px' }}>
          <Button
            size="small"
            style={{ borderColor: '#10b981', color: '#059669' }}
            onClick={() => {
              setSelectedMemoryProject(record.id);
              setMemoryModalVisible(true);
            }}
          >
            🧠 Shared Memory
          </Button>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => {
              form.setFieldsValue({
                name: record.name,
                description: record.description,
                working_directory: record.working_directory,
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
              deleteProject(record.id)
                .then(() => {
                  message.success('Project deleted');
                  fetchProjects();
                })
                .catch((err) => {
                  message.error('Failed to delete project');
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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h2 style={{ margin: 0, color: '#f3f4f6', fontSize: '22px', fontWeight: 700 }}>
            📁 Workspaces & Projects
          </h2>
          <span style={{ color: '#9ca3af', fontSize: '13px' }}>
            Root workspaces and directory boundaries for agent operations
          </span>
        </div>

        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate} style={{ background: '#238636', borderColor: '#238636' }}>
          Add Project
        </Button>
      </div>

      <Table
        loading={loading}
        rowKey="id"
        columns={columns}
        dataSource={projects}
        pagination={false}
      />

      <Modal
        title={editingKey ? 'Edit Project' : 'Add Project'}
        open={visible}
        onOk={handleOk}
        onCancel={() => setVisible(false)}
      >
        <Form form={form} layout="vertical">
          <Form.Item label="Name" name="name" rules={[{ required: true, message: 'Please input project name!' }]}>
            <Input placeholder="e.g. SmartTrader App" />
          </Form.Item>
          <Form.Item label="Working Directory" name="working_directory">
            <Input placeholder="C:\Users\taguo\Desktop\ai-agents-platform" />
          </Form.Item>
          <Form.Item label="Description" name="description">
            <Input.TextArea rows={3} placeholder="Project scope and guidelines" />
          </Form.Item>
        </Form>
      </Modal>

      <ProjectSharedMemoryModal
        open={memoryModalVisible}
        onClose={() => setMemoryModalVisible(false)}
        defaultProjectId={selectedMemoryProject}
      />
    </div>
  );
};

export default ProjectsPage;

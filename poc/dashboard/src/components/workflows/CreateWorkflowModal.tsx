import { ResourceWarning } from '../common/ResourceWarning';
import React from 'react';
import { Modal, Tabs, Form, Input, Button, Checkbox, Tag, Radio } from 'antd';
import { ThunderboltOutlined, CodeOutlined, ApartmentOutlined, SendOutlined, SlackOutlined, RocketOutlined, ToolOutlined, FileTextOutlined, GithubOutlined, FolderOpenOutlined } from '@ant-design/icons';

import type { CreateWorkflowModalProps } from './workflowBuilderTypes';
import { useWorkflowBuilder } from './useWorkflowBuilder';
import { WorkflowGeneratorPanel } from './WorkflowGeneratorPanel';
import { WorkflowDiagramPanel } from './WorkflowDiagramPanel';
import { WorkflowStepsPanel } from './WorkflowStepsPanel';
import { WorkflowYamlPanel } from './WorkflowYamlPanel';
export type { WorkflowStep, AttachedSkill } from './workflowBuilderTypes';

export const CreateWorkflowModal: React.FC<CreateWorkflowModalProps> = (props) => {
  const model = useWorkflowBuilder(props);
  const {
    open, onClose, activeTab, setActiveTab, saving,
    channelProvider, channelId, allowedMcps, workflowSkills,
    createSkillModalOpen, setCreateSkillModalOpen, newSkillForm, creatingSkill, steps,
    handleCreateNewSkill, handleSaveWorkflow,
  } = model;
  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <RocketOutlined style={{ color: '#38bdf8', fontSize: '20px' }} />
          <div>
            <span style={{ fontSize: '16px', fontWeight: 800, color: '#f0f6fc' }}>
              Create Workflow, Canvas DAG & Auto YAML Playbook
            </span>
            <div style={{ fontSize: '12px', color: '#8b949e', fontWeight: 400 }}>
              Design multi-agent DAG pipelines restricted strictly to configured MCPs with attached skills
            </div>
          </div>
        </div>
      }
      open={open}
      onCancel={onClose}
      width={1000}
      footer={[
        <div key="summary" style={{ float: 'left', display: 'flex', alignItems: 'center', gap: '8px', paddingTop: '4px' }}>
          <Tag color="cyan">{steps.length} Steps in DAG</Tag>
          <Tag color="purple"><ToolOutlined /> {allowedMcps.length} MCPs</Tag>
          <Tag color="gold"><FileTextOutlined /> {workflowSkills.length} Skills</Tag>
          {channelProvider && channelId && (
            <Tag color={channelProvider === 'telegram' ? 'blue' : 'gold'}>
              {channelProvider === 'telegram' ? <SendOutlined /> : <SlackOutlined />} {channelId}
            </Tag>
          )}
        </div>,
        <Button key="cancel" onClick={onClose} style={{ background: '#161b22', borderColor: '#30363d', color: '#8b949e' }}>
          Cancel
        </Button>,
        <Button
          key="save"
          type="primary"
          icon={<ThunderboltOutlined />}
          loading={saving}
          disabled={model.resourcesUnavailable}
          onClick={handleSaveWorkflow}
          style={{ background: '#059669', borderColor: '#059669', fontWeight: 700 }}
        >
          Deploy & Save Workflow
        </Button>,
      ]}
    >
      <ResourceWarning errors={[model.connectorError, model.skillsError]} onRetry={model.reloadResources} />
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'ai',
            label: (
              <span style={{ fontWeight: 600 }}>
                <ThunderboltOutlined style={{ color: '#38bdf8' }} /> 1. AI & MCP Scope (Quick Generator & MCP Setup)
              </span>
            ),
            children: (
              <WorkflowGeneratorPanel model={model} />
            ),
          },
          {
            key: 'canvas',
            label: (
              <span style={{ fontWeight: 600 }}>
                <ApartmentOutlined style={{ color: '#10b981' }} /> 2. Workflow Canvas (Visual Flow)
              </span>
            ),
            children: (
              <WorkflowDiagramPanel model={model} />
            ),
          },
          {
            key: 'builder',
            label: (
              <span style={{ fontWeight: 600 }}>
                <ToolOutlined style={{ color: '#a855f7' }} /> 3. Visual Step & Skill Builder (Steps & Skills)
              </span>
            ),
            children: (
              <WorkflowStepsPanel model={model} />
            ),
          },
          {
            key: 'yaml',
            label: (
              <span style={{ fontWeight: 600 }}>
                <CodeOutlined style={{ color: '#f59e0b' }} /> 4. Live YAML Playbook (Generated YAML File)
              </span>
            ),
            children: (
              <WorkflowYamlPanel model={model} />
            ),
          },
        ]}
      />

      {/* Modal to Create New Skill with Git / Local repo location */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileTextOutlined style={{ color: '#f59e0b' }} />
            <span>Create New Skill for Workflow (Define New Skill with Repo Location)</span>
          </div>
        }
        open={createSkillModalOpen}
        onCancel={() => setCreateSkillModalOpen(false)}
        onOk={() => newSkillForm.submit()}
        confirmLoading={creatingSkill}
        okText="Add Skill to Workflow"
      >
        <Form
          form={newSkillForm}
          layout="vertical"
          onFinish={handleCreateNewSkill}
          initialValues={{ source: 'git', save_to_library: true }}
        >
          <Form.Item
            name="name"
            label={<span style={{ color: '#f0f6fc' }}>Skill Name</span>}
            rules={[{ required: true, message: 'Skill name is required' }]}
          >
            <Input placeholder="e.g., Daily Git Reporter" style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }} />
          </Form.Item>

          <Form.Item
            name="source"
            label={<span style={{ color: '#f0f6fc' }}>Skill Source Type</span>}
          >
            <Radio.Group>
              <Radio value="git" style={{ color: '#f0f6fc' }}><GithubOutlined /> Git Repository</Radio>
              <Radio value="local" style={{ color: '#f0f6fc' }}><FolderOpenOutlined /> Local Filesystem Path</Radio>
              <Radio value="custom" style={{ color: '#f0f6fc' }}>Inline Instructions</Radio>
            </Radio.Group>
          </Form.Item>

          <Form.Item
            name="location"
            label={<span style={{ color: '#f0f6fc' }}>Repository / Path Location (Repo or Local Path)</span>}
            tooltip="URL of Git repo (e.g. https://github.com/my-org/skills.git) or local path (e.g. /Users/.../skills/my-skill)"
          >
            <Input
              placeholder="e.g. https://github.com/yarinTag/ai-agents-platform.git or /path/to/skill"
              style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
            />
          </Form.Item>

          <Form.Item
            name="description"
            label={<span style={{ color: '#f0f6fc' }}>Description</span>}
          >
            <Input placeholder="Brief explanation of what this skill does" style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }} />
          </Form.Item>

          <Form.Item
            name="content"
            label={<span style={{ color: '#f0f6fc' }}>Skill Instructions / Prompt Specification</span>}
          >
            <Input.TextArea
              rows={3}
              placeholder="# Instructions for agent when using this skill..."
              style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
            />
          </Form.Item>

          <Form.Item name="save_to_library" valuePropName="checked">
            <Checkbox style={{ color: '#8b949e' }}>Also save skill to platform library for other workflows</Checkbox>
          </Form.Item>
        </Form>
      </Modal>
    </Modal>
  );
};

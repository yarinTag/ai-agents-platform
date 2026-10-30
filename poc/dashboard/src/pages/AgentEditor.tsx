import { Form, Input, Button, Modal, Select, InputNumber, message } from 'antd';
import { FolderOpenOutlined } from '@ant-design/icons';
import { Agent } from '../types/agent';
import { CharacterSelector } from '../components/agents/CharacterSelector';
import FolderPickerModal from '../components/common/FolderPickerModal';
import { ModelSelector } from '../components/robotic';

import type { useAgentsPage } from './useAgentsPage';

export const AgentEditor = (props: Pick<
  ReturnType<typeof useAgentsPage>,
  | 'departments'
  | 'availableSkills'
  | 'visible'
  | 'setVisible'
  | 'folderPickerVisible'
  | 'setFolderPickerVisible'
  | 'form'
  | 'editingKey'
  | 'departmentOptions'
  | 'handleOk'
  | 'eligibleManagers'
>) => {
  const {
    departments,
    availableSkills,
    visible,
    setVisible,
    folderPickerVisible,
    setFolderPickerVisible,
    form,
    editingKey,
    departmentOptions,
    handleOk,
    eligibleManagers,
  } = props;
  return (<>
      {/* Agent Create / Edit Modal */}
      <Modal
        title={editingKey ? 'Edit Agent Profile & Hierarchy' : 'Create Autonomous Agent'}
        open={visible}
        onOk={handleOk}
        onCancel={() => setVisible(false)}
        width={720}
        okText={editingKey ? 'Save Changes' : 'Deploy Agent'}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <Form.Item
              name="name"
              label="Agent Name"
              rules={[{ required: true, message: 'Agent name is required' }]}
            >
              <Input placeholder="e.g. Lead Architect" />
            </Form.Item>

            <Form.Item
              name="department_id"
              label="Department"
              help="Assign agent to an enterprise department for budget and tool governance"
            >
              <Select
                showSearch
                allowClear
                placeholder="Select enterprise department"
                options={departmentOptions}
                onChange={(val) => {
                  const matched = departments.find((d) => d.id === val || d.name === val);
                  if (matched) {
                    form.setFieldsValue({
                      department_id: matched.id,
                      department: matched.name,
                    });
                  } else if (val) {
                    form.setFieldsValue({
                      department: val,
                    });
                  }
                }}
              />
            </Form.Item>
            <Form.Item name="department" hidden>
              <Input />
            </Form.Item>
            <Form.Item name="organization_id" hidden>
              <Input />
            </Form.Item>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <Form.Item
              name="role_type"
              label="Role & Delegation Authority"
              rules={[{ required: true, message: 'Role is required' }]}
            >
              <Select>
                <Select.Option value="ROOT_ORCHESTRATOR">👑 ROOT_ORCHESTRATOR (Top Executive)</Select.Option>
                <Select.Option value="MANAGER">⭐ MANAGER (Can Supervise & Delegate)</Select.Option>
                <Select.Option value="WORKER">💻 WORKER (Task Executor)</Select.Option>
                <Select.Option value="SPECIALIST">🛡️ SPECIALIST (Domain Expert)</Select.Option>
              </Select>
            </Form.Item>

            <Form.Item
              noStyle
              shouldUpdate={(prev, curr) => prev.role_type !== curr.role_type}
            >
              {({ getFieldValue }) => {
                const role = getFieldValue('role_type');
                if (role === 'ROOT_ORCHESTRATOR') {
                  return (
                    <Form.Item label="Reports To">
                      <Input disabled value="None (Top Level Root)" />
                    </Form.Item>
                  );
                }
                return (
                  <Form.Item
                    name="parent_id"
                    label="Supervisor (Reports To)"
                    help="Manager supervising this agent"
                  >
                    <Select placeholder="Select Manager" allowClear>
                      {eligibleManagers.map((m) => (
                        <Select.Option key={m.id} value={m.id}>
                          ⭐ {m.name} ({m.role_type})
                        </Select.Option>
                      ))}
                    </Select>
                  </Form.Item>
                );
              }}
            </Form.Item>
          </div>

          <Form.Item
            noStyle
            shouldUpdate={(prev, curr) => prev.role_type !== curr.role_type}
          >
            {({ getFieldValue }) => {
              const role = getFieldValue('role_type');
              if (role === 'MANAGER' || role === 'ROOT_ORCHESTRATOR') {
                return (
                  <Form.Item
                    name="max_concurrent_children"
                    label="Max Concurrent Subtasks"
                    help="Limit on parallel delegated tasks this manager can run simultaneously"
                  >
                    <InputNumber min={1} max={20} style={{ width: '100%' }} />
                  </Form.Item>
                );
              }
              return null;
            }}
          </Form.Item>

          <Form.Item name="description" label="Short Role Description">
            <Input placeholder="Coordinates frontend implementation and design system compliance" />
          </Form.Item>

          <Form.Item
            name="system_prompt"
            label="System Instructions (Prompt)"
            rules={[{ required: true, message: 'System prompt is required' }]}
          >
            <Input.TextArea
              rows={4}
              placeholder="You are an autonomous AI Agent. Execute tasks with precision..."
            />
          </Form.Item>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <Form.Item name="model" label="AI Model">
              <ModelSelector placeholder="Select AI Model..." />
            </Form.Item>

            <Form.Item
              name="skills"
              label="Equipped Skills"
              help="Select skills from your local skills repository to equip this agent"
            >
              <Select
                mode="multiple"
                allowClear
                showSearch
                placeholder="Search and equip skills (e.g. api-design, systematic-debugger)"
                options={availableSkills}
                filterOption={(input, option) => {
                  const labelStr = typeof option?.label === 'string' ? option.label : String(option?.value || '');
                  return (
                    labelStr.toLowerCase().includes(input.toLowerCase()) ||
                    String(option?.value || '').toLowerCase().includes(input.toLowerCase()) ||
                    String(option?.title || '').toLowerCase().includes(input.toLowerCase())
                  );
                }}
              />
            </Form.Item>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <Form.Item name="repo_path" label="Local Repository Path">
              <Input
                placeholder="/path/to/my-repo"
                addonAfter={
                  <Button
                    type="link"
                    size="small"
                    icon={<FolderOpenOutlined />}
                    onClick={() => setFolderPickerVisible(true)}
                    style={{ padding: '0 6px', color: '#38bdf8' }}
                  >
                    Browse...
                  </Button>
                }
              />
            </Form.Item>
            <Form.Item name="github_url" label="GitHub URL">
              <Input placeholder="https://github.com/org/repo" />
            </Form.Item>
          </div>

          {/* Character / Avatar Selector */}
          <Form.Item name="avatar" label="Pixel Art Office Avatar">
            <CharacterSelector />
          </Form.Item>
        </Form>
      </Modal>

      <FolderPickerModal
        open={folderPickerVisible}
        onClose={() => setFolderPickerVisible(false)}
        onSelect={(path) => form.setFieldsValue({ repo_path: path })}
        title="📁 Select Agent Local Repository Folder"
      />


  </>);
};

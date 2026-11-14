import { usePermissions } from '../hooks/usePermissions';
import { useAuth } from '../context/AuthContext';
import { usePluginSourceText } from '../i18n/pluginSource';
import React, { useState } from 'react';
import { Form, Input, Button, Modal, Tag, message, Select, Segmented, Space } from 'antd';
import { PlusOutlined, SyncOutlined, CopyOutlined } from '@ant-design/icons';
import { Skill } from '../types/skill';
import FolderPickerModal from '../components/common/FolderPickerModal';

import { useSkillsPage } from './useSkillsPage';
import { SkillsCatalogTabs } from './SkillsCatalogTabs';

export const SkillsPage: React.FC = () => {
  const { isAdmin } = usePermissions();
  const { activeDepartmentId } = useAuth();
  const text = usePluginSourceText();
  const [scope, setScope] = useState<'organization' | 'department'>('department');
  const departmentId = !isAdmin || scope === 'department' ? activeDepartmentId : null;
  return <Space orientation="vertical" style={{ width: '100%' }}>
    {isAdmin && activeDepartmentId && <Segmented<'organization' | 'department'> aria-label={text.scope} value={scope}
      onChange={setScope} options={[
        { value: 'organization', label: text.organization },
        { value: 'department', label: text.department },
      ]} />}
    <SkillsScope key={departmentId ?? 'organization'} departmentId={departmentId} />
  </Space>;
};

function SkillsScope({ departmentId }: { departmentId: string | null }) {
  const { isAdmin } = usePermissions();
  const model = useSkillsPage(departmentId);
  const {
    skills,
    plugins,
    scanning,
    visible,
    setVisible,
    form,
    editingKey,
    selectedPluginSkill,
    setSelectedPluginSkill,
    skillContent,
    loadingContent,
    localPath,
    setLocalPath,
    folderPickerOpen,
    setFolderPickerOpen,
    loadConfigAndScan,
    handleCreate,
    handleOk,
  } = model;
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
            onClick={() => loadConfigAndScan(true)}
            style={{ background: '#21262d', color: '#c9d1d9', borderColor: '#30363d' }}
          >
            Rescan Plugins
          </Button>
          <Button type="primary" icon={<PlusOutlined />} disabled={!isAdmin} onClick={handleCreate} style={{ background: '#238636', borderColor: '#238636' }}>
            Create Custom Skill
          </Button>
        </div>
      </div>

      <SkillsCatalogTabs {...model} />

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

      {/* Folder Picker Modal for Local Plugins */}
      <FolderPickerModal
        open={folderPickerOpen}
        onClose={() => setFolderPickerOpen(false)}
        onSelect={(selectedPath) => {
          setLocalPath(selectedPath);
          setFolderPickerOpen(false);
        }}
        initialPath={localPath}
        title="📁 Select Plugins Directory"
      />
    </div>
  );
};
export default SkillsPage;

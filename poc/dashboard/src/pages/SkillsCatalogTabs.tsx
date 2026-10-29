import { ResourceSection } from './ResourceSection';
import { PluginSourceConfiguration } from './PluginSourceConfiguration';
import { Table, Input, Button, Tag, Tabs, Segmented, Select } from 'antd';
import { DeleteOutlined, AppstoreOutlined, FolderOpenOutlined, FileTextOutlined, SyncOutlined, ThunderboltOutlined, CheckCircleOutlined, GithubOutlined, SaveOutlined, DownSquareOutlined, UpSquareOutlined, LockOutlined, UnlockOutlined, BranchesOutlined, KeyOutlined, LinkOutlined } from '@ant-design/icons';
import { CollapsiblePluginCard } from '../components/robotic';

import type { useSkillsPage } from './useSkillsPage';

export const SkillsCatalogTabs = (props: Pick<
  ReturnType<typeof useSkillsPage>,
  | 'sourceConfigError'
  | 'scanError'
  | 'skills'
  | 'plugins'
  | 'loading'
  | 'scanning'
  | 'savingConfig'
  | 'setSelectedPluginSkill'
  | 'sourceMode'
  | 'setSourceMode'
  | 'localPath'
  | 'setLocalPath'
  | 'gitRepo'
  | 'setGitRepo'
  | 'setFolderPickerOpen'
  | 'collapsedPluginNames'
  | 'gitRepos'
  | 'loadingGitRepos'
  | 'hasGitToken'
  | 'manualGitToken'
  | 'setManualGitToken'
  | 'showTokenInput'
  | 'fetchGitRepos'
  | 'loadConfigAndScan'
  | 'handleSaveAndSync'
  | 'handleClearSource'
  | 'isAllCollapsed'
  | 'handleToggleExpandAll'
  | 'handleTogglePluginCollapse'
  | 'handleSelectSkill'
  | 'columns'
>) => {
  const {
    sourceConfigError,
    scanError,
    skills,
    plugins,
    loading,
    scanning,
    savingConfig,
    setSelectedPluginSkill,
    sourceMode,
    setSourceMode,
    localPath,
    setLocalPath,
    gitRepo,
    setGitRepo,
    setFolderPickerOpen,
    collapsedPluginNames,
    gitRepos,
    loadingGitRepos,
    hasGitToken,
    manualGitToken,
    setManualGitToken,
    showTokenInput,
    fetchGitRepos,
    loadConfigAndScan,
    handleSaveAndSync,
    handleClearSource,
    isAllCollapsed,
    handleToggleExpandAll,
    handleTogglePluginCollapse,
    handleSelectSkill,
    columns,
  } = props;
  return (<>
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
              <ResourceSection error={sourceConfigError || scanError} onRetry={() => loadConfigAndScan(false)}>
              <div>
                <PluginSourceConfiguration {...props} />

                {/* Connected Repository Status & Toolbar */}
                <div
                  style={{
                    background: '#161b22',
                    padding: '12px 18px',
                    borderRadius: '8px',
                    border: '1px solid #30363d',
                    marginBottom: '18px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: '10px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                    <CheckCircleOutlined style={{ color: plugins.length > 0 ? '#52c41a' : '#8b949e', fontSize: '18px' }} />
                    <div>
                      <span style={{ color: '#f3f4f6', fontWeight: 600, fontSize: '13px' }}>
                        Active {sourceMode === 'local' ? 'Local' : 'Git'} Source:
                      </span>{' '}
                      <code style={{ color: '#58a6ff', background: '#0d1117', padding: '2px 8px', borderRadius: '4px', fontSize: '12px' }}>
                        {sourceMode === 'local'
                          ? (localPath.trim() || 'None (No local directory configured)')
                          : (gitRepo.trim() || 'None (No Git repository selected)')}
                      </code>
                    </div>
                    <Tag color={plugins.length > 0 ? 'green' : 'default'} style={{ margin: 0, padding: '2px 10px', fontSize: '12px' }}>
                      {plugins.reduce((acc, p) => acc + p.skills_count, 0)} Skills Active
                    </Tag>
                  </div>

                  {plugins.length > 0 && (
                    <Button
                      size="small"
                      icon={isAllCollapsed ? <DownSquareOutlined /> : <UpSquareOutlined />}
                      onClick={handleToggleExpandAll}
                      style={{ background: '#0d1117', borderColor: '#30363d', color: '#8b949e' }}
                    >
                      {isAllCollapsed ? 'Expand All' : 'Collapse All'}
                    </Button>
                  )}
                </div>

                {/* Plugin Packages List with per-card expand/collapse */}
                {plugins.length === 0 ? (
                  <div
                    style={{
                      background: '#161b22',
                      border: '1px dashed #30363d',
                      borderRadius: '10px',
                      padding: '36px 24px',
                      textAlign: 'center',
                      color: '#8b949e',
                    }}
                  >
                    <div style={{ fontSize: '15px', fontWeight: 600, color: '#c9d1d9', marginBottom: '6px' }}>
                      {sourceMode === 'local'
                        ? (localPath.trim() ? 'No skills found in the selected local directory' : 'No local directory configured')
                        : (gitRepo.trim() ? 'No skills found in the selected Git repository' : 'No Git repository selected')}
                    </div>
                    <div style={{ fontSize: '12px' }}>
                      {sourceMode === 'local'
                        ? 'Choose a local folder above and click "Save & Scan Local" to load local plugin skills.'
                        : 'Select a Git repository from the dropdown above and click "Save & Sync from Git" to load repository skills.'}
                    </div>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {plugins.map((plugin) => {
                      const isCollapsed = collapsedPluginNames.has(plugin.name);
                      return (
                        <CollapsiblePluginCard
                          key={plugin.name}
                          title={plugin.display_name || plugin.name.toUpperCase()}
                          version={plugin.version}
                          domain={plugin.domain}
                          skillsCount={plugin.skills_count}
                          path={plugin.path}
                          isCollapsed={isCollapsed}
                          onToggleCollapse={() => handleTogglePluginCollapse(plugin.name)}
                          extra={
                            <Button
                              type="text"
                              size="small"
                              style={{ color: '#58a6ff', fontSize: '12px', padding: '0 4px' }}
                              onClick={() => handleTogglePluginCollapse(plugin.name)}
                            >
                              {isCollapsed ? 'Expand' : 'Collapse'}
                            </Button>
                          }
                        >
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
                        </CollapsiblePluginCard>
                      );
                    })}
                  </div>
                )}
              </div>
              </ResourceSection>
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
                scroll={{ x: 900 }}
              />
            ),
          },
        ]}
      />


  </>);
};

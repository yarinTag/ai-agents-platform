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
  Segmented,
  Select,
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
  DownOutlined,
  RightOutlined,
  GithubOutlined,
  SaveOutlined,
  DownSquareOutlined,
  UpSquareOutlined,
  LockOutlined,
  UnlockOutlined,
  BranchesOutlined,
  KeyOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import { Skill, PluginPackage, PluginsConfig } from '../types/skill';
import {
  getSkills,
  createSkill,
  updateSkill,
  deleteSkill,
  scanPlugins,
  getPluginsConfig,
  updatePluginsConfig,
  getPluginGitRepos,
  discoverMCPResources,
  getPluginSkillContent,
} from '../services/api';
import FolderPickerModal from '../components/common/FolderPickerModal';
import { CollapsiblePluginCard } from '../components/robotic';


export const SkillsPage: React.FC = () => {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [plugins, setPlugins] = useState<PluginPackage[]>([]);
  const [marketplacePath, setMarketplacePath] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [scanning, setScanning] = useState<boolean>(false);
  const [savingConfig, setSavingConfig] = useState<boolean>(false);
  const [visible, setVisible] = useState<boolean>(false);
  const [form] = Form.useForm();
  const [editingKey, setEditingKey] = useState<string>('');
  const [selectedPluginSkill, setSelectedPluginSkill] = useState<any>(null);
  const [skillContent, setSkillContent] = useState<string>('');
  const [loadingContent, setLoadingContent] = useState<boolean>(false);
  const hasScannedRef = useRef<boolean>(false);

  // Plugin Source Configuration State
  const [sourceMode, setSourceMode] = useState<'local' | 'git'>('local');
  const [localPath, setLocalPath] = useState<string>('');
  const [gitRepo, setGitRepo] = useState<string>('');
  const [folderPickerOpen, setFolderPickerOpen] = useState<boolean>(false);

  // Expand / Collapse State for Plugin Cards
  const [collapsedPluginNames, setCollapsedPluginNames] = useState<Set<string>>(new Set());

  // Git Repositories discovery for plugins
  const [gitRepos, setGitRepos] = useState<any[]>([]);
  const [loadingGitRepos, setLoadingGitRepos] = useState<boolean>(false);
  const [hasGitToken, setHasGitToken] = useState<boolean | null>(null);
  const [manualGitToken, setManualGitToken] = useState<string>('');
  const [showTokenInput, setShowTokenInput] = useState<boolean>(false);

  const fetchGitRepos = async (overrideToken?: string) => {
    try {
      setLoadingGitRepos(true);
      const token = overrideToken !== undefined ? overrideToken.trim() : manualGitToken.trim();
      const res = await getPluginGitRepos(token || undefined);
      const repos = res.data?.repositories || [];
      const hasToken = Boolean(res.data?.has_token);
      setGitRepos(repos);
      setHasGitToken(hasToken);
      setShowTokenInput(!hasToken);

      if (repos.length > 0) {
        message.success(`Loaded ${repos.length} Git repositories`);
      } else if (!hasToken) {
        message.info('No Git token detected. Please paste your GitHub / GitLab token below.');
      }
    } catch (err: any) {
      console.warn('getPluginGitRepos failed, falling back to discoverMCPResources', err);
      try {
        const token = overrideToken !== undefined ? overrideToken.trim() : manualGitToken.trim();
        const fallbackRes = await discoverMCPResources('github', token || undefined);
        const repos = fallbackRes.data?.repositories || [];
        setGitRepos(repos);
        setHasGitToken(repos.length > 0);
        setShowTokenInput(repos.length === 0);
        if (repos.length > 0) {
          message.success(`Loaded ${repos.length} repositories`);
        }
      } catch (fErr: any) {
        message.error(`Failed to load repositories: ${fErr?.response?.data?.detail || fErr?.message || 'Error loading repos'}`);
      }
    } finally {
      setLoadingGitRepos(false);
    }
  };

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

  const loadConfigAndScan = async (
    isManual: boolean = false,
    overrides?: { mode?: 'local' | 'git'; localPath?: string; gitRepo?: string }
  ) => {
    try {
      setScanning(true);
      let mode: 'local' | 'git' = overrides?.mode ?? sourceMode;
      let lPath = overrides?.localPath !== undefined ? overrides.localPath : localPath;
      let gRepo = overrides?.gitRepo !== undefined ? overrides.gitRepo : gitRepo;

      // On initial load, read current saved config from backend
      if (!isManual && !overrides) {
        try {
          const cfgRes = await getPluginsConfig();
          if (cfgRes.data) {
            mode = (cfgRes.data.source_mode as 'local' | 'git') || 'local';
            lPath = cfgRes.data.local_path || '';
            gRepo = cfgRes.data.git_repo || '';
            setSourceMode(mode);
            setLocalPath(lPath);
            setGitRepo(gRepo);
          }
        } catch (e) {
          throw e;
        }
      }

      if (mode === 'git' && gitRepos.length === 0) {
        fetchGitRepos();
      }

      const scanParams: { source_mode: 'local' | 'git'; local_path?: string; git_repo?: string } = {
        source_mode: mode,
        ...(mode === 'local' ? { local_path: lPath.trim() } : { git_repo: gRepo.trim() }),
      };

      const res = await scanPlugins(scanParams, isManual);
      if (res.data && Array.isArray(res.data.plugins)) {
        setPlugins(res.data.plugins);
        setMarketplacePath(res.data.marketplace_path || '');
        if (isManual) {
          const activeTarget = mode === 'local' ? lPath.trim() : gRepo.trim();
          if (!activeTarget) {
            message.info(`No ${mode === 'local' ? 'local path' : 'Git repository'} selected.`);
          } else {
            message.success(`Discovered ${res.data.total_skills} skills across ${res.data.plugins.length} plugin packages!`);
          }
        }
      } else {
        setPlugins([]);
        setMarketplacePath('');
      }
    } catch (err: any) {
      console.error('Plugin scan failed', err);
      if (isManual) {
        message.error(`Plugin scan failed: ${err?.response?.data?.detail || err?.message || 'Unable to scan plugins'}`);
      }
      setPlugins([]);
      setMarketplacePath('');
    } finally {
      setScanning(false);
    }
  };

  const handleSaveAndSync = async () => {
    try {
      setSavingConfig(true);
      const payload = {
        source_mode: sourceMode,
        ...(sourceMode === 'local' ? { local_path: localPath.trim() } : { git_repo: gitRepo.trim() }),
      };
      await updatePluginsConfig(payload);
      await loadConfigAndScan(true, { mode: sourceMode, localPath, gitRepo });
    } catch (err: any) {
      console.error('Failed to save plugins configuration', err);
      message.error(`Failed to save configuration: ${err?.response?.data?.detail || err?.message || 'Error occurred'}`);
    } finally {
      setSavingConfig(false);
    }
  };

  const handleClearSource = async () => {
    try {
      setSavingConfig(true);
      setSelectedPluginSkill(null);
      if (sourceMode === 'local') {
        setLocalPath('');
        await updatePluginsConfig({ source_mode: 'local', local_path: '' });
        await loadConfigAndScan(true, { mode: 'local', localPath: '', gitRepo });
      } else {
        setGitRepo('');
        await updatePluginsConfig({ source_mode: 'git', git_repo: '' });
        await loadConfigAndScan(true, { mode: 'git', localPath, gitRepo: '' });
      }
    } catch (err: any) {
      message.error(`Failed to clear source: ${err?.response?.data?.detail || err?.message || 'Error occurred'}`);
    } finally {
      setSavingConfig(false);
    }
  };

  const isAllCollapsed = plugins.length > 0 && collapsedPluginNames.size === plugins.length;

  const handleToggleExpandAll = () => {
    if (isAllCollapsed) {
      setCollapsedPluginNames(new Set());
    } else {
      setCollapsedPluginNames(new Set(plugins.map((p) => p.name)));
    }
  };

  const handleTogglePluginCollapse = (pluginName: string) => {
    setCollapsedPluginNames((prev) => {
      const next = new Set(prev);
      if (next.has(pluginName)) {
        next.delete(pluginName);
      } else {
        next.add(pluginName);
      }
      return next;
    });
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
      loadConfigAndScan(false);
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
            onClick={() => loadConfigAndScan(true)}
            style={{ background: '#21262d', color: '#c9d1d9', borderColor: '#30363d' }}
          >
            Rescan Plugins
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
                {/* Plugin Source Configuration Bar */}
                <div
                  style={{
                    background: '#161b22',
                    border: '1px solid #30363d',
                    borderRadius: '10px',
                    padding: '16px 20px',
                    marginBottom: '16px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <FolderOpenOutlined style={{ color: '#10b981', fontSize: '18px' }} />
                      <span style={{ color: '#f3f4f6', fontWeight: 700, fontSize: '14px' }}>
                        Plugin Source Configuration
                      </span>
                      <span style={{ color: '#8b949e', fontSize: '12px' }}>
                        (Configure where agent plugins and marketplace skills are sourced from)
                      </span>
                    </div>
                    <Segmented
                      value={sourceMode}
                      onChange={async (val) => {
                        const next = val as 'local' | 'git';
                        setSourceMode(next);
                        setSelectedPluginSkill(null);
                        if (next === 'git' && gitRepos.length === 0) {
                          fetchGitRepos();
                        }
                        await loadConfigAndScan(false, { mode: next, localPath, gitRepo });
                      }}
                      options={[
                        { label: 'Local Directory', value: 'local', icon: <FolderOpenOutlined /> },
                        { label: 'Git Repository', value: 'git', icon: <GithubOutlined /> },
                      ]}
                      style={{ background: '#0d1117', border: '1px solid #30363d' }}
                    />
                  </div>

                  {sourceMode === 'local' ? (
                    <div>
                      <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
                        <div style={{ flex: 1, minWidth: '280px' }}>
                          <Input
                            allowClear
                            placeholder="Local plugins path, e.g. /Users/.../my-plugins (leave empty for none)"
                            value={localPath}
                            onChange={(e) => setLocalPath(e.target.value)}
                            style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }}
                            addonAfter={
                              <Button
                                type="text"
                                size="small"
                                icon={<FolderOpenOutlined />}
                                onClick={() => setFolderPickerOpen(true)}
                                style={{ color: '#38bdf8', padding: '0 6px', height: 'auto' }}
                              >
                                Browse...
                              </Button>
                            }
                          />
                        </div>
                        {localPath.trim() && (
                          <Button
                            danger
                            icon={<DeleteOutlined />}
                            loading={savingConfig || scanning}
                            onClick={handleClearSource}
                            style={{ background: '#21262d', borderColor: '#f85149', color: '#f85149' }}
                          >
                            Clear Path
                          </Button>
                        )}
                        <Button
                          type="primary"
                          icon={<SaveOutlined />}
                          loading={savingConfig || scanning}
                          onClick={handleSaveAndSync}
                          style={{ background: '#10b981', borderColor: '#10b981', fontWeight: 600 }}
                        >
                          Save & Scan Local
                        </Button>
                      </div>
                      <div style={{ color: '#8b949e', fontSize: '11px', marginTop: '6px' }}>
                        Displays <strong>only</strong> skills from the configured local directory (or none when no local path is set).
                      </div>
                    </div>
                  ) : (
                    <div>
                      <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
                        <div style={{ flex: 1, minWidth: '320px' }}>
                          <Select
                            showSearch
                            allowClear
                            placeholder="Select or search Git repository (leave empty for none)"
                            value={gitRepo || undefined}
                            onChange={(val) => setGitRepo(val || '')}
                            filterOption={(input, option) =>
                              (option?.searchValue || '').toLowerCase().includes(input.toLowerCase()) ||
                              (option?.value as string || '').toLowerCase().includes(input.toLowerCase())
                            }
                            options={[
                              ...gitRepos.map((repo: any) => {
                                const val = repo.clone_url || repo.path || repo.full_name;
                                const isPrivate = repo.private !== undefined ? Boolean(repo.private) : false;
                                const branch = repo.default_branch || 'main';
                                const fullName = repo.full_name || repo.name;

                                return {
                                  value: val,
                                  searchValue: `${fullName} ${repo.name || ''}`,
                                  label: (
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', padding: '2px 0' }}>
                                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                        <GithubOutlined style={{ color: '#8b949e', fontSize: '13px', flexShrink: 0 }} />
                                        <span style={{ fontWeight: 600, color: '#f0f6fc', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                          {fullName}
                                        </span>
                                      </div>
                                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
                                        <Tag
                                          color={isPrivate ? 'gold' : 'green'}
                                          icon={isPrivate ? <LockOutlined /> : <UnlockOutlined />}
                                          style={{ fontSize: '10px', margin: 0, padding: '0 4px', lineHeight: '18px' }}
                                        >
                                          {isPrivate ? 'Private' : 'Public'}
                                        </Tag>
                                        <Tag
                                          color="blue"
                                          icon={<BranchesOutlined />}
                                          style={{ fontSize: '10px', margin: 0, padding: '0 4px', lineHeight: '18px' }}
                                        >
                                          {branch}
                                        </Tag>
                                      </div>
                                    </div>
                                  ),
                                };
                              }),
                              ...(gitRepo && !gitRepos.some((r: any) => (r.clone_url || r.path || r.full_name) === gitRepo)
                                ? [
                                    {
                                      value: gitRepo,
                                      searchValue: gitRepo,
                                      label: (
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                          <LinkOutlined style={{ color: '#38bdf8' }} />
                                          <span style={{ color: '#38bdf8' }}>{gitRepo} (Configured URL)</span>
                                        </div>
                                      ),
                                    },
                                  ]
                                : []),
                            ]}
                            loading={loadingGitRepos}
                            style={{ width: '100%' }}
                            dropdownStyle={{ background: '#161b22', borderColor: '#30363d', maxHeight: '280px' }}
                            notFoundContent={
                              loadingGitRepos ? (
                                <div style={{ padding: '8px', textAlign: 'center', color: '#8b949e' }}>Loading repositories...</div>
                              ) : (
                                <div style={{ padding: '8px', textAlign: 'center', color: '#8b949e' }}>
                                  No repositories discovered. Use the token input below or configure GitHub MCP connector.
                                </div>
                              )
                            }
                          />
                        </div>
                        <Button
                          icon={<SyncOutlined spin={loadingGitRepos} />}
                          loading={loadingGitRepos}
                          onClick={() => fetchGitRepos()}
                          style={{ background: '#21262d', borderColor: '#30363d', color: '#c9d1d9' }}
                        >
                          Refresh Repos
                        </Button>
                        {gitRepo.trim() && (
                          <Button
                            danger
                            icon={<DeleteOutlined />}
                            loading={savingConfig || scanning}
                            onClick={handleClearSource}
                            style={{ background: '#21262d', borderColor: '#f85149', color: '#f85149' }}
                          >
                            Clear Repo
                          </Button>
                        )}
                        <Button
                          type="primary"
                          icon={<SyncOutlined spin={savingConfig || scanning} />}
                          loading={savingConfig || scanning}
                          onClick={handleSaveAndSync}
                          style={{ background: '#38bdf8', borderColor: '#38bdf8', color: '#0d1117', fontWeight: 600 }}
                        >
                          Save & Sync from Git
                        </Button>
                      </div>

                      {/* If no token or user wants to enter token */}
                      {(hasGitToken === false || showTokenInput) && (
                        <div
                          style={{
                            background: '#0d1117',
                            border: '1px solid #30363d',
                            borderRadius: '8px',
                            padding: '10px 14px',
                            marginTop: '10px',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px', flexWrap: 'wrap', gap: '6px' }}>
                            <span style={{ color: '#e3b341', fontSize: '12px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <KeyOutlined /> No GitHub/GitLab token configured in MCP Hub. Paste a Personal Access Token to load repositories:
                            </span>
                          </div>
                          <div style={{ display: 'flex', gap: '8px' }}>
                            <Input.Password
                              size="small"
                              placeholder="Paste GitHub (ghp_...) or GitLab (glpat-...) token"
                              value={manualGitToken}
                              onChange={(e) => setManualGitToken(e.target.value)}
                              onPressEnter={() => fetchGitRepos(manualGitToken)}
                              style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc', flex: 1 }}
                            />
                            <Button
                              size="small"
                              type="primary"
                              loading={loadingGitRepos}
                              onClick={() => fetchGitRepos(manualGitToken)}
                              style={{ background: '#10b981', borderColor: '#10b981', color: '#0d1117', fontWeight: 600 }}
                            >
                              Load Repos
                            </Button>
                          </div>
                        </div>
                      )}

                      <div style={{ color: '#8b949e', fontSize: '11px', marginTop: '6px' }}>
                        Displays <strong>only</strong> skills synchronized from the selected Git repository (or none when no repository is selected).
                      </div>
                    </div>
                  )}
                </div>

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

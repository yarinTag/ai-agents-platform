import type { PluginsConfig } from '../types/skill';
import { usePermissions } from '../hooks/usePermissions';
import { useEffect, useState, useRef } from 'react';
import { Form, Button, Tag, message } from 'antd';
import { EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { Skill, PluginPackage } from '../types/skill';
import { getSkills, createSkill, updateSkill, deleteSkill, scanPlugins, getPluginsConfig, updatePluginsConfig, getPluginGitRepos, discoverMCPResources, getPluginSkillContent } from '../services/api';

export const useSkillsPage = (activeDepartmentId: string | null) => {
  const { isAdmin } = usePermissions();
  const [effectiveConfig, setEffectiveConfig] = useState<PluginsConfig>();
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
  const sourceConfigLoaded = useRef(false);
  const [sourceConfigError, setSourceConfigError] = useState<string | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);

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
      if (activeDepartmentId || (!isManual && !overrides) || !sourceConfigLoaded.current) {
        try {
          const cfgRes = await getPluginsConfig(activeDepartmentId);
          if (!cfgRes.data) throw new Error('Missing plugin configuration');
          if (cfgRes.data) {
            sourceConfigLoaded.current = true;
            setEffectiveConfig(cfgRes.data);
            setSourceConfigError(null);
            mode = (cfgRes.data.source_mode as 'local' | 'git') || 'local';
            lPath = cfgRes.data.local_path || '';
            gRepo = cfgRes.data.git_repo || '';
            setSourceMode(mode);
            setLocalPath(lPath);
            setGitRepo(gRepo);
          }
        } catch {
          setSourceConfigError('Plugin source configuration is unavailable. Retry before scanning.');
          return;
        }
      }

      if (isAdmin && mode === 'git' && gitRepos.length === 0) {
        fetchGitRepos();
      }

      const scanParams: { source_mode: 'local' | 'git'; local_path?: string; git_repo?: string } = {
        source_mode: mode,
        ...(mode === 'local' ? { local_path: lPath.trim() } : { git_repo: gRepo.trim() }),
      };

      const res = await scanPlugins(activeDepartmentId ? { department_id: activeDepartmentId } : isAdmin ? scanParams : undefined, isManual);
      setScanError(null);
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
      setScanError('Plugin scanning is unavailable. Retry to refresh the catalog.');
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
      setSelectedPluginSkill(null);
      const payload = {
        source_mode: sourceMode,
        ...(sourceMode === 'local' ? { local_path: localPath.trim() } : { git_repo: gitRepo.trim() }),
      };
      await updatePluginsConfig(activeDepartmentId ? { source_mode: 'git', git_repo: gitRepo.trim() } : payload, activeDepartmentId);
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
      if (activeDepartmentId) {
        await updatePluginsConfig({ source_mode: 'inherit' }, activeDepartmentId);
        await loadConfigAndScan(true);
      } else if (sourceMode === 'local') {
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
      const res = await getPluginSkillContent(skill.path, activeDepartmentId);
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
            disabled={!isAdmin} icon={<EditOutlined />}
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
            disabled={!isAdmin} icon={<DeleteOutlined />}
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

  return {
    sourceDepartmentId: activeDepartmentId,
    effectiveConfig,
    skills,
    sourceConfigError,
    scanError,
    setSkills,
    plugins,
    setPlugins,
    marketplacePath,
    setMarketplacePath,
    loading,
    setLoading,
    scanning,
    setScanning,
    savingConfig,
    setSavingConfig,
    visible,
    setVisible,
    form,
    editingKey,
    setEditingKey,
    selectedPluginSkill,
    setSelectedPluginSkill,
    skillContent,
    setSkillContent,
    loadingContent,
    setLoadingContent,
    hasScannedRef,
    sourceMode,
    setSourceMode,
    localPath,
    setLocalPath,
    gitRepo,
    setGitRepo,
    folderPickerOpen,
    setFolderPickerOpen,
    collapsedPluginNames,
    setCollapsedPluginNames,
    gitRepos,
    setGitRepos,
    loadingGitRepos,
    setLoadingGitRepos,
    hasGitToken,
    setHasGitToken,
    manualGitToken,
    setManualGitToken,
    showTokenInput,
    setShowTokenInput,
    fetchGitRepos,
    fetchSkills,
    loadConfigAndScan,
    handleSaveAndSync,
    handleClearSource,
    isAllCollapsed,
    handleToggleExpandAll,
    handleTogglePluginCollapse,
    handleSelectSkill,
    handleCreate,
    handleOk,
    columns,
  };
};

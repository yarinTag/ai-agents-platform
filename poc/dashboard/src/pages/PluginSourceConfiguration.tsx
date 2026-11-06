import { usePermissions } from '../hooks/usePermissions';
import { Table, Input, Button, Tag, Tabs, Segmented, Select } from 'antd';
import { DeleteOutlined, AppstoreOutlined, FolderOpenOutlined, FileTextOutlined, SyncOutlined, ThunderboltOutlined, CheckCircleOutlined, GithubOutlined, SaveOutlined, DownSquareOutlined, UpSquareOutlined, LockOutlined, UnlockOutlined, BranchesOutlined, KeyOutlined, LinkOutlined } from '@ant-design/icons';
import type { useSkillsPage } from './useSkillsPage';

export const PluginSourceConfiguration = (props: Pick<
  ReturnType<typeof useSkillsPage>,
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
>) => {
  const {
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
  } = props;
  const { isAdmin } = usePermissions();
  if (!isAdmin) return <div style={{ color: '#8b949e', marginBottom: 12 }}>Plugin sources are managed by your organization administrator.</div>;
  return (<>
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

  </>);
};

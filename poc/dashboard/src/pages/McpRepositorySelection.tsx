import { Tag, Button, Input, message, Checkbox, Select, Alert } from 'antd';
import { LockOutlined, UnlockOutlined, SyncOutlined, BranchesOutlined } from '@ant-design/icons';
import type { useMcpPage } from './useMcpPage';

export const McpRepositorySelection = (model: Pick<
  ReturnType<typeof useMcpPage>,
  | 'loading'
  | 'agents'
  | 'selectedCatalogItem'
  | 'discoveredResources'
  | 'selectedResources'
  | 'setSelectedResources'
  | 'customResourceInput'
  | 'setCustomResourceInput'
  | 'fetchingResources'
  | 'resourceDiscoveryError'
  | 'setResourceDiscoveryError'
  | 'handleFetchTokenRepositories'
  | 'handleAddCustomResource'
>) => {
  const {
    loading,
    agents,
    selectedCatalogItem,
    discoveredResources,
    selectedResources,
    setSelectedResources,
    customResourceInput,
    setCustomResourceInput,
    fetchingResources,
    resourceDiscoveryError,
    setResourceDiscoveryError,
    handleFetchTokenRepositories,
    handleAddCustomResource,
  } = model;
  return (<>
            {/* Git Repos Selection Section */}
            {selectedCatalogItem && (selectedCatalogItem.provider === 'github' || selectedCatalogItem.provider === 'git' || selectedCatalogItem.provider === 'gitlab') && (
              <div
                style={{
                  marginTop: '16px',
                  padding: '16px',
                  background: '#0d1117',
                  borderRadius: '8px',
                  border: '1px solid #30363d',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap', gap: '8px' }}>
                  <div style={{ fontWeight: 700, color: '#38bdf8', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <BranchesOutlined /> Authorized Repositories
                  </div>
                  <Button
                    size="small"
                    type="primary"
                    icon={<SyncOutlined spin={fetchingResources} />}
                    loading={fetchingResources}
                    onClick={handleFetchTokenRepositories}
                    style={{ background: '#10b981', borderColor: '#10b981', color: '#0d1117', fontWeight: 600 }}
                  >
                    Fetch Token Repositories
                  </Button>
                </div>

                {resourceDiscoveryError && (
                  <Alert
                    type="error"
                    showIcon
                    message="Token Authentication / Discovery Error"
                    description={resourceDiscoveryError}
                    closable
                    onClose={() => setResourceDiscoveryError(null)}
                    style={{ marginBottom: '12px', background: 'rgba(239, 68, 68, 0.12)', border: '1px solid #ef4444' }}
                  />
                )}

                <div style={{ color: '#8b949e', fontSize: '12px', marginBottom: '12px' }}>
                  Select which local and remote repositories the platform agents are authorized to access and modify:
                </div>

                {/* Currently Approved / Selected Repos */}
                <div
                  style={{
                    background: '#161b22',
                    border: '1px solid #30363d',
                    borderRadius: '8px',
                    padding: '10px 12px',
                    marginBottom: '14px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontSize: '12px', fontWeight: 700, color: '#38bdf8' }}>
                      ✓ Selected Repositories ({selectedResources.length}):
                    </span>
                    {selectedResources.length > 0 && (
                      <Button
                        size="small"
                        type="link"
                        danger
                        onClick={() => setSelectedResources([])}
                        style={{ padding: 0, height: 'auto', fontSize: '11px' }}
                      >
                        Clear All
                      </Button>
                    )}
                  </div>
                  {selectedResources.length === 0 ? (
                    <div style={{ color: '#8b949e', fontSize: '12px', fontStyle: 'italic' }}>
                      No repositories selected. Click on available repositories below or add a custom repo name.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {selectedResources.map((repoName) => (
                        <Tag
                          key={repoName}
                          closable
                          onClose={(e) => {
                            e.preventDefault();
                            setSelectedResources(selectedResources.filter((r) => r !== repoName));
                          }}
                          color="cyan"
                          style={{
                            fontSize: '12px',
                            padding: '3px 8px',
                            borderRadius: '6px',
                            fontWeight: 600,
                            display: 'inline-flex',
                            alignItems: 'center',
                          }}
                        >
                          {repoName}
                        </Tag>
                      ))}
                    </div>
                  )}
                </div>

                <div style={{ color: '#8b949e', fontSize: '12px', marginBottom: '8px' }}>
                  Available Repositories (click to toggle):
                </div>

                {discoveredResources.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '180px', overflowY: 'auto', marginBottom: '12px', paddingRight: '4px' }}>
                    {discoveredResources.map((repo: any) => {
                      const repoName = repo.full_name || repo.name;
                      const isChecked = selectedResources.includes(repoName) || selectedResources.includes(repo.name);
                      const isPrivate = repo.private !== undefined ? Boolean(repo.private) : false;
                      const defaultBranch = repo.default_branch || 'main';

                      return (
                        <div
                          key={repoName}
                          onClick={() => {
                            if (isChecked) {
                              setSelectedResources(selectedResources.filter((r) => r !== repoName && r !== repo.name));
                            } else {
                              setSelectedResources([...selectedResources, repoName]);
                            }
                          }}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '8px 12px',
                            background: isChecked ? 'rgba(56, 189, 248, 0.12)' : '#161b22',
                            border: isChecked ? '1px solid #38bdf8' : '1px solid #21262d',
                            borderRadius: '6px',
                            cursor: 'pointer',
                            transition: 'all 0.15s ease',
                            gap: '10px',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: 0 }}>
                            <Checkbox checked={isChecked} />
                            <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                              <span style={{ color: '#f0f6fc', fontWeight: 600, fontSize: '13px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {repo.full_name || repo.name}
                              </span>
                              {repo.name && repo.full_name && repo.name !== repo.full_name && (
                                <span style={{ color: '#8b949e', fontSize: '11px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                  {repo.name}
                                </span>
                              )}
                            </div>
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
                            {repo.private !== undefined && (
                              <Tag
                                color={isPrivate ? 'gold' : 'green'}
                                icon={isPrivate ? <LockOutlined /> : <UnlockOutlined />}
                                style={{ fontSize: '11px', margin: 0, fontWeight: 600 }}
                              >
                                {isPrivate ? 'Private' : 'Public'}
                              </Tag>
                            )}
                            <Tag color="blue" icon={<BranchesOutlined />} style={{ fontSize: '11px', margin: 0 }}>
                              {defaultBranch}
                            </Tag>
                            {repo.is_local && (
                              <Tag color="cyan" style={{ fontSize: '10px', margin: 0 }}>
                                Local
                              </Tag>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Add Custom Repo */}
                <div style={{ display: 'flex', gap: '8px' }}>
                  <Input
                    size="small"
                    placeholder="Add custom repository (e.g. owner/my-repo)"
                    value={customResourceInput}
                    onChange={(e) => setCustomResourceInput(e.target.value)}
                    onPressEnter={handleAddCustomResource}
                    style={{ background: '#161b22', borderColor: '#30363d', color: '#f0f6fc' }}
                  />
                  <Button size="small" type="primary" onClick={handleAddCustomResource}>
                    Add
                  </Button>
                </div>
              </div>
            )}


  </>);
};

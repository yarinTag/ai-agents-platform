import React, { useEffect, useState } from 'react';
import { Modal, Button, Input, Tag, Spin, Space, Tooltip, message } from 'antd';
import {
  FolderOutlined,
  FolderOpenOutlined,
  ArrowUpOutlined,
  ReloadOutlined,
  DesktopOutlined,
  HomeOutlined,
  FileTextOutlined,
  DownloadOutlined,
  CodeOutlined,
  CheckOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { browseDirectory, pickFolderNative, FolderItem, QuickAccessItem } from '../../services/api';

interface FolderPickerModalProps {
  open: boolean;
  onClose: () => void;
  onSelect: (selectedPath: string, folderName: string) => void;
  initialPath?: string;
  title?: string;
}

export const FolderPickerModal: React.FC<FolderPickerModalProps> = ({
  open,
  onClose,
  onSelect,
  initialPath,
  title = '📁 Select Project Directory from Computer',
}) => {
  const [currentPath, setCurrentPath] = useState<string>('');
  const [parentPath, setParentPath] = useState<string | null>(null);
  const [folders, setFolders] = useState<FolderItem[]>([]);
  const [quickAccess, setQuickAccess] = useState<QuickAccessItem[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<FolderItem | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [nativeLoading, setNativeLoading] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [pathInput, setPathInput] = useState<string>('');

  const loadDirectory = async (targetPath?: string) => {
    try {
      setLoading(true);
      const res = await browseDirectory(targetPath);
      setCurrentPath(res.data.current_path);
      setPathInput(res.data.current_path);
      setParentPath(res.data.parent_path || null);
      setFolders(res.data.folders || []);
      setQuickAccess(res.data.quick_access || []);
      setSelectedFolder(null);
    } catch (err: any) {
      console.error(err);
      message.error(err?.response?.data?.detail || 'Failed to open directory');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      loadDirectory(initialPath);
    }
  }, [open, initialPath]);

  const handleNativePick = async () => {
    try {
      setNativeLoading(true);
      const res = await pickFolderNative(currentPath);
      if (res.data.cancelled) {
        // User cancelled picker dialog
        return;
      }
      if (res.data.path) {
        message.success(`Selected folder: ${res.data.name || res.data.path}`);
        onSelect(res.data.path, res.data.name || '');
        onClose();
      } else if (res.data.error) {
        message.warning(res.data.error);
      }
    } catch (err: any) {
      console.error(err);
      const detail = err?.response?.data?.detail || err?.message || '';
      message.error(`Failed to trigger native folder picker${detail ? ': ' + detail : ''}`);
    } finally {
      setNativeLoading(false);
    }
  };

  const handleQuickAccessClick = (path: string) => {
    loadDirectory(path);
  };

  const handleFolderClick = (folder: FolderItem) => {
    setSelectedFolder(folder);
  };

  const handleFolderDoubleClick = (folder: FolderItem) => {
    loadDirectory(folder.path);
  };

  const handleGoUp = () => {
    if (parentPath) {
      loadDirectory(parentPath);
    }
  };

  const handleConfirm = () => {
    if (selectedFolder) {
      onSelect(selectedFolder.path, selectedFolder.name);
      onClose();
    } else if (currentPath) {
      // Pick current directory
      const folderName = currentPath.split(/[/\\\\]/).filter(Boolean).pop() || 'Project';
      onSelect(currentPath, folderName);
      onClose();
    }
  };

  const getQuickIcon = (icon?: string) => {
    switch (icon) {
      case 'home':
        return <HomeOutlined />;
      case 'desktop':
        return <DesktopOutlined />;
      case 'document':
        return <FileTextOutlined />;
      case 'download':
        return <DownloadOutlined />;
      case 'code':
        return <CodeOutlined />;
      default:
        return <FolderOutlined />;
    }
  };

  const filteredFolders = folders.filter((f) =>
    f.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#f8fafc', fontSize: '16px' }}>
          <FolderOpenOutlined style={{ color: '#38bdf8' }} />
          <span>{title}</span>
        </div>
      }
      open={open}
      onCancel={onClose}
      width={760}
      footer={[
        <Button key="cancel" onClick={onClose}>
          Cancel
        </Button>,
        <Button
          key="select"
          type="primary"
          icon={<CheckOutlined />}
          onClick={handleConfirm}
          disabled={!selectedFolder && !currentPath}
          style={{ background: '#238636', borderColor: '#238636' }}
        >
          {selectedFolder ? `Select "${selectedFolder.name}"` : 'Select Current Directory'}
        </Button>,
      ]}
      styles={{
        body: { padding: '16px 20px', background: '#0f172a', borderRadius: '8px' },
      }}
    >
      {/* Top action row: Native Picker CTA */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          background: '#1e293b',
          border: '1px solid #334155',
          borderRadius: '8px',
          padding: '10px 14px',
          marginBottom: '14px',
        }}
      >
        <div>
          <div style={{ fontWeight: 600, color: '#f1f5f9', fontSize: '13px' }}>
            🖥️ Native System Dialog
          </div>
          <div style={{ color: '#94a3b8', fontSize: '11px' }}>
            Select directly via your operating system's native folder picker (Finder / Explorer)
          </div>
        </div>
        <Button
          type="primary"
          icon={<DesktopOutlined />}
          onClick={handleNativePick}
          loading={nativeLoading}
          style={{ background: '#0284c7', borderColor: '#0284c7', borderRadius: '6px' }}
        >
          Open System Picker
        </Button>
      </div>

      {/* Quick Access bar */}
      {quickAccess.length > 0 && (
        <div style={{ marginBottom: '12px' }}>
          <span style={{ fontSize: '11px', color: '#64748b', marginRight: '8px', textTransform: 'uppercase', fontWeight: 600 }}>
            Quick Access:
          </span>
          <Space size={[6, 6]} wrap>
            {quickAccess.map((qa) => (
              <Button
                key={qa.path}
                size="small"
                icon={getQuickIcon(qa.icon)}
                onClick={() => handleQuickAccessClick(qa.path)}
                style={{
                  background: currentPath === qa.path ? '#334155' : '#1e293b',
                  borderColor: currentPath === qa.path ? '#38bdf8' : '#334155',
                  color: currentPath === qa.path ? '#38bdf8' : '#cbd5e1',
                  borderRadius: '6px',
                  fontSize: '12px',
                }}
              >
                {qa.name}
              </Button>
            ))}
          </Space>
        </div>
      )}

      {/* Path bar and controls */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '12px', alignItems: 'center' }}>
        <Tooltip title="Go to Parent Directory">
          <Button
            icon={<ArrowUpOutlined />}
            onClick={handleGoUp}
            disabled={!parentPath}
            style={{ background: '#1e293b', borderColor: '#334155', color: '#cbd5e1' }}
          />
        </Tooltip>

        <Input
          value={pathInput}
          onChange={(e) => setPathInput(e.target.value)}
          onPressEnter={() => loadDirectory(pathInput)}
          placeholder="Path to directory..."
          style={{
            flex: 1,
            background: '#1e293b',
            borderColor: '#334155',
            color: '#f8fafc',
            fontFamily: 'monospace',
            fontSize: '12px',
          }}
          prefix={<FolderOpenOutlined style={{ color: '#38bdf8' }} />}
        />

        <Tooltip title="Refresh directory">
          <Button
            icon={<ReloadOutlined />}
            onClick={() => loadDirectory(currentPath)}
            style={{ background: '#1e293b', borderColor: '#334155', color: '#cbd5e1' }}
          />
        </Tooltip>
      </div>

      {/* Search / Filter in current directory */}
      <div style={{ marginBottom: '10px' }}>
        <Input
          size="small"
          placeholder="Filter folders in this directory..."
          prefix={<SearchOutlined style={{ color: '#64748b' }} />}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          allowClear
          style={{
            background: '#1e293b',
            borderColor: '#334155',
            color: '#cbd5e1',
            borderRadius: '6px',
          }}
        />
      </div>

      {/* Directory Content List */}
      <div
        style={{
          height: '300px',
          overflowY: 'auto',
          background: '#090d16',
          border: '1px solid #1e293b',
          borderRadius: '8px',
          padding: '6px',
        }}
      >
        {loading ? (
          <div style={{ textAlign: 'center', padding: '80px 0' }}>
            <Spin size="large" />
          </div>
        ) : filteredFolders.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px 0', color: '#64748b', fontSize: '13px' }}>
            {searchQuery ? 'No folders match the search query' : 'No subdirectories found in this folder'}
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            {filteredFolders.map((folder) => {
              const isSelected = selectedFolder?.path === folder.path;
              return (
                <div
                  key={folder.path}
                  onClick={() => handleFolderClick(folder)}
                  onDoubleClick={() => handleFolderDoubleClick(folder)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    cursor: 'pointer',
                    background: isSelected ? 'rgba(56, 189, 248, 0.15)' : 'transparent',
                    border: isSelected ? '1px solid #38bdf8' : '1px solid transparent',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.background = '#1e293b';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.background = 'transparent';
                    }
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', overflow: 'hidden' }}>
                    {folder.is_project ? (
                      <span style={{ fontSize: '16px' }}>📦</span>
                    ) : (
                      <FolderOutlined style={{ color: '#38bdf8', fontSize: '15px' }} />
                    )}
                    <span
                      style={{
                        color: isSelected ? '#38bdf8' : '#f1f5f9',
                        fontWeight: folder.is_project ? 600 : 400,
                        fontSize: '13px',
                        textOverflow: 'ellipsis',
                        overflow: 'hidden',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {folder.name}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {folder.is_project && (
                      <Tag color="cyan" style={{ fontSize: '11px', margin: 0, borderRadius: '4px' }}>
                        {folder.project_type || 'Project'}
                      </Tag>
                    )}
                    <span style={{ color: '#475569', fontSize: '11px' }}>Double-click to open</span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Selected folder preview info */}
      <div
        style={{
          marginTop: '10px',
          padding: '6px 10px',
          background: '#1e293b',
          borderRadius: '6px',
          fontSize: '12px',
          color: '#94a3b8',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          <strong style={{ color: '#cbd5e1' }}>Selected Path: </strong>
          <span style={{ color: '#38bdf8', fontFamily: 'monospace' }}>
            {selectedFolder ? selectedFolder.path : currentPath}
          </span>
        </span>
        {selectedFolder?.is_project && (
          <Tag color="green" style={{ margin: 0 }}>
            Detected: {selectedFolder.project_type || 'Project'}
          </Tag>
        )}
      </div>
    </Modal>
  );
};

export default FolderPickerModal;

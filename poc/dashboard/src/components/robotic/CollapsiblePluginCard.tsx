import React, { useState } from 'react';
import { Tag, Button, Typography, Space } from 'antd';
import {
  FolderOpenOutlined,
  DownOutlined,
  RightOutlined,
} from '@ant-design/icons';

const { Text } = Typography;

export interface CollapsiblePluginCardProps {
  title: string;
  version?: string;
  domain?: string;
  skillsCount?: number;
  icon?: React.ReactNode;
  path?: string;
  tags?: React.ReactNode;
  extra?: React.ReactNode;
  children?: React.ReactNode;
  defaultCollapsed?: boolean;
  isCollapsed?: boolean;
  onToggleCollapse?: (collapsed: boolean) => void;
  style?: React.CSSProperties;
}

export const CollapsiblePluginCard: React.FC<CollapsiblePluginCardProps> = ({
  title,
  version,
  domain,
  skillsCount,
  icon = <FolderOpenOutlined style={{ color: '#e3b341', fontSize: '18px' }} />,
  path,
  tags,
  extra,
  children,
  defaultCollapsed = false,
  isCollapsed: controlledCollapsed,
  onToggleCollapse,
  style,
}) => {
  const [internalCollapsed, setInternalCollapsed] = useState<boolean>(defaultCollapsed);

  const isCollapsed = controlledCollapsed !== undefined ? controlledCollapsed : internalCollapsed;

  const handleToggle = () => {
    const nextState = !isCollapsed;
    if (controlledCollapsed === undefined) {
      setInternalCollapsed(nextState);
    }
    if (onToggleCollapse) {
      onToggleCollapse(nextState);
    }
  };

  return (
    <div
      style={{
        background: '#0d1117',
        border: '1px solid #30363d',
        borderRadius: '12px',
        padding: '16px 20px',
        transition: 'all 0.2s ease',
        ...style,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          cursor: 'pointer',
          userSelect: 'none',
        }}
        onClick={handleToggle}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <Button
            type="text"
            size="small"
            icon={
              isCollapsed ? (
                <RightOutlined style={{ color: '#8b949e', fontSize: '12px' }} />
              ) : (
                <DownOutlined style={{ color: '#8b949e', fontSize: '12px' }} />
              )
            }
            onClick={(e) => {
              e.stopPropagation();
              handleToggle();
            }}
            style={{ padding: 0, width: '22px', height: '22px' }}
          />
          {icon}
          <span style={{ fontSize: '16px', fontWeight: 700, color: '#f3f4f6' }}>
            {title}
          </span>
          {version && <Tag color="blue">v{version}</Tag>}
          {domain && <Tag color="purple">{domain}</Tag>}
          {skillsCount !== undefined && <Tag color="cyan">{skillsCount} Skills</Tag>}
          {tags}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {path && (
            <span
              style={{
                fontSize: '11px',
                color: '#6e7681',
                maxWidth: '300px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {path}
            </span>
          )}
          {extra && (
            <div
              onClick={(e) => {
                e.stopPropagation();
              }}
            >
              {extra}
            </div>
          )}
        </div>
      </div>

      {!isCollapsed && children && (
        <div
          style={{
            marginTop: '16px',
            paddingTop: '14px',
            borderTop: '1px solid #21262d',
          }}
        >
          {children}
        </div>
      )}
    </div>
  );
};

export default CollapsiblePluginCard;

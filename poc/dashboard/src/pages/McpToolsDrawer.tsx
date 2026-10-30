import { Tag, Spin, Drawer, List } from 'antd';
import { ToolOutlined } from '@ant-design/icons';
import type { useMcpPage } from './useMcpPage';

export const McpToolsDrawer = (model: Pick<
  ReturnType<typeof useMcpPage>,
  | 'toolsDrawerVisible'
  | 'setToolsDrawerVisible'
  | 'drawerConnector'
  | 'connectorTools'
  | 'loadingTools'
>) => {
  const { toolsDrawerVisible, setToolsDrawerVisible, drawerConnector, connectorTools, loadingTools } = model;
  return (<>
      {/* Tools Drawer */}
      <Drawer
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ToolOutlined style={{ color: '#10b981' }} />
            <span>Tools exposed by {drawerConnector?.name}</span>
          </div>
        }
        placement="right"
        width={480}
        onClose={() => setToolsDrawerVisible(false)}
        open={toolsDrawerVisible}
        styles={{
          body: { background: '#0a0d12', color: '#f0f6fc', padding: '16px' },
          header: { background: '#161b22', borderBottom: '1px solid #21262d', color: '#f0f6fc' },
        }}
      >
        {loadingTools ? (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Spin />
          </div>
        ) : connectorTools.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: '#8b949e' }}>
            No tools registered under this connector.
          </div>
        ) : (
          <List
            dataSource={connectorTools}
            renderItem={(tool) => (
              <List.Item
                style={{
                  border: '1px solid #21262d',
                  borderRadius: '8px',
                  background: '#161b22',
                  marginBottom: '10px',
                  padding: '12px',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-start',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%', alignItems: 'center' }}>
                  <code style={{ fontSize: '13px', fontWeight: 700, color: '#34d399' }}>
                    {tool.name}
                  </code>
                  <Tag style={{ background: '#0d1117', borderColor: '#30363d', color: '#8b949e', fontSize: '10px' }}>
                    MCP Tool
                  </Tag>
                </div>
                <p style={{ margin: '6px 0 0 0', color: '#8b949e', fontSize: '12px' }}>
                  {tool.description || 'No description provided.'}
                </p>
              </List.Item>
            )}
          />
        )}
      </Drawer>

  </>);
};

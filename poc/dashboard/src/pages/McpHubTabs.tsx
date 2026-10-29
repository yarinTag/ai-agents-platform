import { ResourceSection } from './ResourceSection';
import { Tabs } from 'antd';
import { CheckCircleOutlined, AppstoreOutlined, LinkOutlined } from '@ant-design/icons';
import type { useMcpPage } from './useMcpPage';
import { McpWorkflowChannels } from './McpWorkflowChannels';
import { McpInstalledConnectors } from './McpInstalledConnectors';
import { McpMarketplace } from './McpMarketplace';

export const McpHubTabs = (model: Pick<ReturnType<typeof useMcpPage>, 'catalog' | 'connectors' | 'workflows' | 'resourceErrors' | 'loadData'> & Parameters<typeof McpMarketplace>[0] & Parameters<typeof McpInstalledConnectors>[0] & Parameters<typeof McpWorkflowChannels>[0]) => {
  const { catalog, connectors, workflows, resourceErrors, loadData } = model;
  return (<>
      {/* Main Tabs */}
      <Tabs
        defaultActiveKey="catalog"
        tabBarStyle={{ borderBottom: '1px solid #21262d', marginBottom: '20px' }}
        items={[
          {
            key: 'catalog',
            label: (
              <span style={{ fontSize: '14px', fontWeight: 600 }}>
                <AppstoreOutlined /> Integrations Marketplace ({catalog.length})
              </span>
            ),
            children: (
              <ResourceSection error={resourceErrors.catalog || resourceErrors.connectors} onRetry={loadData}>
                <McpMarketplace {...model} />
              </ResourceSection>
            ),
          },
          {
            key: 'installed',
            label: (
              <span style={{ fontSize: '14px', fontWeight: 600 }}>
                <CheckCircleOutlined /> Installed Connectors ({connectors.length})
              </span>
            ),
            children: (
              <ResourceSection error={resourceErrors.connectors} onRetry={loadData}>
                <McpInstalledConnectors {...model} />
              </ResourceSection>
            ),
          },
          {
            key: 'channels',
            label: (
              <span style={{ fontSize: '14px', fontWeight: 600 }}>
                <LinkOutlined /> Workflow Channels ({workflows.filter((w) => w.channel_binding).length} Active / {workflows.length} Total)
              </span>
            ),
            children: (
              <ResourceSection error={resourceErrors.workflows} onRetry={loadData}>
                <McpWorkflowChannels {...model} />
              </ResourceSection>
            ),
          },
        ]}
      />

  </>);
};

import { ResourceSection } from './ResourceSection';
import { Alert, Button, Spin, Tabs } from 'antd';
import { CheckCircleOutlined, AppstoreOutlined, ApiOutlined } from '@ant-design/icons';
import { usePermissions } from '../hooks/usePermissions';
import { useChannelIngressText } from '../i18n/channelIngress';
import { WebhookDiagnostics } from '../components/WebhookDiagnostics';
import type { useMcpPage } from './useMcpPage';
import { McpInstalledConnectors } from './McpInstalledConnectors';
import { McpMarketplace } from './McpMarketplace';

export const McpHubTabs = (model: Pick<ReturnType<typeof useMcpPage>, 'catalog' | 'connectors' | 'resourceErrors' | 'loadData' | 'loading'> & Parameters<typeof McpMarketplace>[0] & Parameters<typeof McpInstalledConnectors>[0]) => {
  const { catalog, connectors, resourceErrors, loadData, loading } = model;
  const { isAdmin } = usePermissions();
  const diagnosticsText = useChannelIngressText();
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
          ...(isAdmin ? [{
            key: 'webhook-diagnostics',
            label: <span><ApiOutlined /> {diagnosticsText.title}</span>,
            destroyOnHidden: true,
            children: loading ? <Spin aria-label={diagnosticsText.loadingConnectors} />
              : resourceErrors.connectors ? <Alert type="warning" showIcon title={diagnosticsText.connectorLoadFailed}
                action={<Button onClick={loadData}>{diagnosticsText.refresh}</Button>} />
                : <WebhookDiagnostics connectors={connectors} />,
          }] : []),
        ]}
      />

  </>);
};

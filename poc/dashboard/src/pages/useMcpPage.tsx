import { configuredResourceValues } from '../services/mcpResources';


import { useMcpState } from './useMcpState';
import { useMcpConnectorActions } from './useMcpConnectorActions';
import { useMcpWorkflowActions } from './useMcpWorkflowActions';
import { getProviderIcon } from './mcpProviderIcon';

export const useMcpPage = () => {
  const state = useMcpState();
  const connectorActions = useMcpConnectorActions(state);
  const workflowActions = useMcpWorkflowActions(state);
  const { catalog, connectors, workflows, searchQuery, selectedCategory } = state;
  const categories = ['ALL', 'Developer Tools', 'Communication', 'Productivity & Planning', 'Databases', 'Data & Search'];

  // Filter catalog
  const filteredCatalog = catalog.filter((item) => {
    const matchesCat = selectedCategory === 'ALL' || item.category === selectedCategory;
    const matchesSearch =
      item.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.package.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCat && matchesSearch;
  });

  // Extract authorized channels from Slack & Telegram connectors
  const slackConnectors = connectors.filter((c) => c.provider === 'slack' || c.id === 'slack');
  const telegramConnectors = connectors.filter((c) => c.provider === 'telegram' || c.id === 'telegram');
  const slackConnector = slackConnectors[0];
  const telegramConnector = telegramConnectors[0];

  const configuredSlackChannels = configuredResourceValues(connectors, 'slack', 'allowed_channels', 'default_channel');
  const availableSlackChannels = configuredSlackChannels;
  const configuredTelegramChats = configuredResourceValues(connectors, 'telegram', 'allowed_channels', 'chat_id');
  const availableTelegramChats = configuredTelegramChats;

  return {
    ...state,
    ...connectorActions,
    ...workflowActions,
    getProviderIcon,
    categories,
    filteredCatalog,
    slackConnectors,
    telegramConnectors,
    slackConnector,
    telegramConnector,
    configuredSlackChannels,
    availableSlackChannels,
    configuredTelegramChats,
    availableTelegramChats,
  };
};

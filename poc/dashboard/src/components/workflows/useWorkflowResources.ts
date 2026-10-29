import { configuredResourceValues } from '../../services/mcpResources';
import { useEffect, useRef, useState } from 'react';
import { getMCPConnectors, getSkills, scanPlugins } from '../../services/api';
import { readResource } from '../../services/resourceLoading';

interface WorkflowResourceOptions {
  open: boolean;
  channelProvider: string;
  channelId: string;
  setChannelId: (value: string) => void;
  setAllowedMcps: (value: string[]) => void;
}

export function useWorkflowResources(options: WorkflowResourceOptions) {
  const [installedMcps, setInstalledMcps] = useState<string[]>([]);
  const [telegramChannels, setTelegramChannels] = useState<string[]>([]);
  const [slackChannels, setSlackChannels] = useState<string[]>([]);
  const [githubRepos, setGithubRepos] = useState<string[]>([]);
  const [catalogSkills, setCatalogSkills] = useState<any[]>([]);
  const [resourcesLoading, setResourcesLoading] = useState(false);
  const [connectorError, setConnectorError] = useState<string | null>(null);
  const [skillsError, setSkillsError] = useState<string | null>(null);
  const generation = useRef(0);

  const reloadResources = async () => {
    const requestId = ++generation.current;
    const current = () => generation.current === requestId;
    setResourcesLoading(true);
    let skillItems: any[] = [];
    let pluginItems: any[] = [];
    const [mcpFailure, skillFailure, pluginFailure] = await Promise.all([
      readResource(getMCPConnectors(), ({ data }) => {
        if (!current()) return;
        const connectors = data?.connectors || [];
        const ids = Array.from(new Set(connectors.map((connector) => connector.id || connector.provider)));
        setInstalledMcps(ids);
        options.setAllowedMcps(ids);
        const telegram = configuredResourceValues(connectors, 'telegram', 'allowed_channels', 'chat_id');
        const slack = configuredResourceValues(connectors, 'slack', 'allowed_channels', 'default_channel');
        setTelegramChannels(telegram);
        setSlackChannels(slack);
        setGithubRepos(Array.from(new Set([
          ...configuredResourceValues(connectors, 'github', 'allowed_repos', 'default_repo'),
          ...configuredResourceValues(connectors, 'git', 'allowed_repos', 'default_repo'),
        ])));
        const channels = options.channelProvider === 'telegram' ? telegram : slack;
        if (!channels.includes(options.channelId)) options.setChannelId(channels[0] || '');
      }, 'MCP connectors'),
      readResource(getSkills(), ({ data }) => { skillItems = data || []; }, 'Skills'),
      readResource(scanPlugins(), ({ data }) => {
        pluginItems = (data?.plugins || []).flatMap((plugin) =>
          (plugin.skills || []).map((skill) => ({ ...skill, source: 'marketplace' })));
      }, 'Plugin catalog'),
    ]);
    if (!current()) return;
    setConnectorError(mcpFailure);
    setSkillsError(skillFailure || pluginFailure);
    setCatalogSkills([...skillItems, ...pluginItems]);
    setResourcesLoading(false);
  };

  useEffect(() => {
    if (options.open) reloadResources();
    return () => { generation.current += 1; };
  }, [options.open]);

  return {
    installedMcps, telegramChannels, slackChannels, githubRepos,
    catalogSkills, setCatalogSkills, resourcesLoading, connectorError, skillsError,
    reloadResources,
  };
}

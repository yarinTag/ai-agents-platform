import { configuredResourceValues } from '../../services/mcpResources';
import { useEffect, useRef, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import { getAgents, getMCPConnectors, discoverMCPResources, getSkills, scanPlugins } from '../../services/api';
import { readResource } from '../../services/resourceLoading';
import { getWorkflowChatContext } from '../../services/workflowChatApi';
import type { WorkflowChatContext } from '../../types/workflowChat';

interface WorkflowResourceOptions {
  open: boolean;
  editing: boolean;
  departmentId?: string | null;
  workflowId?: string;
  channelProvider: string;
  channelId: string;
  setChannelId: (value: string) => void;
  setAllowedMcps: (value: string[]) => void;
  setTargetRepo: Dispatch<SetStateAction<string>>;
}

export function useWorkflowResources(options: WorkflowResourceOptions) {
  const [agentOptions, setAgentOptions] = useState<Array<{ value: string; label: string }>>([]);
  const [channelLabels, setChannelLabels] = useState<Record<string, string>>({});
  const getChannelLabel = (provider: string, id: string) => channelLabels[`${provider}:${id}`] || id;
  const [installedMcps, setInstalledMcps] = useState<string[]>([]);
  const [telegramChannels, setTelegramChannels] = useState<string[]>([]);
  const [slackChannels, setSlackChannels] = useState<string[]>([]);
  const [githubRepos, setGithubRepos] = useState<string[]>([]);
  const [catalogSkills, setCatalogSkills] = useState<any[]>([]);
  const [resourcesLoading, setResourcesLoading] = useState(Boolean(options.open));
  const [connectorError, setConnectorError] = useState<string | null>(null);
  const [skillsError, setSkillsError] = useState<string | null>(null);
  const [repositoryError, setRepositoryError] = useState<string | null>(null);
  const [workspaceCatalog, setWorkspaceCatalog] = useState<WorkflowChatContext['catalog']>(null);
  const [workspaceCatalogError, setWorkspaceCatalogError] = useState<string | null>(null);
  const generation = useRef(0);

  const reloadResources = async () => {
    const requestId = ++generation.current;
    const current = () => generation.current === requestId;
    setResourcesLoading(true);
    setAgentOptions([]);
    setWorkspaceCatalog(null);
    let skillItems: any[] = [];
    let pluginItems: any[] = [];
    const [mcpFailure, skillFailure, pluginFailure, agentFailure, workspaceFailure] = await Promise.all([
      readResource(getMCPConnectors(), ({ data }) => {
        if (!current()) return;
        const connectors = data?.connectors || [];
        const ids = Array.from(new Set(connectors.map((connector) => connector.id || connector.provider)));
        setInstalledMcps(ids);
        if (!options.editing) options.setAllowedMcps(ids);
        const telegram = configuredResourceValues(connectors, 'telegram', 'allowed_channels', 'chat_id');
        const slack = configuredResourceValues(connectors, 'slack', 'allowed_channels', 'default_channel');
        const labels: Record<string, string> = {};
        for (const connector of connectors) {
          const configured = connector.configuration?.channel_labels || {};
          for (const [id, label] of Object.entries(configured)) {
            if (typeof label === 'string' && label.trim()) labels[`${connector.provider}:${id}`] = label;
          }
        }
        setChannelLabels(labels);
        setTelegramChannels(telegram);
        setSlackChannels(slack);
        const gitProviders = ['github', 'git', 'gitlab', 'local_git'];
        const configuredRepos = Array.from(new Set(gitProviders.flatMap(provider => [
          ...configuredResourceValues(connectors, provider, 'allowed_repos', 'default_repo'),
          ...configuredResourceValues(connectors, provider, 'repositories', 'repo'),
        ])));
        setGithubRepos(configuredRepos);
        const providers = Array.from(new Set(connectors
          .filter(connector => gitProviders.includes(connector.provider) || gitProviders.includes(connector.id))
          .map(connector => connector.provider === 'git' ? 'github' : connector.provider)));
        if (!providers.length && connectors.length) providers.push('github');
        let discoveryFailed = false;
        Promise.all(providers.map(provider => discoverMCPResources(provider).catch(() => {
          discoveryFailed = true;
          return null;
        }))).then(results => {
          if (!current()) return;
          const discovered = results.flatMap(response => (response?.data?.repositories || [])
            .map(repository => repository.full_name || repository.name).filter(Boolean));
          const repos: string[] = Array.from(new Set([...configuredRepos, ...discovered]));
          setGithubRepos(repos);
          setRepositoryError(discoveryFailed ? 'Repository discovery is unavailable. Configured repositories remain available.' : null);
          if (!options.editing && repos.length) {
            options.setTargetRepo(previous => previous && repos.includes(previous) ? previous : repos[0]);
          }
        });
        const channels = options.channelProvider === 'telegram' ? telegram : slack;
        if (!options.editing && !channels.includes(options.channelId)) options.setChannelId(channels[0] || '');
      }, 'MCP connectors'),
      readResource(getSkills(), ({ data }) => { skillItems = data || []; }, 'Skills'),
      readResource(scanPlugins(), ({ data }) => {
        pluginItems = (data?.plugins || []).flatMap((plugin) =>
          (plugin.skills || []).map((skill) => ({ ...skill, source: 'marketplace' })));
      }, 'Plugin catalog'),
      readResource(getAgents(), ({ data }) => {
        if (!current()) return;
        const available = data.filter(agent =>
          (!agent.department_id || agent.department_id === options.departmentId) &&
          (!agent.is_workflow_agent || agent.id === `wf-agent-${options.workflowId}`))
          .map(agent => ({ value: agent.id, label: agent.name }));
        if (!options.editing) available.unshift({ value: '__workflow_runner__', label: 'Dedicated workflow runner · created on confirmation' });
        setAgentOptions(available);
      }, 'Execution agents'),
      options.departmentId ? readResource(getWorkflowChatContext(options.departmentId), ({ data }) => {
        if (current()) setWorkspaceCatalog(data.catalog);
      }, 'Repository workspace permissions') : Promise.resolve(null),
    ]);
    if (!current()) return;
    setConnectorError(mcpFailure || agentFailure);
    setWorkspaceCatalogError(workspaceFailure);
    setSkillsError(skillFailure || pluginFailure);
    setCatalogSkills([...skillItems, ...pluginItems]);
    setResourcesLoading(false);
  };

  useEffect(() => {
    if (options.open) reloadResources();
    return () => { generation.current += 1; };
  }, [options.open, options.departmentId, options.workflowId]);

  return {
    agentOptions, getChannelLabel, installedMcps, telegramChannels, slackChannels, githubRepos,
    catalogSkills, setCatalogSkills, resourcesLoading, connectorError, skillsError, repositoryError,
    reloadResources,
    workspaceCatalog, workspaceCatalogError,
  };
}

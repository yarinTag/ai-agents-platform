import React, { useMemo } from 'react';
import {
  AppstoreOutlined,
  FolderOpenOutlined,
  GithubOutlined,
  ThunderboltOutlined,
  FileTextOutlined,
  BranchesOutlined,
  EyeOutlined,
  ArrowRightOutlined,
  ArrowLeftOutlined,
} from '@ant-design/icons';
import { PluginPackage, PluginSkill, Skill } from '../../types/skill';
import {
  ConnectionCanvasDiagram,
  CanvasRootNode,
  CanvasGroupNode,
  CanvasLeafNode,
  CanvasLegendItem,
} from '../common/ConnectionCanvas';
import { buildPluginSkillFlow } from './pluginsFlowModel';

export interface PluginsConnectionCanvasProps {
  sourceMode: 'local' | 'git';
  localPath: string;
  gitRepo: string;
  plugins: PluginPackage[];
  customSkills: Skill[];
  loading?: boolean;
  onRefresh?: () => void;
  onSelectPluginSkill: (skill: PluginSkill) => void;
}

export const PluginsConnectionCanvas: React.FC<PluginsConnectionCanvasProps> = ({
  sourceMode,
  localPath,
  gitRepo,
  plugins,
  customSkills,
  loading = false,
  onRefresh,
  onSelectPluginSkill,
}) => {
  const safePlugins = Array.isArray(plugins) ? plugins : [];
  const safeCustomSkills = Array.isArray(customSkills) ? customSkills : [];

  const totalPluginSkills = useMemo(
    () => safePlugins.reduce((sum, p) => sum + (p?.skills_count || (p?.skills || []).length), 0),
    [safePlugins]
  );

  const uniqueDomains = useMemo(() => {
    const domains = new Set<string>();
    safePlugins.forEach((p) => {
      if (p?.domain) domains.add(p.domain);
      (p?.skills || []).forEach((s) => {
        if (s?.domain) domains.add(s.domain);
      });
    });
    return domains.size;
  }, [safePlugins]);

  const activeSourceLabel =
    sourceMode === 'local'
      ? (localPath || '').trim() || 'Unconfigured Local Path'
      : (gitRepo || '').trim() || 'Unconfigured Git Repository';

  const rootNode = useMemo<CanvasRootNode>(
    () => ({
      tag: sourceMode === 'local' ? 'LOCAL PLUGINS SOURCE' : 'GIT REPOSITORY SOURCE',
      title: 'Skills & Plugins Ecosystem',
      subtitle: activeSourceLabel,
      icon:
        sourceMode === 'local' ? (
          <FolderOpenOutlined style={{ color: '#c084fc', fontSize: 20 }} />
        ) : (
          <GithubOutlined style={{ color: '#c084fc', fontSize: 20 }} />
        ),
      accentColor: '#a855f7',
      metrics: [
        { label: 'Plugin Packages', value: safePlugins.length, color: '#58a6ff' },
        { label: 'Plugin Skills', value: totalPluginSkills, color: '#a855f7' },
        { label: 'Custom Skills', value: safeCustomSkills.length, color: '#38bdf8' },
        { label: 'Domains', value: uniqueDomains, color: '#10b981' },
      ],
    }),
    [sourceMode, activeSourceLabel, safePlugins.length, totalPluginSkills, safeCustomSkills.length, uniqueDomains]
  );

  const groups = useMemo<CanvasGroupNode<PluginSkill | null>[]>(() => {
    const pluginGroups: CanvasGroupNode<PluginSkill | null>[] = safePlugins.map((pkg, pkgIdx) => {
      const flowItems = buildPluginSkillFlow(pkg, safePlugins);
      const totalConnections = flowItems.reduce((acc, item) => acc + item.connectedToIds.length, 0);

      const children: CanvasLeafNode<PluginSkill | null>[] = flowItems.map((item) => {
        const sk = item.skill;
        const isRouter =
          sk.role === 'router' || sk.id.endsWith('-router') || sk.id.endsWith('-start');

        return {
          id: sk.id,
          title: sk.name,
          titleIcon: <ThunderboltOutlined style={{ color: isRouter ? '#f59e0b' : '#38bdf8' }} />,
          subtitle: sk.description,
          isActive: true,
          statusLabel: isRouter ? 'ROUTER' : 'SKILL',
          versionBadge: sk.version ? `v${sk.version}` : pkg.version ? `v${pkg.version}` : undefined,
          flowStageIndex: item.stageIndex,
          flowStageLabel: item.stageLabel,
          connectedToIds: item.connectedToIds,
          connectedFromIds: item.connectedFromIds,
          ownerBadge: {
            label: sk.id,
            icon: <FileTextOutlined />,
          },
          incomingTitle:
            item.connectedFromIds.length > 0
              ? `⬅ Triggered / Used By (${item.connectedFromIds.length}) & Domain`
              : '📦 Domain & Stage',
          incomingBadges: [
            ...(sk.domain || pkg.domain
              ? [
                  {
                    id: `${sk.id}_dom`,
                    label: String(sk.domain || pkg.domain),
                    color: 'purple',
                    icon: <BranchesOutlined />,
                  },
                ]
              : []),
            ...item.connectedFromIds.slice(0, 4).map((fromId) => ({
              id: `${sk.id}_from_${fromId}`,
              label: fromId,
              color: 'gold',
              icon: <ArrowLeftOutlined />,
              tooltip: `Upstream skill ${fromId} routes into ${sk.id}`,
            })),
            ...(item.connectedFromIds.length > 4
              ? [
                  {
                    id: `${sk.id}_from_more`,
                    label: `+${item.connectedFromIds.length - 4} upstream`,
                    color: 'gold',
                    tooltip: item.connectedFromIds.join(', '),
                  },
                ]
              : []),
          ],
          stagesTitle: 'SKILL FLOW & INSTRUCTIONS',
          stagesButtonLabel: 'Details',
          stages: [
            ...(item.connectedToIds.length > 0
              ? [
                  {
                    id: `${sk.id}_routes_stage`,
                    label: `Routes To (${item.connectedToIds.length})`,
                    items: item.connectedToIds.slice(0, 6).map((targetId) => ({
                      id: `${sk.id}_edge_${targetId}`,
                      title: `➔ ${targetId}`,
                      subtitle: 'Connected downstream skill in lifecycle',
                      accentColor: '#10b981',
                    })),
                  },
                ]
              : []),
            {
              id: `${sk.id}_preview_stage`,
              label: 'SKILL.md Preview',
              items: [
                {
                  id: `${sk.id}_preview`,
                  title: sk.content_preview || sk.description || 'Click to inspect full SKILL.md instructions',
                  subtitle: sk.path,
                  accentColor: '#a855f7',
                },
              ],
            },
          ],
          outgoingTitle:
            item.connectedToIds.length > 0
              ? `➔ Connects / Routes To (${item.connectedToIds.length} Skills)`
              : '📄 Skill Definition',
          outgoingBadges:
            item.connectedToIds.length > 0
              ? [
                  ...item.connectedToIds.slice(0, 5).map((targetId) => ({
                    id: `${sk.id}_to_${targetId}`,
                    label: targetId,
                    color: 'green',
                    icon: <ArrowRightOutlined />,
                    tooltip: `${sk.id} ➔ ${targetId}`,
                  })),
                  ...(item.connectedToIds.length > 5
                    ? [
                        {
                          id: `${sk.id}_to_more`,
                          label: `+${item.connectedToIds.length - 5} more`,
                          color: 'cyan',
                          tooltip: item.connectedToIds.join(', '),
                        },
                      ]
                    : []),
                ]
              : [
                  {
                    id: `${sk.id}_file`,
                    label: sk.filename || 'SKILL.md',
                    color: 'cyan',
                    icon: <FileTextOutlined />,
                    tooltip: sk.path,
                  },
                ],
          actions: [
            {
              key: 'inspect',
              tooltip: 'Inspect Skill Instructions (SKILL.md)',
              icon: <EyeOutlined />,
              color: '#38bdf8',
              onClick: () => onSelectPluginSkill(sk),
            },
          ],
          data: sk,
        };
      });

      return {
        id: `plugin_${pkg.name}`,
        badgeLabel: pkg.name === 'core' ? 'CORE LIFECYCLE PLUGIN' : 'PLUGIN PACKAGE',
        badgeColor: pkg.name === 'core' ? 'purple' : 'blue',
        statusBadge: `${children.length} Skills`,
        title: pkg.display_name || pkg.name,
        icon: <AppstoreOutlined style={{ color: '#58a6ff' }} />,
        description: pkg.description || pkg.path,
        accentColor: pkg.name === 'core' ? '#8b5cf6' : '#3b82f6',
        useStageColumnsLayout: true,
        defaultCollapsed: safePlugins.length > 2 && pkgIdx > 0,
        metrics: [
          ...(pkg.domain ? [{ label: 'Domain', value: pkg.domain, color: '#a5b4fc' }] : []),
          { label: 'Skill Links', value: `${totalConnections} Flow Edges`, color: '#10b981' },
        ],
        footerText: `${children.length} Skills • ${pkg.version ? `v${pkg.version}` : 'latest'}`,
        emptyText: 'No skills in this plugin package',
        children,
      };
    });

    if (safeCustomSkills.length > 0) {
      pluginGroups.push({
        id: '__custom_skills__',
        badgeLabel: 'CUSTOM REGISTRY',
        badgeColor: 'cyan',
        statusBadge: `${safeCustomSkills.length} Skills`,
        title: 'Custom Registered Skills',
        icon: <FileTextOutlined style={{ color: '#38bdf8' }} />,
        description: 'Database-persisted custom skills created in this workspace',
        accentColor: '#0ea5e9',
        defaultCollapsed: safePlugins.length > 1,
        footerText: `${safeCustomSkills.length} Custom Skills`,
        children: safeCustomSkills.map((c) => ({
          id: `custom_${c.id}`,
          title: c.name,
          titleIcon: <FileTextOutlined style={{ color: '#10b981' }} />,
          subtitle: c.description || (c.content || '').slice(0, 120),
          isActive: true,
          statusLabel: 'CUSTOM',
          ownerBadge: { label: c.id },
          incomingTitle: '📦 Source',
          incomingBadges: [{ id: `src_${c.id}`, label: 'Workspace Registry', color: 'cyan' }],
          data: null,
        })),
      });
    }

    return pluginGroups;
  }, [safePlugins, safeCustomSkills, onSelectPluginSkill]);

  const legend = useMemo<CanvasLegendItem[]>(
    () => [
      { label: 'Plugins Source', color: 'purple', icon: '🏛️' },
      { label: 'Plugin Package', color: 'blue', icon: '📦' },
      { label: '1. Entry & Router', color: 'gold', icon: '🧭' },
      { label: '2..5. Lifecycle Flow Stages', color: 'cyan', icon: '⚡' },
      { label: 'Downstream Connected Skills', color: 'green', icon: '➔' },
    ],
    []
  );

  return (
    <ConnectionCanvasDiagram<PluginSkill | null>
      rootNode={rootNode}
      groups={groups}
      legend={legend}
      loading={loading}
      showStatusFilter={false}
      onRefresh={onRefresh}
      labels={{
        searchPlaceholder: 'Search plugins, skills, domains, or connected flows...',
        allGroupsLabel: 'All Plugin Packages',
        statusAllLabel: 'All',
        statusActiveLabel: 'Active',
        statusInactiveLabel: 'Inactive',
        expandAllLabel: 'Expand Details',
        collapseAllLabel: 'Collapse Details',
        showLinksLabel: 'Flow Connections',
        refreshLabel: 'Refresh Canvas',
        emptyLabel: 'No plugins or skills match the current filter.',
        panHint: 'Hover any skill to highlight upstream (amber) & downstream (green) connected skills • Click to inspect SKILL.md',
        expandNodeTooltip: 'Expand skill flow & preview',
        collapseNodeTooltip: 'Collapse details',
      }}
      onClickLeaf={(leaf) => {
        if (leaf.data) {
          onSelectPluginSkill(leaf.data);
        }
      }}
    />
  );
};

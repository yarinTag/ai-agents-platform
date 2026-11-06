import React, { useState, useMemo } from 'react';
import {
  BankOutlined, ApartmentOutlined, DollarCircleOutlined, TeamOutlined,
  ClockCircleOutlined, ThunderboltOutlined, SendOutlined, SlackOutlined,
  ToolOutlined, GithubOutlined, BranchesOutlined, EyeOutlined, FileSearchOutlined, RobotOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { Department, Organization } from '../../types/auth';
import { PlatformWorkflow } from '../../types/mcp';
import { useOrgWorkflowsCanvasText } from '../../i18n/orgWorkflowsCanvas';
import {
  ConnectionCanvasDiagram,
  CanvasRootNode,
  CanvasGroupNode,
  CanvasLeafNode,
  CanvasBadgeItem,
  CanvasLegendItem,
} from '../common/ConnectionCanvas';
import { buildOrgWorkflowsTopology, EnrichedWorkflowNode } from './orgWorkflowsCanvasModel';
import { OrgWorkflowInspectorDrawer } from './OrgWorkflowInspectorDrawer';

export interface OrgWorkflowsCanvasTabProps {
  organization: Organization | null;
  departments: Department[];
  workflows: PlatformWorkflow[];
  loading?: boolean;
  onRefresh?: () => void;
  onManageTeam?: (departmentId: string) => void;
}

export const OrgWorkflowsCanvasTab: React.FC<OrgWorkflowsCanvasTabProps> = ({
  organization,
  departments,
  workflows,
  loading = false,
  onRefresh,
  onManageTeam,
}) => {
  const text = useOrgWorkflowsCanvasText();
  const navigate = useNavigate();

  const [inspectedNode, setInspectedNode] = useState<EnrichedWorkflowNode | null>(null);
  const [inspectorTab, setInspectorTab] = useState<'overview' | 'dag' | 'yaml'>('dag');

  const topology = useMemo(
    () =>
      buildOrgWorkflowsTopology(
        departments,
        workflows,
        text.unassignedDept,
        text.unassignedDesc,
        organization?.id
      ),
    [departments, workflows, text.unassignedDept, text.unassignedDesc, organization?.id]
  );

  const rootNode = useMemo<CanvasRootNode>(
    () => ({
      tag: text.orgRootTag,
      title: organization?.name || 'Enterprise Organization',
      subtitle: organization?.slug ? `@${organization.slug}` : undefined,
      icon: <BankOutlined style={{ color: '#c084fc', fontSize: 20 }} />,
      accentColor: '#a855f7',
      metrics: [
        { label: text.departmentsCount, value: topology.totalDepartments, color: '#58a6ff' },
        { label: text.workflowsCount, value: `${topology.activeWorkflows}/${topology.totalWorkflows}`, color: '#a855f7' },
        { label: text.stepsCount, value: topology.totalSteps, color: '#38bdf8' },
        { label: text.channelsCount, value: topology.uniqueChannelsAndMcps, color: '#10b981' },
      ],
    }),
    [organization, text, topology]
  );

  const canvasGroups = useMemo<CanvasGroupNode<EnrichedWorkflowNode>[]>(
    () =>
      topology.groups.map((group) => {
        const { department, workflows: deptWfs, activeCount, totalSteps, isUnassigned } = group;
        const children: CanvasLeafNode<EnrichedWorkflowNode>[] = deptWfs.map((wfNode) => {
          const { workflow, triggers, steps, dagStages, mcpServers, repositories, skills, channels, runnerAgentId } = wfNode;

          const incomingBadges: CanvasBadgeItem[] = triggers.map((tr, idx) => ({
            id: `${workflow.id}_tr_${idx}`,
            label: tr.label,
            color: tr.type === 'cron' ? 'geekblue' : tr.type === 'channel' ? 'cyan' : tr.type === 'webhook' ? 'purple' : 'default',
            icon:
              tr.type === 'cron' ? <ClockCircleOutlined /> : tr.type === 'channel' ? <SendOutlined /> : tr.type === 'webhook' ? <ThunderboltOutlined /> : undefined,
          }));

          const outgoingBadges: CanvasBadgeItem[] = [
            ...repositories.map((repo) => ({
              id: `repo_${repo}`,
              label: repo,
              color: 'purple',
              icon: <GithubOutlined />,
            })),
            ...mcpServers.map((mcp) => ({
              id: `mcp_${mcp}`,
              label: mcp,
              color: 'cyan',
              icon: <ToolOutlined />,
            })),
            ...skills.map((sk) => ({
              id: `skill_${sk}`,
              label: sk,
              color: 'gold',
              icon: <BranchesOutlined />,
            })),
            ...channels.map((ch, idx) => ({
              id: `ch_${ch.provider}_${ch.channelId}_${idx}`,
              label: `${ch.provider.toUpperCase()}: ${ch.channelName || ch.channelId}`,
              color: ch.provider === 'telegram' ? 'blue' : ch.provider === 'slack' ? 'orange' : 'green',
              icon: ch.provider === 'telegram' ? <SendOutlined /> : ch.provider === 'slack' ? <SlackOutlined /> : <ThunderboltOutlined />,
            })),
          ];

          return {
            id: workflow.id,
            title: workflow.name,
            titleIcon: <ApartmentOutlined style={{ color: '#a855f7' }} />,
            subtitle: workflow.description,
            isActive: workflow.is_active,
            statusLabel: workflow.is_active ? text.activeBadge : text.inactiveBadge,
            versionBadge: workflow.revision ? `v${workflow.revision}` : undefined,
            ownerBadge: {
              label: runnerAgentId,
              icon: <RobotOutlined />,
            },
            incomingTitle: `⚡ ${text.triggersLabel}`,
            incomingBadges,
            stagesTitle: `${text.stepsLabel} (${steps.length})`,
            stagesButtonLabel: `${steps.length} ${text.stepsCount}`,
            stages: dagStages.map((stageSteps, stageIdx) => ({
              id: `${workflow.id}_stage_${stageIdx}`,
              label: `${text.stagePrefix} #${stageIdx + 1}`,
              items: stageSteps.map((st) => ({
                id: st.key,
                title: st.name,
                subtitle: `🤖 ${st.agent_id}`,
                meta: st.depends_on && st.depends_on.length > 0 ? `${text.dependsOn}: ${st.depends_on.join(', ')}` : undefined,
                accentColor: '#38bdf8',
              })),
            })),
            outgoingTitle: `🔗 ${text.externalLabel}`,
            outgoingBadges,
            actions: [
              {
                key: 'inspect',
                tooltip: text.inspectWorkflow,
                icon: <EyeOutlined />,
                color: '#38bdf8',
                onClick: () => {
                  setInspectedNode(wfNode);
                  setInspectorTab('dag');
                },
              },
              {
                key: 'logs',
                tooltip: text.openLogs,
                icon: <FileSearchOutlined />,
                color: '#c9d1d9',
                onClick: () => navigate(`/workflows/${workflow.id}/logs`),
              },
            ],
            data: wfNode,
          };
        });

        return {
          id: department.id,
          badgeLabel: isUnassigned ? 'ORG SCOPE' : 'DEPARTMENT',
          badgeColor: isUnassigned ? 'default' : 'blue',
          statusBadge: `${activeCount}/${deptWfs.length} ${text.activeCount}`,
          title: department.name,
          icon: <ApartmentOutlined style={{ color: '#58a6ff' }} />,
          description: department.description,
          accentColor: isUnassigned ? '#64748b' : '#3b82f6',
          metrics: !isUnassigned
            ? [
                {
                  label: text.budgetLabel,
                  icon: <DollarCircleOutlined style={{ color: '#10b981' }} />,
                  value: `$${(department.current_spend_usd || 0).toFixed(2)} / $${(department.monthly_budget_usd || 0).toLocaleString()}`,
                  color: '#10b981',
                },
              ]
            : [],
          footerText: `${deptWfs.length} ${text.workflowsCount} • ${totalSteps} ${text.stepsCount}`,
          footerAction:
            !isUnassigned && onManageTeam
              ? {
                  label: 'Team',
                  icon: <TeamOutlined />,
                  onClick: () => onManageTeam(department.id),
                }
              : undefined,
          emptyText: text.noWorkflowsInDept,
          children,
        };
      }),
    [topology.groups, text, navigate, onManageTeam]
  );

  const legend = useMemo<CanvasLegendItem[]>(
    () => [
      { label: text.legendOrganization, color: 'purple', icon: '🏛️' },
      { label: text.legendDepartment, color: 'blue', icon: '🏢' },
      { label: text.triggersLabel, color: 'geekblue', icon: '⚡' },
      { label: `${text.legendWorkflow} & ${text.legendSteps}`, color: 'cyan', icon: '🔀' },
      { label: text.legendExternal, color: 'green', icon: '🔗' },
    ],
    [text]
  );

  const inspectedDeptName = useMemo(() => {
    if (!inspectedNode) return undefined;
    const found = topology.groups.find((g) => g.department.id === inspectedNode.departmentId);
    return found?.department.name;
  }, [inspectedNode, topology.groups]);

  return (
    <>
      <ConnectionCanvasDiagram<EnrichedWorkflowNode>
        rootNode={rootNode}
        groups={canvasGroups}
        legend={legend}
        loading={loading}
        onRefresh={onRefresh}
        labels={{
          searchPlaceholder: text.searchPlaceholder,
          allGroupsLabel: text.allDepartments,
          statusAllLabel: text.statusAll,
          statusActiveLabel: text.statusActive,
          statusInactiveLabel: text.statusInactive,
          expandAllLabel: text.expandAllSteps,
          collapseAllLabel: text.collapseAllSteps,
          showLinksLabel: text.showResources,
          refreshLabel: text.refresh,
          emptyLabel: text.noWorkflowsFound,
          panHint: text.panHint,
          expandNodeTooltip: text.expandSteps,
          collapseNodeTooltip: text.collapseSteps,
        }}
        onClickLeaf={(leaf) => {
          if (leaf.data) {
            setInspectedNode(leaf.data);
            setInspectorTab('overview');
          }
        }}
        onClickStage={(leaf) => {
          if (leaf.data) {
            setInspectedNode(leaf.data);
            setInspectorTab('dag');
          }
        }}
      />

      <OrgWorkflowInspectorDrawer
        node={inspectedNode}
        departmentName={inspectedDeptName}
        activeTab={inspectorTab}
        onTabChange={setInspectorTab}
        onClose={() => setInspectedNode(null)}
        onOpenLogs={(wfId) => navigate(`/workflows/${wfId}/logs`)}
        onOpenHub={() => navigate('/workflows')}
        text={text}
      />
    </>
  );
};

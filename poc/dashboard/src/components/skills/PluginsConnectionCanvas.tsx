import React, { useMemo } from 'react';
import type { PluginPackage, PluginSkill, Skill } from '../../types/skill';
import type { CanvasGroupNode, CanvasRootNode } from '../common/ConnectionCanvas';
import { PluginSkillFlowGraph } from './PluginSkillFlowGraph';
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
  sourceMode, localPath, gitRepo, plugins, customSkills, loading = false,
  onRefresh, onSelectPluginSkill,
}) => {
  const groups = useMemo<CanvasGroupNode<PluginSkill | null>[]>(() => {
    const packages = Array.isArray(plugins) ? plugins : [];
    const result: CanvasGroupNode<PluginSkill | null>[] = packages.map((pkg) => ({
      id: `plugin_${pkg.name}`,
      title: pkg.display_name || pkg.name,
      badgeLabel: 'PLUGIN PACKAGE',
      children: buildPluginSkillFlow(pkg, packages).map((item) => ({
        id: item.skill.id,
        title: item.skill.name,
        subtitle: item.skill.description,
        flowStageIndex: item.stageIndex,
        flowStageLabel: item.stageLabel,
        connectedToIds: item.connectedToIds,
        connectedFromIds: item.connectedFromIds,
        data: item.skill,
      })),
    }));
    if (Array.isArray(customSkills) && customSkills.length) {
      result.push({
        id: '__custom_skills__', title: 'Custom Registered Skills', badgeLabel: 'CUSTOM REGISTRY',
        children: customSkills.map((skill) => ({
          id: `custom_${skill.id}`, title: skill.name, subtitle: skill.description,
          flowStageIndex: 0, flowStageLabel: 'Custom skill', data: null,
        })),
      });
    }
    return result;
  }, [plugins, customSkills]);
  const rootNode: CanvasRootNode = {
    tag: 'PLUGINS SOURCE', title: 'Skill connections', metrics: [],
    subtitle: sourceMode === 'local' ? (localPath || '').trim() || 'Unconfigured Local Path'
      : (gitRepo || '').trim() || 'Unconfigured Git Repository',
  };

  return <PluginSkillFlowGraph key={`${sourceMode}:${localPath}:${gitRepo}`} rootNode={rootNode} groups={groups} loading={loading}
    onRefresh={onRefresh} onInspect={(leaf) => { if (leaf.data) onSelectPluginSkill(leaf.data); }} />;
};

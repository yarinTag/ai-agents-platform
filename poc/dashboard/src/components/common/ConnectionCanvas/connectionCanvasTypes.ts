import React from 'react';

export interface CanvasBadgeItem {
  id: string;
  label: string;
  color?: string;
  icon?: React.ReactNode;
  tooltip?: string;
}

export interface CanvasStageItem {
  id: string;
  title: string;
  subtitle?: string;
  meta?: string;
  accentColor?: string;
}

export interface CanvasStageGroup {
  id: string;
  label: string;
  items: CanvasStageItem[];
}

export interface CanvasNodeAction {
  key: string;
  tooltip: string;
  icon: React.ReactNode;
  color?: string;
  onClick: () => void;
}

export interface CanvasLeafNode<T = unknown> {
  id: string;
  title: string;
  titleIcon?: React.ReactNode;
  subtitle?: string;
  isActive?: boolean;
  statusLabel?: string;
  versionBadge?: string;
  ownerBadge?: {
    label: string;
    icon?: React.ReactNode;
  };
  /** Optional stage column index & label when a group lays out children as a multi-stage horizontal flow */
  flowStageIndex?: number;
  flowStageLabel?: string;
  /** IDs of downstream/upstream leaf nodes connected to this node (highlighted on hover/selection) */
  connectedToIds?: string[];
  connectedFromIds?: string[];
  incomingTitle?: string;
  incomingBadges?: CanvasBadgeItem[];
  stagesTitle?: string;
  stagesButtonLabel?: string;
  stages?: CanvasStageGroup[];
  outgoingTitle?: string;
  outgoingBadges?: CanvasBadgeItem[];
  actions?: CanvasNodeAction[];
  accentColor?: string;
  data?: T;
}

export interface CanvasGroupMetric {
  label: string;
  value: React.ReactNode;
  color?: string;
  icon?: React.ReactNode;
}

export interface CanvasGroupNode<T = unknown> {
  id: string;
  badgeLabel: string;
  badgeColor?: string;
  statusBadge?: string;
  title: string;
  icon?: React.ReactNode;
  description?: string;
  metrics?: CanvasGroupMetric[];
  footerText?: string;
  footerAction?: {
    label: string;
    icon?: React.ReactNode;
    onClick: () => void;
  };
  accentColor?: string;
  emptyText?: string;
  searchKeywords?: string[];
  /** If true, children with flowStageIndex are arranged in horizontal connected stage columns */
  useStageColumnsLayout?: boolean;
  defaultCollapsed?: boolean;
  children: CanvasLeafNode<T>[];
}

export interface CanvasRootMetric {
  label: string;
  value: React.ReactNode;
  color?: string;
}

export interface CanvasRootNode {
  tag: string;
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
  accentColor?: string;
  metrics: CanvasRootMetric[];
}

export interface CanvasLegendItem {
  label: string;
  color: string;
  icon?: string;
}

export interface ConnectionCanvasLabels {
  searchPlaceholder: string;
  allGroupsLabel: string;
  statusAllLabel: string;
  statusActiveLabel: string;
  statusInactiveLabel: string;
  expandAllLabel: string;
  collapseAllLabel: string;
  showLinksLabel: string;
  refreshLabel: string;
  emptyLabel: string;
  panHint: string;
  expandNodeTooltip: string;
  collapseNodeTooltip: string;
}

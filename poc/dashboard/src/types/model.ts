export interface DiscoveredModel {
  id: string;
  name: string;
  provider: string;
  description: string;
  context_window: number;
  is_default?: boolean;
  tier?: string | null;
}

/** Logical capability tier from GET /api/v1/models/tiers (id such as "tier:developer"). */
export interface ModelTierOption {
  id: string;
  tier: string;
  name: string;
  description: string;
  min_context_window: number;
  requires_reasoning: boolean;
  requires_tools: boolean;
}

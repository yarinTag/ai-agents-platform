export type ModelTier = 'executive' | 'architect' | 'developer' | 'worker' | 'default';

export interface ModelOption {
  label: string;
  value: string;
  name?: string;
  provider: 'Anthropic Claude' | 'NVIDIA NIM' | 'System Default' | string;
  tier: ModelTier;
  contextWindow: number;
  badgeColor: string;
  description: string;
  isDefault?: boolean;
}

export interface ModelGroup {
  label: string;
  options: ModelOption[];
}

export const AI_MODELS: ModelOption[] = [
  // System Default
  {
    label: 'Claude Code Default (System)',
    value: 'default',
    name: 'Claude Code Default',
    provider: 'System Default',
    tier: 'default',
    contextWindow: 200000,
    badgeColor: '#0ea5e9',
    description: 'System configured default Claude model for CLI runner',
    isDefault: true,
  },
  // Anthropic Claude Family
  {
    label: 'Claude 3.7 Sonnet (Executive)',
    value: 'claude-3-7-sonnet-20250219',
    name: 'Claude 3.7 Sonnet',
    provider: 'Anthropic Claude',
    tier: 'executive',
    contextWindow: 200000,
    badgeColor: '#eab308',
    description: 'Hybrid reasoning model combining instant answers with step-by-step thinking',
  },
  {
    label: 'Claude 3.5 Sonnet (Coding)',
    value: 'claude-3-5-sonnet-20241022',
    name: 'Claude 3.5 Sonnet',
    provider: 'Anthropic Claude',
    tier: 'developer',
    contextWindow: 200000,
    badgeColor: '#3b82f6',
    description: 'High-intelligence flagship model optimized for software engineering and coding',
  },
  {
    label: 'Claude 3.5 Haiku (Fast Worker)',
    value: 'claude-3-5-haiku-20241022',
    name: 'Claude 3.5 Haiku',
    provider: 'Anthropic Claude',
    tier: 'worker',
    contextWindow: 200000,
    badgeColor: '#10b981',
    description: 'Ultra-fast, lightweight model ideal for quick subtasks and high throughput',
  },
  {
    label: 'Claude 3 Opus (Architect)',
    value: 'claude-3-opus-20240229',
    name: 'Claude 3 Opus',
    provider: 'Anthropic Claude',
    tier: 'architect',
    contextWindow: 200000,
    badgeColor: '#a855f7',
    description: 'Deep contextual synthesis and high-level architectural planning',
  },
  // NVIDIA NIM Family
  {
    label: 'Nemotron 3 Super 120B (Executive)',
    value: 'nvidia_nim/nvidia/nemotron-3-super-120b-a12b',
    name: 'Nemotron 3 Super 120B',
    provider: 'NVIDIA NIM',
    tier: 'executive',
    contextWindow: 128000,
    badgeColor: '#6366f1',
    description: 'Enterprise grade open-weights model hosted on NVIDIA NIM infrastructure',
  },
  {
    label: 'Llama 3.3 70B Instruct (Fast Worker)',
    value: 'nvidia_nim/meta/llama-3.3-70b-instruct',
    name: 'Llama 3.3 70B Instruct',
    provider: 'NVIDIA NIM',
    tier: 'worker',
    contextWindow: 128000,
    badgeColor: '#f97316',
    description: 'High-performance general instruction tuned model via NIM gateway',
  },
];

export const MODEL_GROUPS: ModelGroup[] = [
  {
    label: 'System Default',
    options: AI_MODELS.filter((m) => m.provider === 'System Default'),
  },
  {
    label: 'Anthropic Claude',
    options: AI_MODELS.filter((m) => m.provider === 'Anthropic Claude'),
  },
  {
    label: 'NVIDIA NIM',
    options: AI_MODELS.filter((m) => m.provider === 'NVIDIA NIM'),
  },
];

export const formatContextWindow = (tokens: number): string => {
  if (tokens >= 1000000) {
    return `${(tokens / 1000000).toFixed(0)}M`;
  }
  if (tokens >= 1000) {
    return `${(tokens / 1000).toFixed(0)}K`;
  }
  return `${tokens}`;
};

export const getModelTierLabel = (tier?: string): string => {
  switch (tier?.toLowerCase()) {
    case 'executive':
      return 'Executive';
    case 'architect':
      return 'Architect';
    case 'developer':
    case 'coding':
      return 'Coding';
    case 'worker':
      return 'Fast Worker';
    case 'default':
      return 'Default';
    default:
      return tier || 'General';
  }
};

export const getModelTierColor = (tier?: string): string => {
  switch (tier?.toLowerCase()) {
    case 'executive':
      return '#eab308'; // gold / amber
    case 'architect':
      return '#a855f7'; // purple
    case 'developer':
    case 'coding':
      return '#3b82f6'; // blue
    case 'worker':
      return '#10b981'; // emerald green
    case 'default':
      return '#0ea5e9'; // cyan
    default:
      return '#8b949e';
  }
};

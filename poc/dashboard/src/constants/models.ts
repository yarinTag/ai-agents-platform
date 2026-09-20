export interface ModelOption {
  label: string;
  value: string;
  description?: string;
}

export interface ModelGroup {
  label: string;
  options: ModelOption[];
}

export const AI_MODELS: ModelOption[] = [
  { label: 'Default', value: 'default', description: 'System / FCC configured default model' },
  { label: 'Sonnet', value: 'sonnet', description: 'Claude Sonnet model' },
  { label: 'Opus', value: 'opus', description: 'Claude Opus model' },
  { label: 'Haiku', value: 'haiku', description: 'Claude Haiku model' },
  { label: 'Fable', value: 'fable', description: 'Claude Fable model' },
];

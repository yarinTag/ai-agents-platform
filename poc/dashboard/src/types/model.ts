export interface DiscoveredModel {
  id: string;
  name: string;
  provider: string;
  description: string;
  context_window: number;
  is_default?: boolean;
}

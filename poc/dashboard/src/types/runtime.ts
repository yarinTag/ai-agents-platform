export type RuntimeProviderId =
  | 'claude_code_native'
  | 'free_claude_code'
  | 'anthropic_api'
  | 'custom_gateway'
  | 'direct_nvidia'
  | 'direct_anthropic'
  | 'direct_openai'
  | 'direct_openrouter';

export interface ProviderModelItem {
  id: string;
  name: string;
  provider: string;
  description: string;
  context_window: number;
  tier?: string;
}

export interface RuntimeProviderStatus {
  id: RuntimeProviderId;
  name: string;
  description: string;
  available: boolean;
  detail: string;
  requires_config: boolean;
  config: {
    model_id?: string;
    models?: ProviderModelItem[];
    has_api_key?: boolean;
    enabled?: boolean;
    [key: string]: unknown;
  };
  is_selected: boolean;
}

export interface RuntimeSetupState {
  setup_completed: boolean;
  selected_provider: RuntimeProviderId | null;
  effective_provider: RuntimeProviderId;
  suggested_provider: RuntimeProviderId | null;
  providers: RuntimeProviderStatus[];
}

export interface RuntimeSelectionDto {
  provider_id: RuntimeProviderId;
  message_threads_enabled?: boolean;
  gateway_base_url?: string;
  model_id?: string;
  api_key?: string;
  enabled_providers?: string[];
  provider_models?: Record<string, string>;
  provider_keys?: Record<string, string>;
}

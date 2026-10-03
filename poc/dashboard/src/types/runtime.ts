export type RuntimeProviderId =
  | 'claude_code_native'
  | 'free_claude_code'
  | 'anthropic_api'
  | 'custom_gateway';

export interface RuntimeProviderStatus {
  id: RuntimeProviderId;
  name: string;
  description: string;
  available: boolean;
  detail: string;
  requires_config: boolean;
  config: Record<string, unknown>;
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
  gateway_base_url?: string;
}

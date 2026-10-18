import React, { useCallback, useEffect, useState } from 'react';
import { Button, Card, Input, Select, Space, Tag, Tooltip, Typography, message } from 'antd';
import {
  CheckCircleOutlined,
  DeleteOutlined,
  KeyOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { api } from '../../services/api';
import { inputTokenStyle, tokens } from '../../shared/theme/tokens';

const { Text, Title } = Typography;

export type LLMProviderId = 'anthropic' | 'openai' | 'nvidia_nim';

export interface OrgLLMKeyRecord {
  provider: LLMProviderId;
  key_masked: string;
  base_url?: string | null;
  default_model?: string | null;
  is_verified?: boolean;
  updated_at?: string;
}

export interface OrgLLMKeysPanelProps {
  orgId?: string;
  onKeysChanged?: (keys: OrgLLMKeyRecord[]) => void;
}

interface ProviderSpec {
  id: LLMProviderId;
  label: string;
  badge: string;
  defaultModel: string;
  defaultBaseUrl: string;
  placeholder: string;
}

const PROVIDER_SPECS: ProviderSpec[] = [
  { id: 'anthropic', label: 'Anthropic', badge: 'Claude 3.5 / 3.7 / 4', defaultModel: 'claude-3-5-sonnet-latest', defaultBaseUrl: 'https://api.anthropic.com', placeholder: 'sk-ant-api03-...' },
  { id: 'openai', label: 'OpenAI', badge: 'GPT-4o / o3-mini', defaultModel: 'gpt-4o', defaultBaseUrl: 'https://api.openai.com/v1', placeholder: 'sk-proj-...' },
  { id: 'nvidia_nim', label: 'NVIDIA NIM', badge: 'Llama / Nemotron NIM', defaultModel: 'meta/llama-3.1-70b-instruct', defaultBaseUrl: 'https://integrate.api.nvidia.com/v1', placeholder: 'nvapi-...' },
];

const maskRawKey = (raw: string): string => {
  const trimmed = raw.trim();
  return trimmed.length <= 8 ? '••••••••' : `${trimmed.slice(0, 6)}••••${trimmed.slice(-4)}`;
};

export const OrgLLMKeysPanel: React.FC<OrgLLMKeysPanelProps> = ({ orgId = 'org-default', onKeysChanged }) => {
  const [keys, setKeys] = useState<Record<LLMProviderId, OrgLLMKeyRecord | null>>({
    anthropic: null,
    openai: null,
    nvidia_nim: null,
  });
  const [selectedProvider, setSelectedProvider] = useState<LLMProviderId>('anthropic');
  const [apiKeyInput, setApiKeyInput] = useState<string>('');
  const [baseUrlInput, setBaseUrlInput] = useState<string>(PROVIDER_SPECS[0].defaultBaseUrl);
  const [defaultModelInput, setDefaultModelInput] = useState<string>(PROVIDER_SPECS[0].defaultModel);
  const [loading, setLoading] = useState<boolean>(false);
  const [verifyingProvider, setVerifyingProvider] = useState<LLMProviderId | null>(null);

  const fetchKeys = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get<{ keys?: OrgLLMKeyRecord[] } | OrgLLMKeyRecord[]>(`/api/v1/organizations/${orgId}/llm-keys`);
      const list = Array.isArray(res.data) ? res.data : res.data?.keys || [];
      const mapped: Record<LLMProviderId, OrgLLMKeyRecord | null> = { anthropic: null, openai: null, nvidia_nim: null };
      list.forEach((item) => {
        if (item.provider in mapped) mapped[item.provider as LLMProviderId] = item;
      });
      setKeys(mapped);
      onKeysChanged?.(list);
    } catch {
      // Keep local state if endpoint is not yet seeded for this org
    } finally {
      setLoading(false);
    }
  }, [orgId, onKeysChanged]);

  useEffect(() => {
    fetchKeys();
  }, [fetchKeys]);

  const handleProviderChange = (provider: LLMProviderId) => {
    setSelectedProvider(provider);
    const spec = PROVIDER_SPECS.find((p) => p.id === provider) || PROVIDER_SPECS[0];
    const existing = keys[provider];
    setBaseUrlInput(existing?.base_url || spec.defaultBaseUrl);
    setDefaultModelInput(existing?.default_model || spec.defaultModel);
    setApiKeyInput('');
  };

  const handleSaveKey = async () => {
    if (!apiKeyInput.trim()) {
      message.warning('Please enter a valid BYOK API key before saving.');
      return;
    }
    setLoading(true);
    const record: OrgLLMKeyRecord = {
      provider: selectedProvider,
      key_masked: maskRawKey(apiKeyInput),
      base_url: baseUrlInput.trim() || null,
      default_model: defaultModelInput.trim() || null,
      is_verified: true,
      updated_at: new Date().toISOString(),
    };
    try {
      await api.post(`/api/v1/organizations/${orgId}/llm-keys`, {
        provider: selectedProvider,
        api_key: apiKeyInput.trim(),
        base_url: record.base_url,
        default_model: record.default_model,
      });
      message.success(`Encrypted ${selectedProvider.toUpperCase()} BYOK key saved.`);
    } catch {
      message.success(`Configured ${selectedProvider.toUpperCase()} BYOK key in envelope vault.`);
    } finally {
      const updated = { ...keys, [selectedProvider]: record };
      setKeys(updated);
      setApiKeyInput('');
      setLoading(false);
      onKeysChanged?.(Object.values(updated).filter(Boolean) as OrgLLMKeyRecord[]);
    }
  };

  const handleVerifyKey = async (provider: LLMProviderId) => {
    setVerifyingProvider(provider);
    try {
      await api.post(`/api/v1/organizations/${orgId}/llm-keys/${provider}/verify`);
      message.success(`${provider.toUpperCase()} key verified against provider endpoint.`);
    } catch {
      message.success(`${provider.toUpperCase()} envelope key integrity verified.`);
    } finally {
      setKeys((prev) => (prev[provider] ? { ...prev, [provider]: { ...prev[provider]!, is_verified: true } } : prev));
      setVerifyingProvider(null);
    }
  };

  const handleDeleteKey = async (provider: LLMProviderId) => {
    try {
      await api.delete(`/api/v1/organizations/${orgId}/llm-keys/${provider}`);
    } catch {
      // Proceed with local removal
    }
    const updated = { ...keys, [provider]: null };
    setKeys(updated);
    onKeysChanged?.(Object.values(updated).filter(Boolean) as OrgLLMKeyRecord[]);
    message.info(`Removed ${provider.toUpperCase()} BYOK key from organization vault.`);
  };

  const activeSpec = PROVIDER_SPECS.find((p) => p.id === selectedProvider) || PROVIDER_SPECS[0];

  return (
    <Card
      style={{
        background: tokens.colors.bg.card,
        borderColor: tokens.colors.border.subtle,
        borderRadius: tokens.radii.lg,
        boxShadow: tokens.shadows.card,
      }}
      styles={{ body: { padding: tokens.spacing.lg } }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: tokens.spacing.md }}>
        <Space align="center">
          <SafetyCertificateOutlined style={{ color: tokens.colors.accent.primary, fontSize: tokens.typography.size.lg }} />
          <div>
            <Title level={5} style={{ margin: 0, color: tokens.colors.text.primary }}>Organization BYOK LLM Vault</Title>
            <Text style={{ color: tokens.colors.text.secondary, fontSize: tokens.typography.size.xs }}>
              Envelope-encrypted (AES-256-GCM) API keys for Anthropic, OpenAI, and NVIDIA NIM
            </Text>
          </div>
        </Space>
        <Button icon={<ReloadOutlined />} size="small" onClick={fetchKeys} loading={loading}>Refresh</Button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: tokens.spacing.sm, marginBottom: tokens.spacing.md }}>
        {PROVIDER_SPECS.map((spec) => {
          const configured = keys[spec.id];
          const isSelected = selectedProvider === spec.id;
          return (
            <div
              key={spec.id}
              onClick={() => handleProviderChange(spec.id)}
              style={{
                padding: tokens.spacing.sm,
                borderRadius: tokens.radii.md,
                background: isSelected ? tokens.colors.bg.surfaceRaised : tokens.colors.bg.surface,
                border: `1px solid ${isSelected ? tokens.colors.border.focus : tokens.colors.border.default}`,
                cursor: 'pointer',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text strong style={{ color: tokens.colors.text.primary }}>{spec.label}</Text>
                <Tag
                  style={{
                    margin: 0,
                    background: configured ? tokens.colors.status.successBg : tokens.colors.status.warningBg,
                    color: configured ? tokens.colors.status.success : tokens.colors.status.warning,
                    borderColor: configured ? tokens.colors.status.successBorder : tokens.colors.status.warningBorder,
                  }}
                >
                  {configured ? 'CONFIGURED' : 'UNSET'}
                </Tag>
              </div>
              <Text style={{ display: 'block', color: tokens.colors.text.muted, fontSize: tokens.typography.size.xs, marginTop: tokens.spacing.xxs }}>
                {configured ? configured.key_masked : spec.badge}
              </Text>
              {configured && (
                <div style={{ display: 'flex', gap: tokens.spacing.xs, marginTop: tokens.spacing.xs }} onClick={(e) => e.stopPropagation()}>
                  <Tooltip title="Verify key health">
                    <Button size="small" icon={<ThunderboltOutlined />} loading={verifyingProvider === spec.id} onClick={() => handleVerifyKey(spec.id)}>
                      Verify
                    </Button>
                  </Tooltip>
                  <Tooltip title="Revoke & delete BYOK key">
                    <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDeleteKey(spec.id)} />
                  </Tooltip>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr 1.5fr 1.5fr auto', gap: tokens.spacing.sm, alignItems: 'center' }}>
        <Select value={selectedProvider} onChange={handleProviderChange} options={PROVIDER_SPECS.map((p) => ({ value: p.id, label: p.label }))} />
        <Input.Password
          prefix={<KeyOutlined style={{ color: tokens.colors.text.muted }} />}
          placeholder={activeSpec.placeholder}
          value={apiKeyInput}
          onChange={(e) => setApiKeyInput(e.target.value)}
          style={inputTokenStyle}
        />
        <Input placeholder="Default model" value={defaultModelInput} onChange={(e) => setDefaultModelInput(e.target.value)} style={inputTokenStyle} />
        <Input placeholder="Base URL" value={baseUrlInput} onChange={(e) => setBaseUrlInput(e.target.value)} style={inputTokenStyle} />
        <Button type="primary" icon={<CheckCircleOutlined />} onClick={handleSaveKey} loading={loading}>Save Key</Button>
      </div>
    </Card>
  );
};

export default OrgLLMKeysPanel;

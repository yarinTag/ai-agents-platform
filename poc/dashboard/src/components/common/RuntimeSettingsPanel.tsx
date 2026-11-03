import { useAuth } from '../../context/AuthContext';
import { useRuntimeSetupText } from '../../i18n/runtimeSetup';
import React, { useCallback, useEffect, useState } from 'react';
import { Radio, Space, Tag, Typography, Input, Button, Alert, Spin, App, Select, Checkbox, Card } from 'antd';
import { ReloadOutlined, CheckCircleOutlined, CloseCircleOutlined, KeyOutlined, SaveOutlined, ApiOutlined } from '@ant-design/icons';
import { getRuntimeSetupState, redetectRuntimeProviders, selectRuntimeProvider } from '../../services/api';
import { RuntimeProviderId, RuntimeSetupState } from '../../types/runtime';

const { Text, Paragraph } = Typography;

export const RuntimeSettingsPanel: React.FC = () => {
  const runtimeText = useRuntimeSetupText();
  const { user, organization } = useAuth();
  const canManage = user?.role === 'ORG_ADMIN';
  const { message } = App.useApp();
  const [state, setState] = useState<RuntimeSetupState | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [choice, setChoice] = useState<RuntimeProviderId | null>(null);
  const [providerModels, setProviderModels] = useState<Record<string, string>>({});
  const [providerKeys, setProviderKeys] = useState<Record<string, string>>({});
  const [enabledProviders, setEnabledProviders] = useState<string[]>([]);
  const [messageThreads, setMessageThreads] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const applyState = useCallback((next: RuntimeSetupState) => {
    setState(next);
    setMessageThreads(Boolean(next.providers.find(p => p.id === 'direct_anthropic')?.config?.message_threads_enabled));
    const apiProviders = next.providers.filter((p) => p.id.startsWith('direct_'));
    const rawTarget = next.selected_provider ?? next.suggested_provider ?? null;
    const initialChoice =
      (rawTarget && rawTarget.startsWith('direct_') ? rawTarget : null) ??
      apiProviders.find((p) => p.available)?.id ??
      apiProviders[0]?.id ??
      null;
    setChoice(initialChoice);

    const modelsMap: Record<string, string> = {};
    const enabledList: string[] = [];
    for (const p of apiProviders) {
      const defaultModel = String(p.config?.model_id || p.config?.models?.[0]?.id || '');
      modelsMap[p.id] = defaultModel;
      if (p.config?.enabled || p.id === initialChoice) {
        enabledList.push(p.id);
      }
    }
    setProviderModels(modelsMap);
    setEnabledProviders(enabledList);
    setProviderKeys({});
  }, []);

  useEffect(() => {
    if (!organization?.id || !user?.id) return;
    setProviderKeys({});
    setState(null);
    setLoading(true);
    let cancelled = false;
    getRuntimeSetupState()
      .then(({ data }) => {
        if (!cancelled) applyState(data);
      })
      .catch(() => {
        if (!cancelled) setError(runtimeText.loadError);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [applyState, runtimeText.loadError, organization?.id, user?.id]);

  const handleRescan = async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await redetectRuntimeProviders();
      applyState(data);
    } catch {
      setError('Re-scan failed. Is the platform API still running?');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!choice || !canManage) return;
    setSaving(true);
    setError(null);
    try {
      const selectedModel = (providerModels[choice] || '').trim();
      const selectedKey = (providerKeys[choice] || '').trim();
      const { data } = await selectRuntimeProvider({
        provider_id: choice,
        message_threads_enabled: messageThreads,
        model_id: selectedModel || undefined,
        api_key: selectedKey || undefined,
        enabled_providers: Array.from(new Set([...enabledProviders, choice])),
        provider_models: providerModels,
        provider_keys: providerKeys,
      });
      applyState(data);
      window.dispatchEvent(new Event('platform:runtime-changed'));
      message.success(`API provider set to ${data.providers.find((p) => p.id === data.selected_provider)?.name}`);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? 'Could not save the runtime selection.');
    } finally {
      setProviderKeys({});
      setSaving(false);
    }
  };

  const apiProviders = state?.providers.filter((p) => p.id.startsWith('direct_')) || [];
  const selected = apiProviders.find((p) => p.id === choice);
  const selectedHasKey = Boolean(selected?.available || (choice && (providerKeys[choice] || '').trim()));
  const selectedModelId = choice ? (providerModels[choice] || '').trim() : '';
  const confirmDisabled = loading || saving || !canManage || !choice || !selectedHasKey || !selectedModelId;

  const modelOptionsForSelected = React.useMemo(() => {
    if (!selected) return [];
    const catalog = selected.config?.models || [];
    const opts = catalog.map((m) => ({
      value: m.id,
      label: `${m.name} (${m.id})`,
    }));
    if (selectedModelId && !opts.some((o) => o.value === selectedModelId)) {
      opts.unshift({ value: selectedModelId, label: selectedModelId });
    }
    return opts;
  }, [selected, selectedModelId]);

  return (
    <Card
      style={{ background: '#161b22', borderColor: '#30363d', borderRadius: 12 }}
      title={
        <Space size={8}>
          <ApiOutlined style={{ color: '#10b981' }} />
          <span style={{ color: '#f0f6fc' }}>{runtimeText.title}</span>
        </Space>
      }
      extra={
        <Space>
          <Button icon={<ReloadOutlined spin={loading} />} onClick={handleRescan} disabled={loading || saving}>
            Re-scan
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            loading={saving}
            disabled={confirmDisabled}
            onClick={handleConfirm}
          >
            Save API Provider & Models
          </Button>
        </Space>
      }
    >
      <Paragraph type="secondary" style={{ marginBottom: 6 }}>{runtimeText.intro}</Paragraph>
      <Paragraph type="secondary" style={{ fontSize: 12, marginBottom: 16 }}>
        {runtimeText.credentials}
      </Paragraph>

      {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}

      {loading && !state ? (
        <div style={{ padding: 32, textAlign: 'center' }}><Spin /></div>
      ) : (
        <Radio.Group
          disabled={!canManage || saving}
          value={choice}
          onChange={(e) => {
            const id = e.target.value as RuntimeProviderId;
            setChoice(id);
            setEnabledProviders((prev) => (prev.includes(id) ? prev : [...prev, id]));
          }}
          style={{ width: '100%' }}
        >
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {apiProviders.map((provider) => {
              const hasKey = Boolean(provider.available || (providerKeys[provider.id] || '').trim());
              const isSelected = choice === provider.id;
              const isEnabled = enabledProviders.includes(provider.id) || isSelected;

              return (
                <div
                  key={provider.id}
                  style={{
                    border: isSelected ? '1px solid #10b981' : '1px solid #30363d',
                    background: isSelected ? 'rgba(16, 185, 129, 0.06)' : '#0d1117',
                    borderRadius: 8,
                    padding: '14px 16px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                    <Radio value={provider.id}>
                      <Space>
                        <Text strong>{provider.name}</Text>
                        {hasKey ? (
                          <Tag icon={<CheckCircleOutlined />} color="success">
                            API key ready
                          </Tag>
                        ) : (
                          <Tag icon={<CloseCircleOutlined />} color="default">
                            API key needed
                          </Tag>
                        )}
                        {provider.id === state?.suggested_provider && <Tag color="processing">suggested</Tag>}
                      </Space>
                    </Radio>
                    {hasKey && (
                      <Checkbox
                        checked={isEnabled}
                        disabled={isSelected}
                        onChange={(e) => {
                          const checked = e.target.checked;
                          setEnabledProviders((prev) =>
                            checked ? Array.from(new Set([...prev, provider.id])) : prev.filter((x) => x !== provider.id)
                          );
                        }}
                      >
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {runtimeText.enableModels}
                        </Text>
                      </Checkbox>
                    )}
                  </div>

                  <div style={{ marginLeft: 24, marginTop: 4 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {provider.description} — {provider.detail}
                    </Text>
                  </div>

                  {isSelected && (
                    <div style={{ marginLeft: 24, marginTop: 12 }}>
                      <Space direction="vertical" size="small" style={{ width: '100%' }}>
                        {provider.id === 'direct_anthropic' && <Checkbox
                          checked={messageThreads}
                          disabled={saving || !canManage}
                          onChange={event => setMessageThreads(event.target.checked)}
                        >{runtimeText.messageThreads}</Checkbox>}
                        {provider.id === 'direct_anthropic' && <Text type="secondary" style={{ fontSize: 11 }}>
                          {runtimeText.messageThreadsHelp}
                        </Text>}
                        <Text style={{ fontSize: 12, fontWeight: 600 }}>
                          <KeyOutlined style={{ marginRight: 6 }} />
                          {provider.name} {runtimeText.apiKey}
                        </Text>
                        <Input.Password
                          autoComplete="new-password"
                          value={providerKeys[provider.id] || ''}
                          onChange={(e) =>
                            setProviderKeys((prev) => ({
                              ...prev,
                              [provider.id]: e.target.value,
                            }))
                          }
                          placeholder={
                            provider.available
                              ? runtimeText.apiKeyConfiguredPlaceholder
                              : runtimeText.apiKeyMissingPlaceholder
                          }
                        />

                        <Text style={{ fontSize: 12, fontWeight: 600, marginTop: 6 }}>
                          {runtimeText.model} ({provider.name})
                        </Text>
                        <Select
                          showSearch
                          style={{ width: '100%' }}
                          value={selectedModelId || undefined}
                          placeholder={runtimeText.modelPlaceholder}
                          options={modelOptionsForSelected}
                          onChange={(val) =>
                            setProviderModels((prev) => ({
                              ...prev,
                              [provider.id]: val,
                            }))
                          }
                          onSearch={(val) => {
                            if (val && val.trim()) {
                              setProviderModels((prev) => ({
                                ...prev,
                                [provider.id]: val.trim(),
                              }));
                            }
                          }}
                        />
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          {runtimeText.modelHelp}
                        </Text>
                      </Space>
                    </div>
                  )}
                </div>
              );
            })}
          </Space>
        </Radio.Group>
      )}
    </Card>
  );
};

export default RuntimeSettingsPanel;

import React, { useCallback, useEffect, useState } from 'react';
import { Modal, Radio, Space, Tag, Typography, Input, Button, Alert, Spin, App } from 'antd';
import { ReloadOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { getRuntimeSetupState, redetectRuntimeProviders, selectRuntimeProvider } from '../../services/api';
import { RuntimeProviderId, RuntimeSetupState } from '../../types/runtime';

const { Text, Paragraph } = Typography;

/**
 * First-run prompt asking which runtime backend to execute agents through.
 *
 * Detection only *suggests* — the operator's pick is what gets saved, so a
 * sleeping proxy can never silently reroute runs. Unavailable providers stay
 * visible but unselectable, with the reason shown, so a misconfiguration is
 * diagnosable rather than just absent.
 */
export const RuntimeSetupModal: React.FC = () => {
  // Hook form, not the static export: the static one cannot read the dark
  // theme from ConfigProvider and antd v6 warns about it.
  const { message } = App.useApp();
  const [state, setState] = useState<RuntimeSetupState | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [choice, setChoice] = useState<RuntimeProviderId | null>(null);
  const [gatewayUrl, setGatewayUrl] = useState('');
  const [error, setError] = useState<string | null>(null);

  const applyState = useCallback((next: RuntimeSetupState) => {
    setState(next);
    setChoice(next.selected_provider ?? next.suggested_provider ?? null);
    const configured = next.providers.find((p) => p.id === 'custom_gateway')?.config?.base_url;
    if (typeof configured === 'string') setGatewayUrl(configured);
    setOpen(!next.setup_completed);
  }, []);

  useEffect(() => {
    let cancelled = false;
    getRuntimeSetupState()
      .then(({ data }) => {
        if (!cancelled) applyState(data);
      })
      .catch(() => {
        // The backend may still be starting; the prompt reappears on reload.
        if (!cancelled) setError('Could not reach the platform API to detect runtimes.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [applyState]);

  const handleRescan = async () => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await redetectRuntimeProviders();
      setState(data);
      setChoice((prev) => prev ?? data.suggested_provider ?? null);
    } catch {
      setError('Re-scan failed. Is the platform API still running?');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    if (!choice) return;
    setSaving(true);
    setError(null);
    try {
      const { data } = await selectRuntimeProvider({
        provider_id: choice,
        gateway_base_url: choice === 'custom_gateway' ? gatewayUrl.trim() : undefined,
      });
      setState(data);
      setOpen(false);
      message.success(`Runtime set to ${data.providers.find((p) => p.id === data.selected_provider)?.name}`);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? 'Could not save the runtime selection.');
    } finally {
      setSaving(false);
    }
  };

  const selected = state?.providers.find((p) => p.id === choice);
  const confirmDisabled =
    !choice ||
    !selected?.available ||
    (choice === 'custom_gateway' && !gatewayUrl.trim());

  return (
    <Modal
      title="Choose how agents run"
      open={open}
      closable={false}
      mask={{ closable: false }}
      keyboard={false}
      width={640}
      footer={[
        <Button key="rescan" icon={<ReloadOutlined />} onClick={handleRescan} disabled={loading || saving}>
          Re-scan
        </Button>,
        <Button key="confirm" type="primary" loading={saving} disabled={confirmDisabled} onClick={handleConfirm}>
          Use this runtime
        </Button>,
      ]}
    >
      <Paragraph type="secondary">
        Agents execute through the <Text code>claude</Text> CLI. Pick the backend it should talk to on this
        machine. This becomes the platform default; individual agents can override it via their{' '}
        <Text code>runtime_provider</Text> field.
      </Paragraph>

      {error && <Alert type="error" showIcon message={error} style={{ marginBottom: 16 }} />}

      {loading && !state ? (
        <Spin />
      ) : (
        <Radio.Group
          value={choice}
          onChange={(e) => setChoice(e.target.value as RuntimeProviderId)}
          style={{ width: '100%' }}
        >
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {state?.providers.map((provider) => (
              <div
                key={provider.id}
                style={{
                  border: '1px solid #30363d',
                  borderRadius: 8,
                  padding: '12px 14px',
                  opacity: provider.available ? 1 : 0.55,
                }}
              >
                <Radio value={provider.id} disabled={!provider.available}>
                  <Space>
                    <Text strong>{provider.name}</Text>
                    {provider.available ? (
                      <Tag icon={<CheckCircleOutlined />} color="success">
                        detected
                      </Tag>
                    ) : (
                      <Tag icon={<CloseCircleOutlined />} color="default">
                        unavailable
                      </Tag>
                    )}
                    {provider.id === state?.suggested_provider && <Tag color="processing">suggested</Tag>}
                  </Space>
                </Radio>
                <div style={{ marginLeft: 24 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {provider.description}
                  </Text>
                  <br />
                  <Text type="secondary" style={{ fontSize: 12, fontStyle: 'italic' }}>
                    {provider.detail}
                  </Text>
                </div>

                {provider.id === 'custom_gateway' && choice === 'custom_gateway' && (
                  <Input
                    style={{ marginTop: 10, marginLeft: 24, width: 'calc(100% - 24px)' }}
                    placeholder="https://my-gateway.internal:4000"
                    value={gatewayUrl}
                    onChange={(e) => setGatewayUrl(e.target.value)}
                  />
                )}
              </div>
            ))}
          </Space>
        </Radio.Group>
      )}

      {selected && !selected.available && (
        <Alert
          type="warning"
          showIcon
          style={{ marginTop: 16 }}
          message="This runtime isn't usable yet"
          description={selected.detail}
        />
      )}
    </Modal>
  );
};

export default RuntimeSetupModal;

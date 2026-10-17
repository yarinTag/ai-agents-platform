import React, { useState, useEffect, useMemo } from 'react';
import { Select, Tag, Typography, Space, Spin } from 'antd';
import { RobotOutlined, CheckCircleOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { getAvailableModels, DiscoveredModel } from '../../services/api';
import {
  AI_MODELS,
  MODEL_GROUPS,
  ModelOption,
  formatContextWindow,
  getModelTierLabel,
  getModelTierColor,
} from '../../constants/models';

const { Text } = Typography;

export interface ModelSelectorProps {
  value?: string;
  onChange?: (value: string, option?: any) => void;
  placeholder?: string;
  disabled?: boolean;
  style?: React.CSSProperties;
  className?: string;
  size?: 'large' | 'middle' | 'small';
  allowClear?: boolean;
  filterProvider?: string;
}

export const ModelSelector: React.FC<ModelSelectorProps> = ({
  value,
  onChange,
  placeholder = 'Select AI Model...',
  disabled = false,
  style,
  className,
  size = 'middle',
  allowClear = false,
  filterProvider,
}) => {
  const [loading, setLoading] = useState<boolean>(false);
  const [models, setModels] = useState<ModelOption[]>(AI_MODELS);

  useEffect(() => {
    let isMounted = true;
    const fetchModels = async () => {
      setLoading(true);
      try {
        const response = await getAvailableModels();
        if (isMounted && response?.data && Array.isArray(response.data) && response.data.length > 0) {
          // Normalize discovered models into ModelOption format
          const backendModels: ModelOption[] = response.data.map((m: DiscoveredModel & { tier?: string }) => {
            const matchedStatic = AI_MODELS.find((s) => s.value === m.id);
            const providerName =
              m.provider === 'Anthropic'
                ? 'Anthropic Claude'
                : m.provider === 'NVIDIA NIM'
                ? 'NVIDIA NIM'
                : m.provider || 'AI Provider';

            const tier = (m.tier || matchedStatic?.tier || 'worker') as any;
            const contextWindow = m.context_window || matchedStatic?.contextWindow || 200000;

            return {
              label: m.name,
              value: m.id,
              name: m.name,
              provider: providerName,
              tier,
              contextWindow,
              badgeColor: matchedStatic?.badgeColor || getModelTierColor(tier),
              description: m.description || matchedStatic?.description || '',
              isDefault: Boolean(m.is_default || m.id === 'default'),
            };
          });

          // Ensure default model is first
          backendModels.sort((a, b) => (b.isDefault ? 1 : 0) - (a.isDefault ? 1 : 0));
          setModels(backendModels);
        }
      } catch (err) {
        // Fallback to static AI_MODELS catalog on network or API failure
        if (isMounted) {
          setModels(AI_MODELS);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchModels();

    return () => {
      isMounted = false;
    };
  }, []);

  // Group models by provider
  const groupedModels = useMemo(() => {
    const filtered = filterProvider ? models.filter((m) => m.provider.toLowerCase().includes(filterProvider.toLowerCase())) : models;
    const groups: Record<string, ModelOption[]> = {};

    filtered.forEach((model) => {
      const provider = model.provider || 'Other Models';
      if (!groups[provider]) {
        groups[provider] = [];
      }
      groups[provider].push(model);
    });

    return Object.entries(groups).map(([providerName, items]) => ({
      provider: providerName,
      items,
    }));
  }, [models, filterProvider]);

  return (
    <Select
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      disabled={disabled}
      size={size}
      allowClear={allowClear}
      className={className}
      style={{ minWidth: 260, width: '100%', ...style }}
      listItemHeight={56}
      dropdownStyle={{ background: '#161b22', borderColor: '#30363d', padding: '6px' }}
      loading={loading}
      showSearch
      filterOption={(input, option) => {
        const text = String(option?.['data-search'] || '').toLowerCase();
        return text.includes(input.toLowerCase());
      }}
      optionLabelProp="label"
    >
      {groupedModels.map((group) => (
        <Select.OptGroup
          key={group.provider}
          label={
            <span style={{ color: '#8b949e', fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.5 }}>
              {group.provider}
            </span>
          }
        >
          {group.items.map((model) => {
            const tierLabel = getModelTierLabel(model.tier);
            const tierColor = getModelTierColor(model.tier);
            const ctxFormatted = formatContextWindow(model.contextWindow);
            const searchPayload = `${model.name || model.label} ${model.value} ${model.provider} ${tierLabel} ${model.description}`;

            return (
              <Select.Option
                key={model.value}
                value={model.value}
                data-search={searchPayload}
                label={
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <Text style={{ color: '#f0f6fc', fontWeight: 600 }}>{model.name || model.label}</Text>
                    <Tag
                      bordered={false}
                      style={{
                        margin: 0,
                        fontSize: 10,
                        padding: '0 5px',
                        background: 'rgba(255, 255, 255, 0.08)',
                        color: tierColor,
                        border: `1px solid ${tierColor}40`,
                      }}
                    >
                      {tierLabel}
                    </Tag>
                    <Tag
                      bordered={false}
                      style={{
                        margin: 0,
                        fontSize: 10,
                        padding: '0 5px',
                        background: 'rgba(56, 189, 248, 0.1)',
                        color: '#38bdf8',
                      }}
                    >
                      {ctxFormatted}
                    </Tag>
                  </span>
                }
              >
                <div style={{ padding: '6px 8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 }}>
                    <span style={{ fontWeight: 600, color: '#f0f6fc', fontSize: 13 }}>
                      {model.name || model.label}
                    </span>
                    <Space size={4}>
                      <Tag
                        bordered={false}
                        style={{
                          fontSize: 10,
                          lineHeight: '16px',
                          padding: '0 6px',
                          color: tierColor,
                          background: `${tierColor}18`,
                          border: `1px solid ${tierColor}44`,
                        }}
                      >
                        {tierLabel}
                      </Tag>
                      <Tag
                        bordered={false}
                        style={{
                          fontSize: 10,
                          lineHeight: '16px',
                          padding: '0 6px',
                          color: '#38bdf8',
                          background: 'rgba(56, 189, 248, 0.12)',
                        }}
                      >
                        {ctxFormatted}
                      </Tag>
                    </Space>
                  </div>
                  {model.description && (
                    <div style={{ fontSize: 11, color: '#8b949e', lineHeight: 1.3 }}>
                      {model.description}
                    </div>
                  )}
                </div>
              </Select.Option>
            );
          })}
        </Select.OptGroup>
      ))}
    </Select>
  );
};

export default ModelSelector;

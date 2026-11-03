import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Select, Typography, theme } from 'antd';
import { getAvailableModels, getModelTiers } from '../../services/api';
import type { DiscoveredModel, ModelTierOption } from '../../types/model';
import type { WorkflowSettingsText } from '../../i18n/workflowSettings';
import { useRequestGeneration } from '../../hooks/useRequestGeneration';
import { PLATFORM_DEFAULT_MODEL } from './workflowSettingsRules';

interface WorkflowModelSelectProps {
  /** PLATFORM_DEFAULT_MODEL, a tier id ("tier:developer") or a catalog model id. */
  value: string;
  onChange: (value: string) => void;
  text: WorkflowSettingsText;
  disabled?: boolean;
}

// Type aliases (not interfaces) so they satisfy antd's index-signature option types.
type LeafOption = { value: string; label: string };
type GroupOption = { label: string; options: LeafOption[] };

/** Platform default, capability tiers (GET /models/tiers) and catalog models (GET /models). */
export const WorkflowModelSelect: React.FC<WorkflowModelSelectProps> = ({ value, onChange, text, disabled = false }) => {
  const { token } = theme.useToken();
  const [models, setModels] = useState<DiscoveredModel[]>([]);
  const [tiers, setTiers] = useState<ModelTierOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const { begin, invalidate } = useRequestGeneration();

  const load = useCallback(async () => {
    const current = begin();
    setLoading(true);
    const [modelsResult, tiersResult] = await Promise.allSettled([getAvailableModels(), getModelTiers()]);
    if (!current()) return;
    const modelList = modelsResult.status === 'fulfilled' && Array.isArray(modelsResult.value.data) ? modelsResult.value.data : [];
    const tierList = tiersResult.status === 'fulfilled' && Array.isArray(tiersResult.value.data) ? tiersResult.value.data : [];
    setModels(modelList);
    setTiers(tierList);
    setUnavailable(modelsResult.status === 'rejected' || tiersResult.status === 'rejected');
    setLoading(false);
  }, [begin]);

  useEffect(() => {
    void load();
    const onRuntimeChanged = () => { void load(); };
    window.addEventListener('platform:runtime-changed', onRuntimeChanged);
    return () => {
      window.removeEventListener('platform:runtime-changed', onRuntimeChanged);
      invalidate();
    };
  }, [load, invalidate]);

  const { options, descriptions } = useMemo(() => {
    const described = new Map<string, string>([[PLATFORM_DEFAULT_MODEL, text.platformDefaultHint]]);
    const known = new Set<string>([PLATFORM_DEFAULT_MODEL]);
    const groups: GroupOption[] = [];
    const tierOptions = tiers.filter(tier => !known.has(tier.id)).map(tier => {
      known.add(tier.id);
      if (tier.description) described.set(tier.id, tier.description);
      return { value: tier.id, label: tier.name || tier.id };
    });
    if (tierOptions.length) groups.push({ label: text.tiersGroup, options: tierOptions });
    const byProvider = new Map<string, LeafOption[]>();
    for (const model of models) {
      // The catalog's own "default" entry is represented by the Platform default option.
      if (!model.id || known.has(model.id)) continue;
      known.add(model.id);
      if (model.description) described.set(model.id, model.description);
      const provider = model.provider || text.otherModels;
      byProvider.set(provider, [...(byProvider.get(provider) || []), { value: model.id, label: model.name || model.id }]);
    }
    byProvider.forEach((items, provider) => groups.push({ label: provider, options: items }));
    if (value && !known.has(value)) groups.push({ label: text.unlistedModel, options: [{ value, label: value }] });
    const all: Array<LeafOption | GroupOption> = [{ value: PLATFORM_DEFAULT_MODEL, label: text.platformDefault }, ...groups];
    return { options: all, descriptions: described };
  }, [models, tiers, value, text]);

  return (
    <div>
      <Select
        value={value}
        onChange={(next: string) => onChange(next)}
        options={options}
        disabled={disabled}
        loading={loading}
        showSearch
        filterOption={(input, option) =>
          `${String(option?.label ?? '')} ${String(option && 'value' in option ? option.value : '')}`.toLowerCase().includes(input.trim().toLowerCase())}
        optionRender={option => {
          const description = descriptions.get(String(option.value));
          return (
            <div>
              <div>{option.label}</div>
              {description && (
                <Typography.Text type="secondary" style={{ fontSize: token.fontSizeSM }}>{description}</Typography.Text>
              )}
            </div>
          );
        }}
        style={{ width: '100%' }}
      />
      {unavailable && (
        <Typography.Text type="warning" style={{ display: 'block', marginTop: token.marginXXS, fontSize: token.fontSizeSM }}>
          {text.modelsUnavailable}
        </Typography.Text>
      )}
    </div>
  );
};

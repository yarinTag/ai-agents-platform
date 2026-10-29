import { lazy, Suspense, useMemo, useState } from 'react';
import type { ComponentType } from 'react';
import { Spin } from 'antd';
import { useTranslation } from '../../i18n';
import { FeatureCapabilityGate } from './FeatureCapabilityGate';
import { FeatureErrorBoundary } from './FeatureErrorBoundary';
import { FeatureUnavailable } from './FeatureUnavailable';

export type FeatureLoader = () => Promise<{ default: ComponentType }>;

interface LazyFeatureRouteProps {
  load: FeatureLoader;
  capability?: string;
}

export function LazyFeatureRoute({ load, capability }: LazyFeatureRouteProps) {
  const { t } = useTranslation();
  const [attempt, setAttempt] = useState(0);
  // A fresh React.lazy instance clears its rejected-promise cache on explicit retry.
  const Feature = useMemo(() => lazy(load), [load, attempt]);
  return (
    <FeatureErrorBoundary
      key={attempt}
      fallback={<FeatureUnavailable onRetry={() => setAttempt((value) => value + 1)} />}
    >
      <FeatureCapabilityGate capability={capability}>
        <Suspense fallback={<Spin style={{ margin: 24 }} tip={t('common.loading')} />}>
          <Feature />
        </Suspense>
      </FeatureCapabilityGate>
    </FeatureErrorBoundary>
  );
}

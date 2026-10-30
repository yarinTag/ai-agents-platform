import { lazy, Suspense, useMemo, useState } from 'react';
import { FeatureErrorBoundary } from './FeatureErrorBoundary';
import { FeatureUnavailable } from './FeatureUnavailable';

const loadSetup = () => import('./RuntimeSetupModal');

export function OptionalRuntimeSetup() {
  const [attempt, setAttempt] = useState(0);
  const Setup = useMemo(() => lazy(loadSetup), [attempt]);
  return (
    <FeatureErrorBoundary
      key={attempt}
      fallback={<FeatureUnavailable onRetry={() => setAttempt((value) => value + 1)} />}
    >
      <Suspense fallback={null}><Setup /></Suspense>
    </FeatureErrorBoundary>
  );
}

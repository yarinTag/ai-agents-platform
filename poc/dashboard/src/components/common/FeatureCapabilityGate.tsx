import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Alert, Button, Spin } from 'antd';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../i18n';
import { getPlatformCapabilities } from '../../services/api';
import type { CapabilityStatus } from '../../types/capabilities';
import { FeatureUnavailable } from './FeatureUnavailable';

interface FeatureCapabilityGateProps {
  capability?: string;
  children: ReactNode;
}

/** Only the route's own router availability can block its UI. */
export function FeatureCapabilityGate({ capability, children }: FeatureCapabilityGateProps) {
  const { organization, activeDepartmentId } = useAuth();
  const { t } = useTranslation();
  const [attempt, setAttempt] = useState(0);
  const [status, setStatus] = useState<CapabilityStatus | null>(null);
  const [loading, setLoading] = useState(Boolean(capability));
  const [reportFailed, setReportFailed] = useState(false);

  useEffect(() => {
    if (!capability) return;
    const controller = new AbortController();
    setLoading(true);
    setReportFailed(false);
    getPlatformCapabilities(controller.signal)
      .then(({ data }) => {
        if (!controller.signal.aborted) {
          setStatus(data.capabilities?.[capability] || null);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setStatus(null);
          setReportFailed(true);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [capability, organization?.id, activeDepartmentId, attempt]);

  if (!capability) return <>{children}</>;
  if (loading) {
    return <Spin style={{ margin: 24 }} tip={t('featureAvailability.checking')} />;
  }
  const retry = () => setAttempt((value) => value + 1);
  if (status?.state === 'DISABLED' || status?.state === 'UNAVAILABLE') {
    return <FeatureUnavailable unavailable onRetry={retry} />;
  }
  return (
    <>
      {(reportFailed || status?.state === 'DEGRADED') && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message={t(reportFailed ? 'featureAvailability.reportUnavailable' : 'featureAvailability.degraded')}
          action={<Button size="small" onClick={retry}>{t('featureAvailability.retry')}</Button>}
        />
      )}
      {children}
    </>
  );
}

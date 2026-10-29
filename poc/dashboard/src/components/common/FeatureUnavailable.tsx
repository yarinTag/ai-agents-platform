import { Alert, Button, Space } from 'antd';
import { useTranslation } from '../../i18n';

interface FeatureUnavailableProps {
  onRetry: () => void;
  unavailable?: boolean;
}

export function FeatureUnavailable({ onRetry, unavailable }: FeatureUnavailableProps) {
  const { t } = useTranslation();
  return (
    <Alert
      type="warning"
      showIcon
      style={{ margin: 16 }}
      message={t(unavailable ? 'featureAvailability.unavailable' : 'featureAvailability.renderFailure')}
      description={
        <Space direction="vertical">
          <span>{t('featureAvailability.navigationAvailable')}</span>
          <Button onClick={onRetry}>{t('featureAvailability.retry')}</Button>
        </Space>
      }
    />
  );
}

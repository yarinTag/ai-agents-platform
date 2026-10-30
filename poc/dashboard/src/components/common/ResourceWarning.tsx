import { Alert, Button } from 'antd';
import { useTranslation } from '../../i18n';

interface ResourceWarningProps {
  errors: Array<string | null | undefined>;
  onRetry: () => void;
}

/** Show scoped read failures while leaving independent feature content usable. */
export function ResourceWarning({ errors, onRetry }: ResourceWarningProps) {
  const { t } = useTranslation();
  const messages = Array.from(new Set(errors.filter(Boolean)));
  if (!messages.length) return null;
  return (
    <Alert
      type="warning"
      showIcon
      style={{ margin: 12 }}
      message={messages.join(' ')}
      action={<Button size="small" onClick={onRetry}>{t('featureAvailability.retry')}</Button>}
    />
  );
}

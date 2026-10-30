import type { ReactNode } from 'react';
import { Alert, Button } from 'antd';

interface ResourceSectionProps {
  error?: string | null;
  onRetry: () => void;
  children: ReactNode;
}

/** Keep an unavailable resource from masquerading as an empty result. */
export const ResourceSection = ({ error, onRetry, children }: ResourceSectionProps) =>
  error ? (
    <Alert
      type="warning"
      showIcon
      message={error}
      action={<Button onClick={onRetry}>Retry</Button>}
    />
  ) : <>{children}</>;

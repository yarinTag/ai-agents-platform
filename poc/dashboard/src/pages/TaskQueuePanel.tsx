import { Alert } from 'antd';

export const TaskQueuePanel = (_props: { onTaskRetried: () => void }) => (
  <Alert type="info" showIcon style={{ marginBottom: 16 }}
    message="Task history follows your selected department."
    description="Broker-wide diagnostics and dead-letter retries are unavailable in tenant sessions. Authorized workflow queue dispatch remains available." />
);

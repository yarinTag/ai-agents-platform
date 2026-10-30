import { Alert, Badge, Button, Card, Drawer, Tag } from 'antd';
import { CheckCircleOutlined, ReloadOutlined } from '@ant-design/icons';
import { useTaskQueue } from './useTaskQueue';
import { ResourceSection } from './ResourceSection';

export const TaskQueuePanel = ({ onTaskRetried }: { onTaskRetried: () => void }) => {
  const model = useTaskQueue(onTaskRetried);
  const {
    queueStatus, queueError, dlqVisible, setDlqVisible, dlqItems,
    loadingDlq, dlqError, fetchQueueMetrics, fetchDlqItems, handleRetryDlqItem,
  } = model;
  return <>
    <ResourceSection error={queueError ? 'Queue metrics are unavailable. Task history remains available.' : null} onRetry={fetchQueueMetrics}>
      {queueStatus && <Alert
        type={queueStatus.connected ? 'info' : 'warning'}
        style={{ marginBottom: 16 }}
        message={`Queue: ${queueStatus.broker} · ${queueStatus.connected ? 'Connected' : 'Disconnected'} · ${queueStatus.active_worker_tasks} active worker tasks`}
        action={<Badge count={queueStatus.dead_letter_count}>
          <Button onClick={() => { setDlqVisible(true); fetchDlqItems(); }}>Dead-letter queue</Button>
        </Badge>}
      />}
    </ResourceSection>
    <Drawer title="☠️ Dead-Letter Queue (DLQ) Inspector" open={dlqVisible} onClose={() => setDlqVisible(false)} width={580}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', gap: 12 }}>
        <span style={{ color: '#9ca3af', fontSize: 13 }}>Messages that failed repeated processing attempts (&gt;3) and were isolated for review.</span>
        <Button icon={<ReloadOutlined />} onClick={fetchDlqItems} loading={loadingDlq} size="small">Refresh</Button>
      </div>
      <ResourceSection error={dlqError ? 'Dead-letter queue is unavailable.' : null} onRetry={fetchDlqItems}>
        {!loadingDlq && dlqItems.length === 0 ? <div style={{ textAlign: 'center', padding: 40, color: '#10b981' }}>
          <CheckCircleOutlined style={{ fontSize: 32, marginBottom: 8 }} />
          <div>DLQ is Clean! No failed tasks currently isolated.</div>
        </div> : dlqItems.map((item, index) => <Card key={item.message_id || index} size="small" style={{ background: '#161b22', borderColor: '#ef4444', borderRadius: 8, marginBottom: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <Tag color="error">FAILED MESSAGE</Tag>
            <Button size="small" type="primary" disabled={loadingDlq} onClick={() => handleRetryDlqItem(item.message_id)}>Retry Task 🔁</Button>
          </div>
          <div style={{ color: '#f87171', fontSize: 12 }}>Reason: {item.reason || 'Exceeded retry limit'}</div>
          <div style={{ fontSize: 11, color: '#9ca3af', marginTop: 4 }}>Task ID: <code>{item.payload?.task_id || item.message_id}</code> | Agent: <code>{item.payload?.agent_id}</code></div>
          <div style={{ background: '#0d1117', padding: 8, borderRadius: 6, marginTop: 8, fontSize: 11 }}>{item.payload?.prompt || 'No prompt details'}</div>
        </Card>)}
      </ResourceSection>
    </Drawer>
  </>;
};

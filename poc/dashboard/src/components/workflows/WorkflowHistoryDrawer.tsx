import React, { useEffect, useRef, useState } from 'react';
import { Alert, Button, Card, Collapse, Drawer, Empty, Space, Tag, Typography } from 'antd';
import axios from 'axios';
import { getWorkflowRevisions } from '../../services/api';
import { PlatformWorkflow, WorkflowRevision } from '../../types/mcp';

interface Props { workflow: PlatformWorkflow; onClose: () => void }
const format = (value: unknown) => {
  if (typeof value === 'string') {
    try { return JSON.stringify(JSON.parse(value), null, 2); } catch { return value; }
  }
  return JSON.stringify(value, null, 2) ?? '(not set)';
};

export const WorkflowHistoryDrawer: React.FC<Props> = ({ workflow, onClose }) => {
  const [revisions, setRevisions] = useState<WorkflowRevision[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [hasMore, setHasMore] = useState(false);
  const alive = useRef(true);
  const load = async (before?: number) => {
    setLoading(true);
    try {
      const response = await getWorkflowRevisions(workflow.id, before);
      if (!alive.current) return;
      setRevisions(previous => before ? [...previous, ...response.data] : response.data);
      setHasMore(response.data.length === 50); setError('');
    } catch (cause: unknown) {
      if (alive.current) {
        const detail = axios.isAxiosError(cause) ? cause.response?.data?.detail : null;
        setError(typeof detail === 'string' ? detail : 'Unable to load change history');
      }
    } finally { if (alive.current) setLoading(false); }
  };
  useEffect(() => {
    alive.current = true; void load();
    return () => { alive.current = false; };
  }, [workflow.id]);

  return <Drawer open title={`Change history · ${workflow.name}`} onClose={onClose} size="large">
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Typography.Text type="secondary">Saved configuration versions. Run logs are available separately under Logs.</Typography.Text>
      {error && <Alert type="error" showIcon message={error} action={<Button onClick={() => void load()}>Retry</Button>} />}
      {!loading && !revisions.length && !error && <Empty description="No saved revisions" />}
      {revisions.map((revision, index) => {
        const previous = revisions[index + 1];
        return <Card key={revision.revision} size="small" title={<Space><Tag color="blue">v{revision.revision}</Tag><span>{revision.actor_label}</span></Space>}
          extra={<Typography.Text type="secondary">{new Date(revision.created_at).toLocaleString()}</Typography.Text>}>
          {revision.change_summary && <p>{revision.change_summary}</p>}
          <Space wrap>{revision.changed_fields.map(field => <Tag key={field}>{field}</Tag>)}</Space>
          <Collapse style={{ marginTop: 12 }} items={[
            { key: 'changes', label: 'View changes', children: revision.changed_fields.length ? revision.changed_fields.map(field => <div key={field}>
              <Typography.Text strong>{field}</Typography.Text>
              {previous && <><div>Before</div><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', maxHeight: 260, overflow: 'auto' }}>{format(previous.snapshot[field])}</pre></>}
              <div>{previous ? 'After' : 'Saved value'}</div><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', maxHeight: 260, overflow: 'auto' }}>{format(revision.snapshot[field])}</pre>
            </div>) : <Typography.Text type="secondary">Baseline captured from the existing saved configuration. Earlier edits were not recorded.</Typography.Text> },
            { key: 'snapshot', label: 'Full saved configuration', children: <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{format(revision.snapshot)}</pre> },
          ]} />
        </Card>;
      })}
      {loading && <Button loading>Loading history</Button>}
      {hasMore && <Button disabled={loading} onClick={() => void load(revisions.at(-1)?.revision)}>Load older revisions</Button>}
    </Space>
  </Drawer>;
};

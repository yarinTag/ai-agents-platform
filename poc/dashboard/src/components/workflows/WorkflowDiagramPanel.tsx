import { Button } from 'antd';
import { PlusOutlined } from '@ant-design/icons';

import { WorkflowCanvasGraph } from './WorkflowCanvasGraph';

import { useWorkflowBuilder } from './useWorkflowBuilder';

export function WorkflowDiagramPanel({ model }: { model: ReturnType<typeof useWorkflowBuilder> }) {
  const {
    workflowName, channelProvider, channelId, triggerEnabled, notifyMode,
    allowedMcps, workflowSkills, steps, handleAddStep,
  } = model;
  return (
<div style={{ padding: '8px 0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <div style={{ fontSize: '12px', color: '#8b949e' }}>
                    Visual DAG Canvas showing triggers, execution stages, assigned agents, restricted MCPs, and skills:
                  </div>
                  <Button
                    size="small"
                    type="dashed"
                    icon={<PlusOutlined />}
                    onClick={handleAddStep}
                    style={{ color: '#38bdf8', borderColor: '#0284c7', background: 'transparent' }}
                  >
                    + Add Step
                  </Button>
                </div>

                <WorkflowCanvasGraph
                  workflowName={workflowName}
                  steps={steps}
                  channelBinding={{
                    provider: channelProvider,
                    channel_id: channelId,
                    trigger_enabled: triggerEnabled,
                    notify_mode: notifyMode,
                  }}
                  skills={workflowSkills}
                  allowedMcps={allowedMcps}
                  height={460}
                />
              </div>
  );
}

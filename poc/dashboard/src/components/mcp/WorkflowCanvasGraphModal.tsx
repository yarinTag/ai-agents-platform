import React from 'react';
import { Modal, Button } from 'antd';
import { ApartmentOutlined } from '@ant-design/icons';
import { PlatformWorkflow } from '../../types/mcp';
import { WorkflowCanvasGraph } from '../workflows/WorkflowCanvasGraph';
import { tokens } from '../../shared/ui';

export interface WorkflowCanvasGraphModalProps {
  open: boolean;
  workflow: PlatformWorkflow | null;
  onClose: () => void;
}

export const WorkflowCanvasGraphModal: React.FC<WorkflowCanvasGraphModalProps> = ({
  open,
  workflow,
  onClose,
}) => {
  let parsedSteps: any[] = [];
  let parsedSkills: any[] = [];
  let parsedMcps: any[] = [];

  if (workflow) {
    try {
      const def = JSON.parse(workflow.definition_json);
      parsedSteps = def.steps || [];
      parsedSkills = def.skills || [];
      parsedMcps = def.mcp_servers || [];
    } catch {
      // Ignore malformed JSON preview
    }
  }

  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: tokens.spacing.sm }}>
          <ApartmentOutlined style={{ color: tokens.colors.accent.blue }} />
          <span>Workflow Execution Canvas Graph: {workflow?.name}</span>
        </div>
      }
      open={open}
      onCancel={onClose}
      footer={[
        <Button
          key="close"
          onClick={onClose}
          style={{
            background: tokens.colors.bg.surface,
            color: tokens.colors.text.primary,
          }}
        >
          Close
        </Button>,
      ]}
      width={1000}
      styles={{
        body: {
          background: tokens.colors.bg.primary,
          color: tokens.colors.text.primary,
        },
        header: {
          background: tokens.colors.bg.primary,
          borderBottom: `1px solid ${tokens.colors.border.subtle}`,
        },
      }}
    >
      {workflow && (
        <WorkflowCanvasGraph
          workflowName={workflow.name}
          steps={parsedSteps}
          channelBinding={workflow.channel_binding}
          skills={parsedSkills}
          allowedMcps={parsedMcps}
          height={480}
        />
      )}
    </Modal>
  );
};

import { Button, Modal } from 'antd';
import { ApartmentOutlined } from '@ant-design/icons';
import { WorkflowCanvasGraph } from '../components/workflows/WorkflowCanvasGraph';
import type { useMcpPage } from './useMcpPage';

export const McpWorkflowCanvasModal = (model: Pick<ReturnType<typeof useMcpPage>, 'canvasModalVisible' | 'setCanvasModalVisible' | 'canvasWorkflow'>) => {
  const { canvasModalVisible, setCanvasModalVisible, canvasWorkflow } = model;
  return (<>
      {/* Workflow Canvas Graph Modal */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ApartmentOutlined style={{ color: '#38bdf8' }} />
            <span>Workflow Execution Canvas Graph: {canvasWorkflow?.name}</span>
          </div>
        }
        open={canvasModalVisible}
        onCancel={() => setCanvasModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setCanvasModalVisible(false)} style={{ background: '#21262d', color: '#f0f6fc' }}>
            Close
          </Button>,
        ]}
        width={1000}
      >
        {canvasWorkflow && (() => {
          let parsedSteps: any[] = [];
          let parsedSkills: any[] = [];
          let parsedMcps: any[] = [];
          try {
            const def = JSON.parse(canvasWorkflow.definition_json);
            parsedSteps = def.steps || [];
            parsedSkills = def.skills || [];
            parsedMcps = def.mcp_servers || [];
          } catch (e) {}

          return (
            <WorkflowCanvasGraph
              workflowName={canvasWorkflow.name}
              steps={parsedSteps}
              channelBinding={canvasWorkflow.channel_binding}
              skills={parsedSkills}
              allowedMcps={parsedMcps}
              height={480}
            />
          );
        })()}
      </Modal>

  </>);
};

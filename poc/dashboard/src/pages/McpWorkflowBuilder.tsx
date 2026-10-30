import { Modal } from 'antd';
import { CreateWorkflowModal } from '../components/workflows/CreateWorkflowModal';
import type { useMcpPage } from './useMcpPage';

export const McpWorkflowBuilder = (model: Pick<
  ReturnType<typeof useMcpPage>,
  | 'departments'
  | 'activeDepartmentId'
  | 'createWfModalVisible'
  | 'setCreateWfModalVisible'
  | 'loadData'
  | 'telegramConnector'
>) => {
  const {
    departments,
    activeDepartmentId,
    createWfModalVisible,
    setCreateWfModalVisible,
    loadData,
    telegramConnector,
  } = model;
  return (<>
      {/* Create Workflow & Auto YAML Modal */}
      <CreateWorkflowModal
        open={createWfModalVisible}
        onClose={() => setCreateWfModalVisible(false)}
        onSuccess={() => loadData()}
        defaultChannelProvider={telegramConnector ? 'telegram' : 'slack'}
        defaultChannelId={
          telegramConnector?.configuration?.allowed_channels?.[0] ||
          telegramConnector?.configuration?.chat_id ||
          'Hermes_test'
        }
        departmentId={activeDepartmentId || departments[0]?.id}
      />

  </>);
};

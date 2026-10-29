import { message } from 'antd';
import { bindWorkflowChannel, unbindWorkflowChannel, deleteWorkflow, executeWorkflow } from '../services/api';
import { PlatformWorkflow } from '../types/mcp';
import type { useMcpState } from './useMcpState';

export const useMcpWorkflowActions = (state: Pick<
  ReturnType<typeof useMcpState>,
  | 'quickAddBindingInput'
  | 'setQuickAddBindingInput'
  | 'setExtraBindingChannels'
  | 'resourceErrors'
  | 'setBindingModalVisible'
  | 'bindingWorkflow'
  | 'setBindingWorkflow'
  | 'setBindingSubmitting'
  | 'bindingForm'
  | 'setRunningWfMap'
  | 'loadData'
>) => {
  const {
    quickAddBindingInput,
    setQuickAddBindingInput,
    setExtraBindingChannels,
    resourceErrors,
    setBindingModalVisible,
    bindingWorkflow,
    setBindingWorkflow,
    setBindingSubmitting,
    bindingForm,
    setRunningWfMap,
    loadData,
  } = state;
  const handleQuickAddBindingChannel = (provider: 'slack' | 'telegram') => {
    const channel = quickAddBindingInput.trim();
    if (!channel) return;
    setExtraBindingChannels(previous => ({
      ...previous,
      [provider]: [...previous[provider], channel],
    }));
    bindingForm.setFieldValue('channel_id', channel);
    setQuickAddBindingInput('');
    message.success(`Added ${channel} and selected`);
  };

  const handleOpenBindingModal = (wf: PlatformWorkflow) => {
    setBindingWorkflow(wf);
    bindingForm.resetFields();

    if (wf.channel_binding) {
      bindingForm.setFieldsValue({
        provider: wf.channel_binding.provider,
        channel_id: wf.channel_binding.channel_id,
        trigger_enabled: wf.channel_binding.trigger_enabled,
        notify_mode: wf.channel_binding.notify_mode,
        message_template: wf.channel_binding.message_template,
      });
    } else {
      bindingForm.setFieldsValue({
        provider: 'slack',
        channel_id: '#pr-review',
        trigger_enabled: true,
        notify_mode: 'ON_COMPLETE',
      });
    }

    setBindingModalVisible(true);
  };

  const handleSaveBinding = async () => {
    if (resourceErrors.connectors || resourceErrors.workflows) {
      message.error('Channel binding data is unavailable. Refresh and retry.');
      return;
    }
    if (!bindingWorkflow) return;
    try {
      const values = await bindingForm.validateFields();
      setBindingSubmitting(true);

      await bindWorkflowChannel(bindingWorkflow.id, {
        provider: values.provider,
        connector_id: values.provider,
        channel_id: values.channel_id,
        channel_name: values.channel_id,
        trigger_enabled: values.trigger_enabled,
        notify_mode: values.notify_mode,
        message_template: values.message_template,
      });

      message.success(`Bound workflow "${bindingWorkflow.name}" to channel ${values.channel_id}`);
      setBindingModalVisible(false);
      loadData();
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error('Failed to save channel binding');
    } finally {
      setBindingSubmitting(false);
    }
  };

  const handleUnbindChannel = async (workflowId: string) => {
    try {
      await unbindWorkflowChannel(workflowId);
      message.success('Channel binding removed');
      loadData();
    } catch (err) {
      message.error('Failed to unbind channel');
    }
  };

  const handleRunWorkflow = async (record: PlatformWorkflow) => {
    setRunningWfMap((prev) => ({ ...prev, [record.id]: true }));
    try {
      const res = await executeWorkflow(record.id);
      message.success(`Workflow "${record.name}" finished execution! Status: ${res.data?.status || 'COMPLETED'}`);
      if (record.channel_binding) {
        message.info(`Sent completion alert to ${record.channel_binding.provider}:${record.channel_binding.channel_id}`);
      }
      loadData();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || 'Failed to execute workflow');
    } finally {
      setRunningWfMap((prev) => ({ ...prev, [record.id]: false }));
    }
  };

  const handleDeleteWorkflow = async (workflowId: string) => {
    try {
      await deleteWorkflow(workflowId);
      message.success('Workflow deleted successfully');
      loadData();
    } catch (err) {
      message.error('Failed to delete workflow');
    }
  };

  // Categories list
  return { handleQuickAddBindingChannel, handleOpenBindingModal, handleSaveBinding, handleUnbindChannel, handleRunWorkflow, handleDeleteWorkflow };
};

import { usePermissions } from '../hooks/usePermissions';
import { TaskQueuePanel } from './TaskQueuePanel';
import React from 'react';
import { Table, Form, Input, Button, Modal, Tag, Slider, message, Select, InputNumber, Tree, Card } from 'antd';
import { PlusOutlined, SyncOutlined, CopyOutlined, CodeOutlined } from '@ant-design/icons';
import { Task } from '../types/task';
import { Agent } from '../types/agent';

import { useTasksPage } from './useTasksPage';

export const TasksPage: React.FC = () => {
  const { canOperate } = usePermissions();
  const model = useTasksPage();
  const {
    tasks,
    refresh,
    agents,
    loading,
    visible,
    setVisible,
    form,
    editingKey,
    taskDetail,
    detailVisible,
    setDetailVisible,
    delegatingTask,
    delegateModalVisible,
    setDelegateModalVisible,
    delegateForm,
    delegating,
    treeModalVisible,
    setTreeModalVisible,
    treeData,
    loadingTree,
    handleCreate,
    handleOk,
    handleDelegateSubmit,
    convertTreeToNodes,
    columns,
    getSubordinateWorkers,
  } = model;
  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h2 style={{ margin: 0, color: '#f3f4f6', fontSize: '22px', fontWeight: 700 }}>
            📋 Task Orchestration & Execution
          </h2>
          <span style={{ color: '#9ca3af', fontSize: '13px' }}>
            Live asynchronous executions, structured subtask delegation, and multi-agent task coordination.
          </span>
        </div>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          disabled={!canOperate} onClick={handleCreate}
          style={{ background: '#10b981', borderColor: '#10b981', borderRadius: '8px' }}
        >
          Dispatch New Task
        </Button>
      </div>

      <TaskQueuePanel onTaskRetried={refresh} />

      <Table
        dataSource={tasks}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 10 }}
        scroll={{ x: 1000 }}
        style={{ background: '#161b22', borderRadius: '12px' }}
      />

      {/* Dispatch New Task Modal */}
      <Modal
        title={editingKey ? 'Edit Task' : 'Dispatch Autonomous Task'}
        open={visible}
        onOk={handleOk}
        onCancel={() => setVisible(false)}
        okText="Dispatch"
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="agent_id"
            label="Assigned Agent"
            rules={[{ required: true, message: 'Please select an agent' }]}
          >
            <Select placeholder="Select executor">
              {agents.map((a) => (
                <Select.Option key={a.id} value={a.id}>
                  🤖 {a.name} ({a.role_type || 'WORKER'} - {a.department || 'General'})
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="prompt"
            label="Task Prompt / Objective"
            rules={[{ required: true, message: 'Task prompt is required' }]}
          >
            <Input.TextArea rows={4} placeholder="Analyze codebase and create report..." />
          </Form.Item>
          <Form.Item name="priority" label="Execution Priority (1: Background, 5: Standard, 10: Urgent Incident)" initialValue={5}>
            <Slider min={1} max={10} marks={{
              1: { style: { color: '#64748b' }, label: '1 (Low)' },
              5: { style: { color: '#38bdf8' }, label: '5 (Std)' },
              8: { style: { color: '#f59e0b' }, label: '8 (High)' },
              10: { style: { color: '#ef4444' }, label: '10 (Urgent)' },
            }} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Delegate Subtask Modal */}
      <Modal
        title={`Delegate Subtask from ${delegatingTask?.agent_id}`}
        open={delegateModalVisible}
        onOk={handleDelegateSubmit}
        onCancel={() => setDelegateModalVisible(false)}
        confirmLoading={delegating}
        okText="Delegate Subtask"
      >
        <Form form={delegateForm} layout="vertical">
          <Form.Item
            name="target_agent_id"
            label="Target Subordinate Agent"
            rules={[{ required: true, message: 'Please select a subordinate agent' }]}
          >
            <Select placeholder="Select subordinate worker">
              {getSubordinateWorkers(delegatingTask?.agent_id).map((a) => (
                <Select.Option key={a.id} value={a.id}>
                  💻 {a.name} ({a.role_type} - {a.department})
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item
            name="subtask_prompt"
            label="Subtask Instructions"
            rules={[{ required: true, message: 'Subtask instructions are required' }]}
          >
            <Input.TextArea rows={3} placeholder="Implement database migration or run test suite..." />
          </Form.Item>

          <Form.Item name="timeout_seconds" label="Timeout (Seconds)">
            <InputNumber min={10} max={3600} style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Task Execution Tree Modal */}
      <Modal
        title="Execution Lineage Tree"
        open={treeModalVisible}
        onOk={() => setTreeModalVisible(false)}
        onCancel={() => setTreeModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setTreeModalVisible(false)}>
            Close
          </Button>,
        ]}
        width={600}
      >
        {loadingTree ? (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <SyncOutlined spin style={{ fontSize: '24px', color: '#38bdf8' }} />
          </div>
        ) : treeData ? (
          <Card style={{ background: '#0f172a', border: '1px solid #334155', borderRadius: '10px' }}>
            <Tree
              showLine
              defaultExpandAll
              treeData={[convertTreeToNodes(treeData)]}
              style={{ background: 'transparent', color: '#f8fafc' }}
            />
          </Card>
        ) : (
          <div>No subtasks found for this execution.</div>
        )}
      </Modal>

      {/* Task Details / Logs Modal */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <CodeOutlined style={{ color: '#58a6ff', fontSize: '18px' }} />
            <span style={{ color: '#f3f4f6', fontWeight: 600 }}>
              Task Console: #{taskDetail?.id?.slice(0, 8)}
            </span>
            {taskDetail?.status && (
              <Tag
                color={
                  taskDetail.status === 'completed'
                    ? 'green'
                    : taskDetail.status === 'running'
                    ? 'blue'
                    : taskDetail.status === 'failed'
                    ? 'red'
                    : 'default'
                }
              >
                {taskDetail.status.toUpperCase()}
              </Tag>
            )}
          </div>
        }
        open={detailVisible}
        onOk={() => setDetailVisible(false)}
        onCancel={() => setDetailVisible(false)}
        width={720}
        footer={[
          <Button
            key="copy"
            icon={<CopyOutlined />}
            onClick={() => {
              const fullLog = [
                `Task ID: ${taskDetail?.id}`,
                `Agent: ${taskDetail?.agent_id}`,
                `Status: ${taskDetail?.status}`,
                `Prompt: ${taskDetail?.prompt}`,
                taskDetail?.result ? `Result:\n${typeof taskDetail.result === 'string' ? taskDetail.result : JSON.stringify(taskDetail.result, null, 2)}` : '',
                taskDetail?.error ? `Error:\n${typeof taskDetail.error === 'string' ? taskDetail.error : JSON.stringify(taskDetail.error, null, 2)}` : '',
              ]
                .filter(Boolean)
                .join('\n\n');
              navigator.clipboard.writeText(fullLog);
              message.success('Task execution logs copied to clipboard');
            }}
          >
            Copy Logs
          </Button>,
          <Button key="ok" type="primary" onClick={() => setDetailVisible(false)}>
            Close
          </Button>,
        ]}
      >
        {taskDetail && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {/* Meta summary strip */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                gap: '8px',
                background: '#161b22',
                padding: '10px 14px',
                borderRadius: '8px',
                border: '1px solid #30363d',
                fontSize: '12px',
              }}
            >
              <div>
                <span style={{ color: '#8b949e' }}>Agent:</span>{' '}
                <strong style={{ color: '#58a6ff' }}>{taskDetail.agent_id}</strong>
              </div>
              {taskDetail.project_id && (
                <div>
                  <span style={{ color: '#8b949e' }}>Project:</span>{' '}
                  <span style={{ color: '#f3f4f6' }}>{taskDetail.project_id}</span>
                </div>
              )}
              {taskDetail.created_at && (
                <div>
                  <span style={{ color: '#8b949e' }}>Created:</span>{' '}
                  <span style={{ color: '#c9d1d9' }}>
                    {new Date(taskDetail.created_at).toLocaleTimeString()}
                  </span>
                </div>
              )}
              {taskDetail.ended_at && (
                <div>
                  <span style={{ color: '#8b949e' }}>Ended:</span>{' '}
                  <span style={{ color: '#c9d1d9' }}>
                    {new Date(taskDetail.ended_at).toLocaleTimeString()}
                  </span>
                </div>
              )}
            </div>

            {/* Prompt */}
            <div>
              <strong style={{ color: '#d1d5db', fontSize: '13px' }}>Instruction / Prompt:</strong>
              <div
                style={{
                  background: '#0d1117',
                  border: '1px solid #30363d',
                  padding: '10px 12px',
                  borderRadius: '6px',
                  marginTop: '6px',
                  fontSize: '12px',
                  color: '#e6edf3',
                  whiteSpace: 'pre-wrap',
                }}
              >
                {taskDetail.prompt || 'N/A'}
              </div>
            </div>

            {/* Execution Result */}
            {taskDetail.result && (
              <div>
                <strong style={{ color: '#52c41a', fontSize: '13px' }}>Execution Output & Result:</strong>
                <pre
                  style={{
                    background: '#0d1117',
                    border: '1px solid #238636',
                    padding: '12px',
                    borderRadius: '6px',
                    marginTop: '6px',
                    maxHeight: '260px',
                    overflowY: 'auto',
                    fontSize: '12px',
                    color: '#7ee787',
                    fontFamily: 'monospace',
                    whiteSpace: 'pre-wrap',
                    lineHeight: '1.4',
                  }}
                >
                  {typeof taskDetail.result === 'string'
                    ? taskDetail.result
                    : JSON.stringify(taskDetail.result, null, 2)}
                </pre>
              </div>
            )}

            {/* Error Output */}
            {taskDetail.error && (
              <div>
                <strong style={{ color: '#f85149', fontSize: '13px' }}>Error Details:</strong>
                <pre
                  style={{
                    background: '#1f0d0d',
                    border: '1px solid #da3633',
                    padding: '12px',
                    borderRadius: '6px',
                    marginTop: '6px',
                    maxHeight: '180px',
                    overflowY: 'auto',
                    fontSize: '12px',
                    color: '#ff7b72',
                    fontFamily: 'monospace',
                    whiteSpace: 'pre-wrap',
                  }}
                >
                  {typeof taskDetail.error === 'string'
                    ? taskDetail.error
                    : JSON.stringify(taskDetail.error, null, 2)}
                </pre>
              </div>
            )}

            {/* Execution Events Stream (if present) */}
            {taskDetail.events && taskDetail.events.length > 0 && (
              <div>
                <strong style={{ color: '#58a6ff', fontSize: '13px' }}>
                  Execution Event Stream ({taskDetail.events.length} events):
                </strong>
                <div
                  style={{
                    background: '#0d1117',
                    border: '1px solid #30363d',
                    padding: '10px',
                    borderRadius: '6px',
                    marginTop: '6px',
                    maxHeight: '180px',
                    overflowY: 'auto',
                    fontSize: '11px',
                    fontFamily: 'monospace',
                  }}
                >
                  {taskDetail.events.map((ev: any, idx: number) => (
                    <div key={idx} style={{ color: '#8b949e', marginBottom: '4px', borderBottom: '1px dashed #21262d', paddingBottom: '3px' }}>
                      <span style={{ color: '#79c0ff' }}>[{ev.type || 'event'}]</span>{' '}
                      <span style={{ color: '#c9d1d9' }}>
                        {ev.message ? (typeof ev.message === 'string' ? ev.message : JSON.stringify(ev.message)) : (ev.content || JSON.stringify(ev))}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};
export default TasksPage;

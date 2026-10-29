import { Button, Input, Modal, Form, message } from 'antd';
import { BranchesOutlined } from '@ant-design/icons';
import type { useMcpPage } from './useMcpPage';
import { McpRepositorySelection } from './McpRepositorySelection';
import { McpSlackSelection } from './McpSlackSelection';
import { McpTelegramSelection } from './McpTelegramSelection';

export const McpConnectorModal = (model: Pick<
  ReturnType<typeof useMcpPage>,
  | 'loading'
  | 'modalVisible'
  | 'setModalVisible'
  | 'selectedCatalogItem'
  | 'editingConnector'
  | 'submitting'
  | 'form'
  | 'fetchingResources'
  | 'handleFetchTokenRepositories'
  | 'handleSaveConnector'
  | 'getProviderIcon'
> & Parameters<typeof McpRepositorySelection>[0] & Parameters<typeof McpSlackSelection>[0] & Parameters<typeof McpTelegramSelection>[0]) => {
  const {
    loading,
    modalVisible,
    setModalVisible,
    selectedCatalogItem,
    editingConnector,
    submitting,
    form,
    fetchingResources,
    handleFetchTokenRepositories,
    handleSaveConnector,
    getProviderIcon,
  } = model;
  return (<>
      {/* Connect / Configure Modal */}
      <Modal
        title={
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            {selectedCatalogItem && getProviderIcon(selectedCatalogItem.provider, 22)}
            <span>
              {editingConnector ? `Configure ${selectedCatalogItem?.name}` : `Connect ${selectedCatalogItem?.name}`}
            </span>
          </div>
        }
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={handleSaveConnector}
        confirmLoading={submitting}
        okText={editingConnector ? 'Save Changes' : 'Install & Connect'}
        width={620}
      >
        <p style={{ color: '#8b949e', fontSize: '13px', marginBottom: '16px' }}>
            {selectedCatalogItem?.description}
          </p>

          <Form form={form} layout="vertical">
            <Form.Item
              name="name"
              label={<span style={{ color: '#f0f6fc' }}>Connector Name</span>}
              rules={[{ required: true, message: 'Please enter a connector name' }]}
            >
              <Input placeholder="e.g. My GitHub Account" style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }} />
            </Form.Item>

            {selectedCatalogItem &&
              Object.entries(selectedCatalogItem.config_schema)
                .filter(([key]) => key !== 'chat_id' && key !== 'default_channel')
                .map(([key, field]) => {
                const isTokenField =
                  (key === 'token' || key === 'personal_access_token' || key === 'api_key') &&
                  (selectedCatalogItem.provider === 'github' || selectedCatalogItem.provider === 'git' || selectedCatalogItem.provider === 'gitlab');

                return (
                  <Form.Item
                    key={key}
                    name={key}
                    label={<span style={{ color: '#f0f6fc' }}>{field.label}</span>}
                    rules={[{ required: field.required, message: `${field.label} is required` }]}
                    extra={
                      isTokenField ? (
                        <div style={{ marginTop: '6px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ color: '#8b949e', fontSize: '11px' }}>
                            Query remote repositories using this Personal Access Token
                          </span>
                          <Button
                            size="small"
                            type="primary"
                            icon={<BranchesOutlined />}
                            loading={fetchingResources}
                            onClick={handleFetchTokenRepositories}
                            style={{ background: '#10b981', borderColor: '#10b981', color: '#0d1117', fontWeight: 600, fontSize: '11px', height: '26px' }}
                          >
                            Fetch Token Repositories
                          </Button>
                        </div>
                      ) : undefined
                    }
                  >
                    {field.type === 'password' ? (
                      <Input.Password
                        placeholder={field.placeholder}
                        style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }}
                      />
                    ) : (
                      <Input
                        placeholder={field.placeholder}
                        style={{ background: '#0d1117', borderColor: '#30363d', color: '#f0f6fc' }}
                      />
                    )}
                  </Form.Item>
                );
              })}

            <McpRepositorySelection {...model} />
            <McpSlackSelection {...model} />
            <McpTelegramSelection {...model} />
          </Form>
      </Modal>

  </>);
};

import React, { useState, useEffect } from 'react';
import { getMCPConnectors, getMCPTools, getMCPToolCalls, executeMCPTool } from '../../services/api';
import { MCPConnector, MCPTool, MCPToolCall } from '../../types/mcp';

interface ConnectorModalProps {
  connector: MCPConnector;
  tools: MCPTool[];
  calls: MCPToolCall[];
  onClose: () => void;
  onRefresh: () => void;
}

const CONNECTOR_ICONS: Record<string, string> = {
  github: '🐙',
  google_workspace: '📑',
  trello: '📋',
  telegram: '✈️',
  slack: '💬',
  jira: '🎫',
};

export const ConnectorDetailModal: React.FC<ConnectorModalProps> = ({
  connector,
  tools,
  calls,
  onClose,
  onRefresh,
}) => {
  const [activeTab, setActiveTab] = useState<'tools' | 'history' | 'test'>('tools');
  const [selectedTool, setSelectedTool] = useState<string>(tools[0]?.name || '');
  const [testAgentId, setTestAgentId] = useState<string>('agent-lead');
  const [testArgs, setTestArgs] = useState<string>('{}');
  const [testResult, setTestResult] = useState<any>(null);
  const [testing, setTesting] = useState<boolean>(false);
  const [testError, setTestError] = useState<string | null>(null);

  const handleTestCall = async () => {
    setTesting(true);
    setTestError(null);
    setTestResult(null);
    try {
      let parsedArgs = {};
      try {
        parsedArgs = JSON.parse(testArgs);
      } catch (err: any) {
        throw new Error('Invalid JSON arguments: ' + err.message);
      }

      const res = await executeMCPTool({
        agent_id: testAgentId,
        connector_id: connector.id,
        tool_name: selectedTool,
        input_args: parsedArgs,
      });
      setTestResult(res.data);
      onRefresh();
    } catch (err: any) {
      setTestError(err.response?.data?.detail || err.message);
    } finally {
      setTesting(false);
    }
  };

  const connectorCalls = calls.filter((c) => c.connector_id === connector.id);

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        zIndex: 1000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backdropFilter: 'blur(4px)',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '760px',
          maxHeight: '85vh',
          backgroundColor: '#161b22',
          border: '1px solid #30363d',
          borderRadius: '10px',
          boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          color: '#f0f6fc',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid #21262d',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: '#0d1117',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '24px' }}>
              {CONNECTOR_ICONS[connector.connector_type] || '🔌'}
            </span>
            <div>
              <div style={{ fontSize: '16px', fontWeight: 700 }}>{connector.name}</div>
              <div style={{ fontSize: '12px', color: '#8b949e' }}>
                Type: {connector.connector_type} • Status:{' '}
                <span
                  style={{
                    color: connector.status === 'CONNECTED' ? '#34d399' : '#f87171',
                    fontWeight: 600,
                  }}
                >
                  {connector.status}
                </span>
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#8b949e',
              fontSize: '18px',
              cursor: 'pointer',
              padding: '4px 8px',
            }}
          >
            ✕
          </button>
        </div>

        {/* Tabs */}
        <div
          style={{
            display: 'flex',
            borderBottom: '1px solid #21262d',
            background: '#161b22',
            padding: '0 16px',
            gap: '8px',
          }}
        >
          {[
            { id: 'tools', label: `Available Tools (${tools.length})` },
            { id: 'history', label: `Execution History (${connectorCalls.length})` },
            { id: 'test', label: 'Test Tool Call' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              style={{
                padding: '10px 14px',
                border: 'none',
                background: 'none',
                fontSize: '12px',
                fontWeight: 600,
                color: activeTab === tab.id ? '#58a6ff' : '#8b949e',
                borderBottom: activeTab === tab.id ? '2px solid #58a6ff' : '2px solid transparent',
                cursor: 'pointer',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div style={{ padding: '20px', overflowY: 'auto', flex: 1 }}>
          {activeTab === 'tools' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {tools.length === 0 ? (
                <div style={{ color: '#8b949e', fontSize: '13px' }}>No tools registered.</div>
              ) : (
                tools.map((t) => (
                  <div
                    key={t.id}
                    style={{
                      background: '#0d1117',
                      border: '1px solid #21262d',
                      borderRadius: '6px',
                      padding: '12px 16px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#79c0ff' }}>
                        {t.name}
                      </span>
                      <span style={{ fontSize: '10px', color: '#8b949e' }}>ID: {t.id}</span>
                    </div>
                    {t.description && (
                      <div style={{ fontSize: '12px', color: '#c9d1d9', marginTop: '6px' }}>
                        {t.description}
                      </div>
                    )}
                    {t.input_schema && (
                      <pre
                        style={{
                          background: '#161b22',
                          padding: '8px',
                          borderRadius: '4px',
                          fontSize: '11px',
                          marginTop: '8px',
                          overflowX: 'auto',
                          border: '1px solid #30363d',
                          color: '#e6edf3',
                        }}
                      >
                        {JSON.stringify(t.input_schema, null, 2)}
                      </pre>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === 'history' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {connectorCalls.length === 0 ? (
                <div style={{ color: '#8b949e', fontSize: '13px' }}>No tool calls executed yet.</div>
              ) : (
                connectorCalls.map((call) => (
                  <div
                    key={call.id}
                    style={{
                      background: '#0d1117',
                      border: '1px solid #21262d',
                      borderRadius: '6px',
                      padding: '12px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                      <span style={{ fontWeight: 700, fontFamily: 'monospace', color: '#58a6ff' }}>
                        {call.tool_name}
                      </span>
                      <span
                        style={{
                          fontSize: '10px',
                          padding: '2px 6px',
                          borderRadius: '10px',
                          fontWeight: 700,
                          backgroundColor:
                            call.status === 'COMPLETED'
                              ? 'rgba(52, 211, 153, 0.15)'
                              : call.status === 'FAILED'
                              ? 'rgba(248, 113, 113, 0.15)'
                              : 'rgba(96, 165, 250, 0.15)',
                          color:
                            call.status === 'COMPLETED'
                              ? '#34d399'
                              : call.status === 'FAILED'
                              ? '#f87171'
                              : '#60a5fa',
                        }}
                      >
                        {call.status}
                      </span>
                    </div>
                    <div style={{ fontSize: '11px', color: '#8b949e' }}>
                      Agent: <strong style={{ color: '#c9d1d9' }}>{call.agent_id}</strong> • Started:{' '}
                      {new Date(call.started_at).toLocaleTimeString()}
                    </div>
                    {call.output_result && (
                      <div
                        style={{
                          marginTop: '6px',
                          fontSize: '11px',
                          color: '#7ee787',
                          fontFamily: 'monospace',
                          background: '#161b22',
                          padding: '6px',
                          borderRadius: '4px',
                          maxHeight: '100px',
                          overflowY: 'auto',
                        }}
                      >
                        {call.output_result}
                      </div>
                    )}
                    {call.error && (
                      <div
                        style={{
                          marginTop: '6px',
                          fontSize: '11px',
                          color: '#f87171',
                          fontFamily: 'monospace',
                          background: '#161b22',
                          padding: '6px',
                          borderRadius: '4px',
                        }}
                      >
                        {call.error}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === 'test' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#8b949e', marginBottom: '4px' }}>
                  Target Tool
                </label>
                <select
                  value={selectedTool}
                  onChange={(e) => setSelectedTool(e.target.value)}
                  style={{
                    width: '100%',
                    background: '#0d1117',
                    border: '1px solid #30363d',
                    borderRadius: '6px',
                    padding: '8px 12px',
                    color: '#f0f6fc',
                    fontSize: '13px',
                  }}
                >
                  {tools.map((t) => (
                    <option key={t.id} value={t.name}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#8b949e', marginBottom: '4px' }}>
                  Calling Agent ID
                </label>
                <input
                  type="text"
                  value={testAgentId}
                  onChange={(e) => setTestAgentId(e.target.value)}
                  style={{
                    width: '100%',
                    background: '#0d1117',
                    border: '1px solid #30363d',
                    borderRadius: '6px',
                    padding: '8px 12px',
                    color: '#f0f6fc',
                    fontSize: '13px',
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#8b949e', marginBottom: '4px' }}>
                  JSON Arguments
                </label>
                <textarea
                  rows={4}
                  value={testArgs}
                  onChange={(e) => setTestArgs(e.target.value)}
                  style={{
                    width: '100%',
                    background: '#0d1117',
                    border: '1px solid #30363d',
                    borderRadius: '6px',
                    padding: '8px 12px',
                    color: '#f0f6fc',
                    fontFamily: 'monospace',
                    fontSize: '12px',
                  }}
                />
              </div>

              <button
                disabled={testing}
                onClick={handleTestCall}
                style={{
                  alignSelf: 'flex-start',
                  padding: '8px 18px',
                  borderRadius: '6px',
                  background: '#238636',
                  color: '#fff',
                  border: 'none',
                  fontWeight: 600,
                  fontSize: '13px',
                  cursor: testing ? 'not-allowed' : 'pointer',
                  opacity: testing ? 0.7 : 1,
                }}
              >
                {testing ? 'Executing...' : 'Run Tool Test'}
              </button>

              {testError && (
                <div
                  style={{
                    background: 'rgba(248, 113, 113, 0.15)',
                    border: '1px solid rgba(248, 113, 113, 0.4)',
                    color: '#f87171',
                    padding: '10px 14px',
                    borderRadius: '6px',
                    fontSize: '12px',
                  }}
                >
                  <strong>Execution Error:</strong> {testError}
                </div>
              )}

              {testResult && (
                <div
                  style={{
                    background: '#0d1117',
                    border: '1px solid #238636',
                    padding: '12px',
                    borderRadius: '6px',
                  }}
                >
                  <div style={{ fontSize: '12px', fontWeight: 700, color: '#34d399', marginBottom: '6px' }}>
                    Tool Execution Response:
                  </div>
                  <pre
                    style={{
                      margin: 0,
                      fontSize: '11px',
                      color: '#e6edf3',
                      fontFamily: 'monospace',
                      overflowX: 'auto',
                    }}
                  >
                    {JSON.stringify(testResult, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export const MCPTopBar: React.FC = () => {
  const [connectors, setConnectors] = useState<MCPConnector[]>([]);
  const [tools, setTools] = useState<MCPTool[]>([]);
  const [recentCalls, setRecentCalls] = useState<MCPToolCall[]>([]);
  const [selectedConnector, setSelectedConnector] = useState<MCPConnector | null>(null);

  const fetchData = async () => {
    try {
      const [cRes, tRes, callRes] = await Promise.all([
        getMCPConnectors(),
        getMCPTools(),
        getMCPToolCalls(20),
      ]);
      setConnectors(cRes.data || []);
      setTools(tRes.data || []);
      setRecentCalls(callRes.data || []);
    } catch (e) {
      console.error('Failed to fetch MCP status:', e);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 8000);
    return () => clearInterval(interval);
  }, []);

  const activeCallsCount = recentCalls.filter((c) => c.status === 'RUNNING').length;

  return (
    <div
      style={{
        height: '36px',
        backgroundColor: '#0a0d12',
        borderBottom: '1px solid #1f242c',
        display: 'flex',
        alignItems: 'center',
        padding: '0 20px',
        gap: '14px',
        fontSize: '11px',
        color: '#8b949e',
        userSelect: 'none',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, color: '#58a6ff' }}>
        <span>⚡ MCP CONNECTORS:</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, overflowX: 'auto' }}>
        {connectors.map((c) => {
          const cTools = tools.filter((t) => t.connector_id === c.id);
          const isCalling = recentCalls.some((call) => call.connector_id === c.id && call.status === 'RUNNING');
          const isConnected = c.status === 'CONNECTED';

          return (
            <div
              key={c.id}
              onClick={() => setSelectedConnector(c)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '3px 8px',
                borderRadius: '5px',
                backgroundColor: isCalling ? 'rgba(88, 166, 255, 0.15)' : '#161b22',
                border: isCalling ? '1px solid #58a6ff' : '1px solid #30363d',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
              title={`Click to view ${c.name} tools and history`}
            >
              <span style={{ fontSize: '13px' }}>{CONNECTOR_ICONS[c.connector_type] || '🔌'}</span>
              <span style={{ fontWeight: 600, color: '#c9d1d9' }}>{c.name}</span>
              <span
                style={{
                  fontSize: '9px',
                  fontWeight: 700,
                  backgroundColor: '#21262d',
                  padding: '1px 4px',
                  borderRadius: '3px',
                  color: '#8b949e',
                }}
              >
                {cTools.length} tools
              </span>
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: '50%',
                  backgroundColor: isConnected ? '#34d399' : '#f87171',
                  boxShadow: isCalling ? '0 0 6px #34d399' : 'none',
                }}
              />
            </div>
          );
        })}
      </div>

      {activeCallsCount > 0 && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            color: '#e3b341',
            background: 'rgba(227, 179, 65, 0.15)',
            padding: '2px 8px',
            borderRadius: '10px',
            fontSize: '10px',
            fontWeight: 700,
          }}
        >
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#e3b341' }} />
          <span>{activeCallsCount} Active Tool Call{activeCallsCount > 1 ? 's' : ''}</span>
        </div>
      )}

      {selectedConnector && (
        <ConnectorDetailModal
          connector={selectedConnector}
          tools={tools.filter((t) => t.connector_id === selectedConnector.id)}
          calls={recentCalls}
          onClose={() => setSelectedConnector(null)}
          onRefresh={fetchData}
        />
      )}
    </div>
  );
};

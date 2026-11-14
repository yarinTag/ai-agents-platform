import { useEffect, useState } from 'react';
import { Alert, Button, Card, Spin } from 'antd';
import { useAuth } from '../context/AuthContext';
import { useGovernanceText } from '../i18n/governance';
import CapabilityAccessTable from '../components/org/CapabilityAccessTable';
import { getGovernanceCatalog } from '../services/governanceApi';
import type { CapabilityCatalog } from '../types/governance';

export function McpDepartmentTools() {
  const { activeDepartmentId } = useAuth();
  const text = useGovernanceText();

  return activeDepartmentId
    ? <DepartmentCatalog key={activeDepartmentId} departmentId={activeDepartmentId} />
    : <Alert type="info" showIcon message={text.selectDepartment} />;
}

function DepartmentCatalog({ departmentId }: { departmentId: string }) {
  const text = useGovernanceText();
  const [catalog, setCatalog] = useState<CapabilityCatalog>();
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const request = new AbortController();
    getGovernanceCatalog(departmentId, request.signal)
      .then(({ data }) => {
        if (!request.signal.aborted) setCatalog(data);
      })
      .catch(() => {
        if (!request.signal.aborted) setFailed(true);
      });
    return () => request.abort();
  }, [departmentId, attempt]);

  const retry = () => {
    setFailed(false);
    setAttempt(value => value + 1);
  };

  return <Card title="MCP Hub">
    {failed ? <Alert type="error" showIcon message={text.loadError}
      action={<Button onClick={retry}>{text.refresh}</Button>} />
      : catalog ? <CapabilityAccessTable catalog={catalog} capabilities={[]} text={text} />
        : <Spin />}
  </Card>;
}

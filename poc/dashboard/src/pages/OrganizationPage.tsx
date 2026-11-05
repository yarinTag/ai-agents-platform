import React, { useState, useEffect, useCallback } from 'react';
import { Card, Row, Col, Statistic, Tabs, Tag, Button, Typography, message } from 'antd';
import {
  BankOutlined, TeamOutlined, UserOutlined, SafetyCertificateOutlined,
  DollarCircleOutlined, ApartmentOutlined, SyncOutlined, SettingOutlined,
} from '@ant-design/icons';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from '../i18n';
import { useRuntimeSetupText } from '../i18n/runtimeSetup';
import { useOrgWorkflowsCanvasText } from '../i18n/orgWorkflowsCanvas';
import { RuntimeSettingsPanel } from '../components/common/RuntimeSettingsPanel';
import {
  getDepartments, createDepartment, getDepartmentMembers,
  bulkInviteDepartmentMembers, removeDepartmentMember, getOrganizationUsers, getWorkflows,
} from '../services/api';
import { Department, DepartmentMember, OrganizationUser, InvitationRecord } from '../types/auth';
import { PlatformWorkflow } from '../types/mcp';
import { DepartmentsBudgetTab, TeamInvitationsTab, OrgUsersTab, OrgWorkflowsCanvasTab } from '../components/org';

const { Text } = Typography;

export const OrganizationPage: React.FC = () => {
  const { organization, user, refreshUserProfile } = useAuth();
  const { t } = useTranslation();
  const runtimeText = useRuntimeSetupText();
  const canvasText = useOrgWorkflowsCanvasText();

  const [activeTab, setActiveTab] = useState<'departments' | 'workflows' | 'team' | 'users' | 'runtime'>('departments');
  const [departmentsList, setDepartmentsList] = useState<Department[]>([]);
  const [loadingDepts, setLoadingDepts] = useState<boolean>(false);
  const [creatingDept, setCreatingDept] = useState<boolean>(false);
  const [workflowsList, setWorkflowsList] = useState<PlatformWorkflow[]>([]);
  const [loadingWorkflows, setLoadingWorkflows] = useState<boolean>(false);

  // Team tab state
  const [selectedDeptId, setSelectedDeptId] = useState<string | null>(null);
  const [deptMembers, setDeptMembers] = useState<DepartmentMember[]>([]);
  const [loadingMembers, setLoadingMembers] = useState<boolean>(false);
  const [inviting, setInviting] = useState<boolean>(false);
  const [recentInvitations, setRecentInvitations] = useState<InvitationRecord[]>([]);

  // Org users state
  const [orgUsers, setOrgUsers] = useState<OrganizationUser[]>([]);
  const [loadingUsers, setLoadingUsers] = useState<boolean>(false);

  // Load departments
  const loadDepartments = useCallback(async () => {
    if (!organization?.id) return;
    setLoadingDepts(true);
    try {
      const res = await getDepartments(organization.id);
      setDepartmentsList(res.data);
      setSelectedDeptId((prev) => prev || (res.data.length > 0 ? res.data[0].id : null));
    } catch (err: any) {
      message.error(t('org.loadDeptsError'));
    } finally {
      setLoadingDepts(false);
    }
  }, [organization?.id, t]);

  // Load department members
  const loadDepartmentMembers = useCallback(async (deptId: string) => {
    setLoadingMembers(true);
    try {
      const res = await getDepartmentMembers(deptId);
      setDeptMembers(res.data);
    } catch (err: any) {
      message.error(t('org.loadMembersError'));
    } finally {
      setLoadingMembers(false);
    }
  }, [t]);

  // Load organization users
  const loadOrgUsers = useCallback(async () => {
    if (!organization?.id) return;
    setLoadingUsers(true);
    try {
      const res = await getOrganizationUsers(organization.id);
      setOrgUsers(res.data);
    } catch (err: any) {
      message.error(t('org.loadUsersError'));
    } finally {
      setLoadingUsers(false);
    }
  }, [organization?.id, t]);

  // Load organization workflows
  const loadWorkflows = useCallback(async () => {
    setLoadingWorkflows(true);
    try {
      const res = await getWorkflows();
      const data = res.data as any;
      setWorkflowsList(Array.isArray(data) ? data : (data?.workflows || []));
    } catch {
      setWorkflowsList([]);
    } finally {
      setLoadingWorkflows(false);
    }
  }, []);

  useEffect(() => {
    if (organization?.id) {
      loadDepartments();
      loadOrgUsers();
      loadWorkflows();
    }
  }, [organization?.id, loadDepartments, loadOrgUsers, loadWorkflows]);

  useEffect(() => {
    if (selectedDeptId) {
      loadDepartmentMembers(selectedDeptId);
    }
  }, [selectedDeptId, loadDepartmentMembers]);

  // Manual refresh helper
  const handleRefresh = async () => {
    await Promise.all([loadDepartments(), loadOrgUsers(), loadWorkflows()]);
    if (selectedDeptId) {
      await loadDepartmentMembers(selectedDeptId);
    }
  };

  // Handle department creation
  const handleCreateDepartment = async (values: any) => {
    if (!organization?.id) return;
    setCreatingDept(true);
    try {
      await createDepartment({
        name: values.name.trim(),
        description: values.description ? values.description.trim() : undefined,
        monthly_budget_usd: values.monthly_budget_usd || 100,
        budget_action: values.budget_action || 'HARD_STOP',
        organization_id: organization.id,
      });
      message.success(t('departments.createdSuccess'));
      await loadDepartments();
      await refreshUserProfile();
    } catch (err: any) {
      message.error(err.response?.data?.detail || t('departments.createFailed'));
    } finally {
      setCreatingDept(false);
    }
  };

  // Handle member invitation
  const handleInviteMembers = async (values: any) => {
    if (!selectedDeptId) {
      message.warning(t('departments.selectDeptToManage'));
      return;
    }
    setInviting(true);
    try {
      const rawEmails: string[] = Array.isArray(values.emails)
        ? values.emails
        : values.emails.split(/[\n,;]+/).map((e: string) => e.trim()).filter(Boolean);

      const res = await bulkInviteDepartmentMembers(selectedDeptId, {
        emails: rawEmails,
        role: values.role || 'OPERATOR',
      });

      const invitedCount = res.data.invited_count || (res.data.invitations ? res.data.invitations.length : 0);
      message.success(t('org.inviteIssuedSuccess', { count: invitedCount }));
      setRecentInvitations(res.data.invitations || []);
      await loadDepartmentMembers(selectedDeptId);
    } catch (err: any) {
      message.error(err.response?.data?.detail || t('auth.inviteFailed'));
    } finally {
      setInviting(false);
    }
  };

  // Handle member removal
  const handleRemoveMember = async (userId: string) => {
    if (!selectedDeptId) return;
    try {
      await removeDepartmentMember(selectedDeptId, userId);
      message.success(t('org.removeMemberSuccess'));
      await loadDepartmentMembers(selectedDeptId);
    } catch (err: any) {
      message.error(err.response?.data?.detail || t('org.removeMemberError'));
    }
  };

  const handleManageTeam = (deptId: string) => {
    setSelectedDeptId(deptId);
    setActiveTab('team');
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Hero Banner */}
      <div
        style={{
          background: 'radial-gradient(ellipse at top left, #1e1b4b 0%, #0d1117 70%)',
          borderRadius: '16px',
          border: '1px solid #30363d',
          padding: '24px 32px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px', flexWrap: 'wrap' }}>
            <span
              style={{
                background: 'linear-gradient(135deg, #a855f7 0%, #3b82f6 100%)',
                padding: '8px',
                borderRadius: '10px',
                display: 'inline-flex',
                color: '#fff',
                fontSize: '22px',
              }}
            >
              <BankOutlined />
            </span>
            <h1 style={{ margin: 0, fontSize: '26px', fontWeight: 800, color: '#f0f6fc' }}>
              {organization?.name || 'Enterprise Organization'}
            </h1>
            {organization?.slug && (
              <Tag
                color="blue"
                style={{
                  borderRadius: '12px',
                  fontWeight: 600,
                  fontSize: '12px',
                  padding: '2px 10px',
                  border: '1px solid #1d4ed8',
                }}
              >
                {organization.slug}
              </Tag>
            )}
            {organization?.domain && (
              <Tag
                color="cyan"
                style={{
                  borderRadius: '12px',
                  fontWeight: 600,
                  fontSize: '12px',
                  padding: '2px 10px',
                  border: '1px solid #0e7490',
                }}
              >
                @{organization.domain}
              </Tag>
            )}
          </div>
          <p style={{ margin: 0, color: '#8b949e', fontSize: '14px', maxWidth: '780px' }}>
            Configure enterprise departments, budget hard-stops, team member roles, and secure access permissions across the autonomous agents fleet.
          </p>

          {/* Hierarchy Flow Tags */}
          <div
            style={{
              marginTop: '16px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              flexWrap: 'wrap',
              background: 'rgba(13, 17, 23, 0.7)',
              border: '1px solid #30363d',
              borderRadius: '8px',
              padding: '8px 14px',
              width: 'fit-content',
            }}
          >
            <SafetyCertificateOutlined style={{ color: '#10b981', fontSize: '13px' }} />
            <Text style={{ color: '#8b949e', fontSize: '11px', fontWeight: 600 }}>
              {t('org.hierarchyTitle', 'Hierarchy Structure:')}
            </Text>
            <Tag color="cyan" style={{ fontSize: '11px', margin: 0 }}>
              {organization?.name ? `${organization.name} (${organization.slug})` : t('org.hierarchyOrg', 'Organization')}
            </Tag>
            <span style={{ color: '#484f58' }}>➔</span>
            <Tag color="blue" style={{ fontSize: '11px', margin: 0 }}>
              {t('org.hierarchyDepartments', 'Departments')}
            </Tag>
            <span style={{ color: '#484f58' }}>➔</span>
            <Tag color="purple" style={{ fontSize: '11px', margin: 0 }}>
              {t('org.hierarchyRoles', 'Roles & Permissions')}
            </Tag>
            <span style={{ color: '#484f58' }}>➔</span>
            <Tag color="green" style={{ fontSize: '11px', margin: 0 }}>
              {t('org.hierarchyAgents', 'Autonomous Agents')}
            </Tag>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <Button
            icon={<SyncOutlined spin={loadingDepts || loadingUsers} />}
            onClick={handleRefresh}
            style={{
              background: '#161b22',
              borderColor: '#30363d',
              color: '#f0f6fc',
              fontWeight: 600,
            }}
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Summary KPI Row */}
      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} lg={6}>
          <Card style={{ background: '#161b22', borderColor: '#30363d', borderRadius: '12px' }}>
            <Statistic
              title={<span style={{ color: '#8b949e', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Total Departments</span>}
              value={departmentsList.length}
              prefix={<ApartmentOutlined style={{ color: '#58a6ff' }} />}
              valueStyle={{ color: '#f0f6fc', fontWeight: 700 }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={{ background: '#161b22', borderColor: '#30363d', borderRadius: '12px' }}>
            <Statistic
              title={<span style={{ color: '#8b949e', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Organization Members</span>}
              value={orgUsers.length}
              prefix={<TeamOutlined style={{ color: '#a855f7' }} />}
              valueStyle={{ color: '#f0f6fc', fontWeight: 700 }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={{ background: '#161b22', borderColor: '#30363d', borderRadius: '12px' }}>
            <Statistic
              title={<span style={{ color: '#8b949e', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Total Monthly Budget</span>}
              value={`$${departmentsList.reduce((acc, d) => acc + (d.monthly_budget_usd || 0), 0).toLocaleString()}`}
              prefix={<DollarCircleOutlined style={{ color: '#10b981' }} />}
              valueStyle={{ color: '#10b981', fontWeight: 700 }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card style={{ background: '#161b22', borderColor: '#30363d', borderRadius: '12px' }}>
            <Statistic
              title={<span style={{ color: '#8b949e', fontSize: '12px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Active User Role</span>}
              value={user?.role || 'MEMBER'}
              prefix={<SafetyCertificateOutlined style={{ color: user?.role === 'ORG_ADMIN' ? '#eab308' : '#38bdf8' }} />}
              valueStyle={{ color: user?.role === 'ORG_ADMIN' ? '#eab308' : '#f0f6fc', fontWeight: 700, fontSize: '20px' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Main Card */}
      <div
        style={{
          background: '#161b22',
          border: '1px solid #30363d',
          borderRadius: '12px',
          padding: '16px 24px',
        }}
      >
        <Tabs
          activeKey={activeTab}
          onChange={(k) => setActiveTab(k as any)}
          tabBarStyle={{ borderColor: '#21262d', marginBottom: '20px' }}
          items={[
            {
              key: 'departments',
              label: (
                <span style={{ fontSize: 13, fontWeight: 600 }}>
                  <DollarCircleOutlined style={{ marginRight: 6 }} />
                  {t('org.tabsDepartments')} ({departmentsList.length})
                </span>
              ),
              children: (
                <DepartmentsBudgetTab
                  departments={departmentsList}
                  loading={loadingDepts}
                  onCreateDepartment={handleCreateDepartment}
                  creating={creatingDept}
                  onManageTeam={handleManageTeam}
                />
              ),
            },
            {
              key: 'workflows',
              label: (
                <span style={{ fontSize: 13, fontWeight: 600 }}>
                  <ApartmentOutlined style={{ marginRight: 6 }} />
                  {canvasText.tabLabel} ({workflowsList.length})
                </span>
              ),
              children: (
                <OrgWorkflowsCanvasTab
                  organization={organization}
                  departments={departmentsList}
                  workflows={workflowsList}
                  loading={loadingDepts || loadingWorkflows}
                  onRefresh={handleRefresh}
                  onManageTeam={handleManageTeam}
                />
              ),
            },
            {
              key: 'team',
              label: (
                <span style={{ fontSize: 13, fontWeight: 600 }}>
                  <TeamOutlined style={{ marginRight: 6 }} />
                  {t('org.tabsTeam')}
                </span>
              ),
              children: (
                <TeamInvitationsTab
                  departments={departmentsList}
                  selectedDeptId={selectedDeptId}
                  onSelectDeptId={setSelectedDeptId}
                  deptMembers={deptMembers}
                  loadingMembers={loadingMembers}
                  onInviteMembers={handleInviteMembers}
                  inviting={inviting}
                  recentInvitations={recentInvitations}
                  onRemoveMember={handleRemoveMember}
                  currentUserId={user?.id}
                />
              ),
            },
            {
              key: 'users',
              label: (
                <span style={{ fontSize: 13, fontWeight: 600 }}>
                  <UserOutlined style={{ marginRight: 6 }} />
                  {t('org.tabsUsers')} ({orgUsers.length})
                </span>
              ),
              children: (
                <OrgUsersTab
                  orgUsers={orgUsers}
                  loading={loadingUsers}
                  currentUserId={user?.id}
                  organizationName={organization?.name}
                />
              ),
            },
            {
              key: 'runtime',
              label: (
                <span style={{ fontSize: 13, fontWeight: 600 }}>
                  <SettingOutlined style={{ marginRight: 6 }} />
                  {runtimeText.settings}
                </span>
              ),
              children: <RuntimeSettingsPanel />,
            },
          ]}
        />
      </div>
    </div>
  );
};

export default OrganizationPage;

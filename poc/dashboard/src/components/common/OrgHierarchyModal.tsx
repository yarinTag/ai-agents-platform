import React, { useState, useEffect, useCallback } from 'react';
import {
  Modal,
  Tabs,
  Tag,
  Space,
  Typography,
  message,
} from 'antd';
import {
  BankOutlined,
  TeamOutlined,
  UserOutlined,
  SafetyCertificateOutlined,
  DollarCircleOutlined,
  ApartmentOutlined,
} from '@ant-design/icons';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../i18n';
import { useOrgWorkflowsCanvasText } from '../../i18n/orgWorkflowsCanvas';
import {
  getDepartments,
  createDepartment,
  getDepartmentMembers,
  bulkInviteDepartmentMembers,
  removeDepartmentMember,
  getOrganizationUsers,
  getWorkflows,
} from '../../services/api';
import { Department, DepartmentMember, OrganizationUser, InvitationRecord } from '../../types/auth';
import { PlatformWorkflow } from '../../types/mcp';
import { DepartmentsBudgetTab, TeamInvitationsTab, OrgUsersTab, OrgWorkflowsCanvasTab } from '../org';

const { Text } = Typography;

export interface OrgHierarchyModalProps {
  visible: boolean;
  onClose: () => void;
}

export const OrgHierarchyModal: React.FC<OrgHierarchyModalProps> = ({ visible, onClose }) => {
  const { organization, user, refreshUserProfile } = useAuth();
  const { t } = useTranslation();
  const canvasText = useOrgWorkflowsCanvasText();

  const [activeTab, setActiveTab] = useState<'departments' | 'workflows' | 'team' | 'users'>('departments');
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
      if (res.data.length > 0 && !selectedDeptId) {
        setSelectedDeptId(res.data[0].id);
      }
    } catch (err: any) {
      message.error(t('org.loadDeptsError'));
    } finally {
      setLoadingDepts(false);
    }
  }, [organization?.id, selectedDeptId, t]);

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
    if (visible && organization?.id) {
      loadDepartments();
      loadOrgUsers();
      loadWorkflows();
    }
  }, [visible, organization?.id, loadDepartments, loadOrgUsers, loadWorkflows]);

  useEffect(() => {
    if (selectedDeptId) {
      loadDepartmentMembers(selectedDeptId);
    }
  }, [selectedDeptId, loadDepartmentMembers]);

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
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <BankOutlined style={{ color: '#10b981', fontSize: 20 }} />
          <div>
            <span style={{ fontSize: 16, fontWeight: 700, color: '#f0f6fc' }}>
              {t('org.modalTitle')} ({organization?.name || 'Enterprise'})
            </span>
            <div style={{ fontSize: 12, color: '#8b949e', fontWeight: 400 }}>
              {t('org.orgId')} <code style={{ color: '#58a6ff' }}>{organization?.slug}</code>
              {organization?.domain && (
                <span style={{ marginLeft: 12 }}>
                  {t('org.verifiedDomain')} <code style={{ color: '#34d399' }}>@{organization.domain}</code>
                </span>
              )}
            </div>
          </div>
        </div>
      }
      open={visible}
      onCancel={onClose}
      width={860}
      footer={null}
      destroyOnClose
      style={{ top: 30 }}
    >
      {/* Hierarchy Structure Explanation Banner */}
      <div
        style={{
          background: '#0d1117',
          border: '1px solid #30363d',
          borderRadius: 8,
          padding: '10px 14px',
          marginTop: 12,
          marginBottom: 16,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <Space size={6} wrap>
          <SafetyCertificateOutlined style={{ color: '#10b981', fontSize: 14 }} />
          <Text style={{ color: '#8b949e', fontSize: '11px', fontWeight: 600 }}>
            {t('org.hierarchyTitle')}
          </Text>
          <Tag color="cyan" style={{ fontSize: '11px', margin: 0 }}>
            {t('org.hierarchyOrg')} ({organization?.slug})
          </Tag>
          <span style={{ color: '#484f58' }}>➔</span>
          <Tag color="blue" style={{ fontSize: '11px', margin: 0 }}>
            {t('org.hierarchyDepartments')}
          </Tag>
          <span style={{ color: '#484f58' }}>➔</span>
          <Tag color="purple" style={{ fontSize: '11px', margin: 0 }}>
            {t('org.hierarchyRoles')}
          </Tag>
          <span style={{ color: '#484f58' }}>➔</span>
          <Tag color="green" style={{ fontSize: '11px', margin: 0 }}>
            {t('org.hierarchyAgents')}
          </Tag>
        </Space>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={(k) => setActiveTab(k as any)}
        tabBarStyle={{ borderColor: '#21262d' }}
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
                onRefresh={() => {
                  loadDepartments();
                  loadWorkflows();
                }}
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
        ]}
      />
    </Modal>
  );
};

export default OrgHierarchyModal;

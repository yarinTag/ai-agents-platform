import React, { useEffect, useState } from 'react';
import { Form, message } from 'antd';
import { Agent } from '../types/agent';
import { useAuth } from '../context/AuthContext';
import { getAgents, createAgent, updateAgent, getSkills, getAvailableModels, DiscoveredModel, scanPlugins } from '../services/api';

export const useAgentsPage = () => {
  const { departments, activeDepartmentId, organization } = useAuth();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [availableSkills, setAvailableSkills] = useState<any[]>([]);
  const [availableModels, setAvailableModels] = useState<DiscoveredModel[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [visible, setVisible] = useState<boolean>(false);
  const [folderPickerVisible, setFolderPickerVisible] = useState<boolean>(false);
  const [form] = Form.useForm();
  const [editingKey, setEditingKey] = useState<string>('');
  const [activeTab, setActiveTab] = useState<string>('roster');
  const [chatAgent, setChatAgent] = useState<Agent | null>(null);
  const [chatVisible, setChatVisible] = useState<boolean>(false);
  const [customDepartments, setCustomDepartments] = useState<string[]>([]);
  const [deptSearchText, setDeptSearchText] = useState<string>('');
  const [newCustomDept, setNewCustomDept] = useState<string>('');

  const dynamicDepartments = React.useMemo(() => {
    const set = new Set<string>([...customDepartments]);
    agents.forEach((a) => {
      if (a.department?.trim()) set.add(a.department.trim());
    });
    const opts = Array.from(set).map((d) => ({ value: d, label: d }));

    const searchTrimmed = deptSearchText.trim();
    if (searchTrimmed && !set.has(searchTrimmed)) {
      opts.unshift({
        value: searchTrimmed,
        label: `➕ Create department "${searchTrimmed}"`,
      });
    }
    return opts;
  }, [agents, customDepartments, deptSearchText]);

  const departmentOptions = React.useMemo(() => {
    if (departments && departments.length > 0) {
      return departments.map((d) => ({
        value: d.id,
        label: `📁 ${d.name}`,
        name: d.name,
      }));
    }
    return dynamicDepartments;
  }, [departments, dynamicDepartments]);

  const handleAddCustomDept = (nameToAdd?: string) => {
    const val = (nameToAdd || newCustomDept).trim();
    if (!val) return;
    if (!customDepartments.includes(val)) {
      setCustomDepartments((prev) => [...prev, val]);
    }
    form.setFieldsValue({ department: val });
    setNewCustomDept('');
    setDeptSearchText('');
  };

  const fetchAgents = async () => {
    try {
      setLoading(true);
      const res = await getAgents();
      setAgents(res.data || []);
    } catch (err) {
      console.error(err);
      message.error('Failed to load agents roster');
    } finally {
      setLoading(false);
    }
  };

  const fetchSkillsAndModels = async () => {
    try {
      const [skillsRes, pluginsRes, modelsRes] = await Promise.all([
        getSkills().catch(() => ({ data: [] })),
        scanPlugins().catch(() => ({ data: { plugins: [] } })),
        getAvailableModels().catch(() => ({ data: [] })),
      ]);

      const formattedOptions: any[] = [];

      if (pluginsRes.data && pluginsRes.data.plugins) {
        pluginsRes.data.plugins.forEach((pkg: any) => {
          if (pkg.skills && pkg.skills.length > 0) {
            formattedOptions.push({
              label: `📦 ${pkg.display_name || pkg.name.toUpperCase()} (${pkg.skills.length})`,
              title: pkg.name,
              options: pkg.skills.map((s: any) => ({
                label: `⚡ ${s.name} (${s.id})`,
                value: s.id,
                title: s.description,
              })),
            });
          }
        });
      }

      if (skillsRes.data && skillsRes.data.length > 0) {
        formattedOptions.push({
          label: `💾 Custom / DB Skills (${skillsRes.data.length})`,
          title: 'custom',
          options: skillsRes.data.map((s: any) => ({
            label: `⚡ ${s.name} (${s.id})`,
            value: s.id,
            title: s.description || '',
          })),
        });
      }

      setAvailableSkills(formattedOptions);

      if (modelsRes.data) {
        setAvailableModels(modelsRes.data);
      }
    } catch {
      // Fallback
    }
  };

  useEffect(() => {
    fetchAgents();
    fetchSkillsAndModels();
  }, []);

  const handleCreate = () => {
    form.resetFields();
    const activeDept = departments.find((d) => d.id === activeDepartmentId) || departments[0];
    const initialDeptId = activeDept?.id || null;
    const initialDeptName = activeDept?.name || customDepartments[0] || (agents[0]?.department) || 'Engineering';

    form.setFieldsValue({
      role_type: 'WORKER',
      department_id: initialDeptId,
      department: initialDeptName,
      organization_id: organization?.id || null,
      model: 'default',
      max_tokens: 8000,
      temperature: 0.7,
      max_concurrent_children: 3,
      avatar: 'frontend_dev',
    });
    setEditingKey('');
    setVisible(true);
  };

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      if (Array.isArray(values.department)) {
        values.department = values.department[0] || '';
      }
      if (typeof values.department === 'string') {
        values.department = values.department.trim();
      }

      // Link both department_id and department
      const selectedDeptId =
        values.department_id ||
        departments.find((d) => d.name === values.department)?.id ||
        activeDepartmentId;

      const matchedDept = departments.find(
        (d) => d.id === selectedDeptId || d.id === values.department || d.name === values.department
      );

      if (matchedDept) {
        values.department_id = matchedDept.id;
        values.department = matchedDept.name;
      } else if (selectedDeptId) {
        values.department_id = selectedDeptId;
      }

      if (organization?.id && !values.organization_id) {
        values.organization_id = organization.id;
      }

      if (editingKey) {
        await updateAgent(editingKey, values);
        message.success('Agent updated successfully');
      } else {
        await createAgent(values);
        message.success('Agent created successfully');
      }
      setVisible(false);
      fetchAgents();
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Failed to save agent';
      message.error(detail);
      console.error(err);
    }
  };

  const officeFloorAgents = React.useMemo(() => {
    return agents.filter(
      (a) =>
        a.role_type !== 'WORKFLOW_AUTOMATION' &&
        !(a as any).is_workflow_agent &&
        a.department !== 'Workflow Automations'
    );
  }, [agents]);

  const workflowAgents = React.useMemo(() => {
    return agents.filter(
      (a) =>
        a.role_type === 'WORKFLOW_AUTOMATION' ||
        Boolean((a as any).is_workflow_agent) ||
        a.department === 'Workflow Automations'
    );
  }, [agents]);

  const eligibleManagers = agents.filter((a) => {
    if (editingKey && a.id === editingKey) return false;
    const r = (a.role_type || '').toUpperCase();
    return r === 'MANAGER' || r === 'ROOT_ORCHESTRATOR';
  });

  return {
    departments,
    activeDepartmentId,
    organization,
    agents,
    setAgents,
    availableSkills,
    setAvailableSkills,
    availableModels,
    setAvailableModels,
    loading,
    setLoading,
    visible,
    setVisible,
    folderPickerVisible,
    setFolderPickerVisible,
    form,
    editingKey,
    setEditingKey,
    activeTab,
    setActiveTab,
    chatAgent,
    setChatAgent,
    chatVisible,
    setChatVisible,
    customDepartments,
    setCustomDepartments,
    deptSearchText,
    setDeptSearchText,
    newCustomDept,
    setNewCustomDept,
    dynamicDepartments,
    departmentOptions,
    handleAddCustomDept,
    fetchAgents,
    fetchSkillsAndModels,
    handleCreate,
    handleOk,
    officeFloorAgents,
    workflowAgents,
    eligibleManagers,
  };
};

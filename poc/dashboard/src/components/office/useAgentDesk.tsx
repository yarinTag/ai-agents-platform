import type { AgentDeskDrawerProps } from './agentDeskTypes';
import React, { useState, useEffect } from 'react';
import { Form, message } from 'antd';

import { createTask, updateAgent, scanPlugins, getSkills } from '../../services/api';

import { useAuth } from '../../context/AuthContext';


export function useAgentDesk({ agent, tasks, visible, onClose, onTaskCreated, agents }: AgentDeskDrawerProps) {
  const { departments, activeDepartmentId, organization } = useAuth();
  const [form] = Form.useForm();
  const [repoForm] = Form.useForm();
  const [running, setRunning] = useState(false);
  const [savingRepo, setSavingRepo] = useState(false);
  const [availableSkills, setAvailableSkills] = useState<any[]>([]);
  const [customDepartments, setCustomDepartments] = useState<string[]>([]);
  const [deptSearchText, setDeptSearchText] = useState<string>('');
  const [newCustomDept, setNewCustomDept] = useState<string>('');

  const dynamicDepartments = React.useMemo(() => {
    const set = new Set<string>([...customDepartments]);
    if (agents) {
      agents.forEach((a) => {
        if (a.department?.trim()) set.add(a.department.trim());
      });
    }
    if (agent?.department?.trim()) {
      set.add(agent.department.trim());
    }
    const opts = Array.from(set).map((d) => ({ value: d, label: d }));

    const searchTrimmed = deptSearchText.trim();
    if (searchTrimmed && !set.has(searchTrimmed)) {
      opts.unshift({
        value: searchTrimmed,
        label: `➕ Create department "${searchTrimmed}"`,
      });
    }
    return opts;
  }, [agents, agent, customDepartments, deptSearchText]);

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
    repoForm.setFieldsValue({ department: val });
    setNewCustomDept('');
    setDeptSearchText('');
  };

  useEffect(() => {
    const fetchSkills = async () => {
      try {
        const [skillsRes, pluginsRes] = await Promise.all([
          getSkills().catch(() => ({ data: [] })),
          scanPlugins().catch(() => ({ data: { plugins: [] } })),
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
      } catch {
        // Fallback
      }
    };
    fetchSkills();
  }, []);

  useEffect(() => {
    if (agent) {
      const matchedDept = departments.find(
        (d) => d.id === agent.department_id || d.name === agent.department
      );
      repoForm.setFieldsValue({
        repo_path: agent.repo_path || 'C:\\Users\\taguo\\Desktop\\ai-agents-platform',
        github_url: agent.github_url || '',
        model: agent.model || 'default',
        department_id: agent.department_id || matchedDept?.id || activeDepartmentId || null,
        department: agent.department || matchedDept?.name || 'Engineering',
        skills: agent.skills || [],
      });
    }
  }, [agent, repoForm, departments, activeDepartmentId]);

  const agentTasks = agent ? tasks.filter((t) => String(t.agent_id) === String(agent.id)) : [];
  const activeTask = agentTasks.find((t) => t.status === 'running' || t.status === 'queued');

  const handleLaunchTask = async () => {
    if (!agent) return;
    try {
      const values = await form.validateFields();
      setRunning(true);
      let parsedInput: Record<string, any> = {};
      try {
        parsedInput = values.input_data ? JSON.parse(values.input_data) : { prompt: values.prompt };
      } catch {
        parsedInput = { prompt: values.prompt || values.input_data };
      }

      await createTask({
        agent_id: agent.id,
        project_id: null,
        skill_id: null,
        input_data: parsedInput,
      });

      message.success(`Task dispatched to ${agent.name}!`);
      form.resetFields();
      onTaskCreated();
    } catch (err) {
      message.error('Failed to launch task');
      console.error(err);
    } finally {
      setRunning(false);
    }
  };

  const handleSaveRepo = async () => {
    if (!agent) return;
    try {
      const values = await repoForm.validateFields();
      if (Array.isArray(values.department)) {
        values.department = values.department[0] || 'Engineering';
      }
      if (typeof values.department === 'string') {
        values.department = values.department.trim() || 'Engineering';
      }

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

      setSavingRepo(true);
      await updateAgent(agent.id, {
        repo_path: values.repo_path,
        github_url: values.github_url,
        model: values.model,
        department: values.department,
        department_id: values.department_id,
        organization_id: organization?.id,
        skills: values.skills || [],
      });
      message.success('Workstation configuration updated!');
      agent.repo_path = values.repo_path;
      agent.github_url = values.github_url;
      agent.model = values.model;
      agent.department = values.department;
      agent.department_id = values.department_id;
      agent.organization_id = organization?.id;
      agent.skills = values.skills || [];
      onTaskCreated();
    } catch (err) {
      message.error('Failed to update workstation configuration');
      console.error(err);
    } finally {
      setSavingRepo(false);
    }
  };

  return {
    agent, tasks, visible, onClose, onTaskCreated,
    agents, departments, activeDepartmentId, organization, form,
    repoForm, running, setRunning, savingRepo, setSavingRepo,
    availableSkills, setAvailableSkills, customDepartments, setCustomDepartments, deptSearchText,
    setDeptSearchText, newCustomDept, setNewCustomDept, dynamicDepartments, departmentOptions,
    handleAddCustomDept, agentTasks, activeTask, handleLaunchTask, handleSaveRepo,
  };
}

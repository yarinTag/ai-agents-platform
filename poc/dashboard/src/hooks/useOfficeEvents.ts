import { useState, useEffect, useCallback } from 'react';
import { Agent } from '../types/agent';
import { Task } from '../types/task';
import { getAgents, getTasks } from '../services/api';
import { eventStream, ConnectionStatus, PlatformEventPayload } from '../services/eventStream';

export function useOfficeEvents() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('disconnected');
  const [lastEvent, setLastEvent] = useState<PlatformEventPayload | null>(null);

  // Full fetch fallback / initial load
  const fetchData = useCallback(async () => {
    try {
      const [agentsRes, tasksRes] = await Promise.all([getAgents(), getTasks()]);
      setAgents(agentsRes.data || []);
      setTasks(tasksRes.data || []);
    } catch (err) {
      console.error('[useOfficeEvents] Failed to load data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // 1. Initial snapshot fetch
    fetchData();

    // 2. Track connection status
    const unsubStatus = eventStream.onStatusChange((status) => {
      setConnectionStatus(status);
    });

    // 3. Connect to SSE
    eventStream.connect();

    // 4. Live Agent Events
    const unsubAgentCreated = eventStream.subscribe('agent_created', (event) => {
      setLastEvent(event);
      const newAgent: Agent = event.payload as Agent;
      if (newAgent && newAgent.id) {
        setAgents((prev) => {
          const idx = prev.findIndex((a) => a.id === newAgent.id);
          if (idx >= 0) {
            const next = [...prev];
            next[idx] = { ...next[idx], ...newAgent };
            return next;
          }
          return [...prev, newAgent];
        });
      }
    });

    const unsubAgentUpdated = eventStream.subscribe('agent_updated', (event) => {
      setLastEvent(event);
      const updatedAgent: Agent = event.payload as Agent;
      if (updatedAgent && updatedAgent.id) {
        setAgents((prev) =>
          prev.map((a) => (a.id === updatedAgent.id ? { ...a, ...updatedAgent } : a))
        );
      }
    });

    const unsubAgentDeleted = eventStream.subscribe('agent_deleted', (event) => {
      setLastEvent(event);
      const deletedId = event.agent_id || event.payload?.id;
      if (deletedId) {
        setAgents((prev) => prev.filter((a) => a.id !== deletedId));
      }
    });

    // 5. Live Task Events
    const unsubTaskCreated = eventStream.subscribe('task_created', (event) => {
      setLastEvent(event);
      const rawTask = event.payload;
      const taskId = rawTask.run_id || rawTask.id || event.task_id;
      if (taskId) {
        setTasks((prev) => {
          const idx = prev.findIndex((t) => t.id === taskId || t.run_id === taskId);
          const taskObj: Task = {
            id: taskId,
            run_id: taskId,
            agent_id: rawTask.agent_id || event.agent_id || '',
            project_id: rawTask.project_id || event.project_id,
            prompt: rawTask.prompt || '',
            status: rawTask.status || 'queued',
            created_at: rawTask.created_at || event.timestamp,
            started_at: rawTask.started_at,
            ended_at: rawTask.ended_at,
            parent_task_id: rawTask.parent_task_id || event.parent_task_id,
            root_task_id: rawTask.root_task_id,
            assigned_by: rawTask.assigned_by,
          };
          if (idx >= 0) {
            const next = [...prev];
            next[idx] = { ...next[idx], ...taskObj };
            return next;
          }
          return [taskObj, ...prev];
        });
      }
    });

    const unsubTaskStarted = eventStream.subscribe('task_started', (event) => {
      setLastEvent(event);
      const taskId = event.task_id;
      if (taskId) {
        setTasks((prev) =>
          prev.map((t) =>
            t.id === taskId || t.run_id === taskId
              ? { ...t, status: 'running', started_at: event.timestamp }
              : t
          )
        );
      }
      if (event.agent_id) {
        setAgents((prev) =>
          prev.map((a) => (a.id === event.agent_id ? { ...a, status: 'running' } : a))
        );
      }
    });

    const unsubTaskCompleted = eventStream.subscribe('task_completed', (event) => {
      setLastEvent(event);
      const taskId = event.task_id;
      if (taskId) {
        setTasks((prev) =>
          prev.map((t) =>
            t.id === taskId || t.run_id === taskId
              ? { ...t, status: 'completed', ended_at: event.timestamp, result: event.payload?.result }
              : t
          )
        );
      }
      if (event.agent_id) {
        setAgents((prev) =>
          prev.map((a) => (a.id === event.agent_id ? { ...a, status: 'idle' } : a))
        );
      }
    });

    const unsubTaskFailed = eventStream.subscribe('task_failed', (event) => {
      setLastEvent(event);
      const taskId = event.task_id;
      if (taskId) {
        setTasks((prev) =>
          prev.map((t) =>
            t.id === taskId || t.run_id === taskId
              ? { ...t, status: 'failed', ended_at: event.timestamp, error: event.payload?.error }
              : t
          )
        );
      }
      if (event.agent_id) {
        setAgents((prev) =>
          prev.map((a) => (a.id === event.agent_id ? { ...a, status: 'error' } : a))
        );
      }
    });

    const unsubTaskDelegated = eventStream.subscribe('task_delegated', (event) => {
      setLastEvent(event);
      // When task is delegated, refresh tasks to capture updated tree lineage
      fetchData();
    });

    const unsubTaskDeleted = eventStream.subscribe('task_deleted', (event) => {
      setLastEvent(event);
      const deletedTaskId = event.task_id || event.payload?.run_id || event.payload?.id;
      if (deletedTaskId) {
        setTasks((prev) => prev.filter((t) => t.id !== deletedTaskId && t.run_id !== deletedTaskId));
      }
    });

    return () => {
      unsubStatus();
      unsubAgentCreated();
      unsubAgentUpdated();
      unsubAgentDeleted();
      unsubTaskCreated();
      unsubTaskStarted();
      unsubTaskCompleted();
      unsubTaskFailed();
      unsubTaskDelegated();
      unsubTaskDeleted();
    };
  }, [fetchData]);

  return {
    agents,
    tasks,
    loading,
    connectionStatus,
    lastEvent,
    refresh: fetchData,
  };
}

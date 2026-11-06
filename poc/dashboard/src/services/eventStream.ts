import { getRequestDepartment } from './requestScope';
/**
 * Global SSE Event Stream Service.
 * Connects to the FastAPI backend SSE endpoint (/api/v1/events/stream)
 * with auto-reconnection, sequence tracking, and typed subscriber callbacks.
 * ZERO MOCKS: Consumes real platform events from SQLite event_log.
 */

export interface PlatformEventPayload {
  event_id: string;
  sequence_number: number;
  event_type: string;
  agent_id?: string | null;
  task_id?: string | null;
  execution_id?: string | null;
  parent_task_id?: string | null;
  project_id?: string | null;
  correlation_id?: string | null;
  payload: Record<string, any>;
  source: string;
  timestamp: string;
}

export type ConnectionStatus = 'connecting' | 'connected' | 'reconnecting' | 'disconnected';
export type EventHandler = (event: PlatformEventPayload) => void;

class EventStreamService {
  private eventSource: EventSource | null = null;
  private lastSequence: number = 0;
  private status: ConnectionStatus = 'disconnected';
  private listeners: Map<string, Set<EventHandler>> = new Map();
  private statusListeners: Set<(status: ConnectionStatus) => void> = new Set();
  private reconnectTimer: any = null;
  private baseUrl: string = 'http://localhost:8000';

  constructor() {
    this.listeners.set('*', new Set());
  }

  public setBaseUrl(url: string) {
    this.baseUrl = url;
  }

  public getStatus(): ConnectionStatus {
    return this.status;
  }

  public getLastSequence(): number {
    return this.lastSequence;
  }

  public connect(): void {
    if (this.eventSource && (this.status === 'connected' || this.status === 'connecting')) {
      return;
    }

    const token = localStorage.getItem('agents_platform_auth_token');
    if (!token) {
      this.setStatus('disconnected');
      return;
    }

    this.setStatus('connecting');

    const streamUrl = new URL(`${this.baseUrl}/api/v1/events/stream`);
    streamUrl.searchParams.set('token', token);
    const department = getRequestDepartment();
    if (department) streamUrl.searchParams.set('department_id', department);
    if (this.lastSequence > 0) {
      streamUrl.searchParams.set('after_sequence', String(this.lastSequence));
    }

    try {
      this.eventSource = new EventSource(streamUrl.toString());

      this.eventSource.onopen = () => {
        this.setStatus('connected');
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };

      this.eventSource.onerror = () => {
        this.setStatus('reconnecting');
        this.closeEventSource();
        this.scheduleReconnect();
      };

      // Listen to generic messages and specific event types
      const registeredTypes = [
        'connected',
        'heartbeat',
        'agent.created',
        'agent.updated',
        'agent.deleted',
        'agent_created',
        'agent_updated',
        'agent_deleted',
        'task.created',
        'task.started',
        'task.completed',
        'task.failed',
        'task.cancelled',
        'task.delegated',
        'task.deleted',
        'task_created',
        'task_started',
        'task_completed',
        'task_failed',
        'task_cancelled',
        'task_delegated',
        'task_deleted',
      ];

      registeredTypes.forEach((type) => {
        this.eventSource?.addEventListener(type, (e: MessageEvent) => {
          this.handleIncomingMessage(type, e.data);
        });
      });

      this.eventSource.onmessage = (e: MessageEvent) => {
        this.handleIncomingMessage('message', e.data);
      };
    } catch (err) {
      console.error('[EventStream] Connection initialization error:', err);
      this.setStatus('reconnecting');
      this.scheduleReconnect();
    }
  }

  private handleIncomingMessage(eventType: string, rawData: string): void {
    try {
      const parsed = JSON.parse(rawData);

      // Extract sequence number if present
      if (parsed.sequence_number && parsed.sequence_number > this.lastSequence) {
        this.lastSequence = parsed.sequence_number;
      }

      const eventPayload: PlatformEventPayload = {
        event_id: parsed.event_id || parsed.id || `evt-${Date.now()}`,
        sequence_number: parsed.sequence_number || this.lastSequence,
        event_type: parsed.event_type || eventType,
        agent_id: parsed.agent_id,
        task_id: parsed.task_id,
        execution_id: parsed.execution_id,
        parent_task_id: parsed.parent_task_id,
        project_id: parsed.project_id,
        correlation_id: parsed.correlation_id,
        payload: parsed.payload || parsed,
        source: parsed.source || 'backend_sse',
        timestamp: parsed.timestamp || new Date().toISOString(),
      };

      // Dispatch to specific event listeners (supporting both dot and underscore)
      const rawType = eventPayload.event_type;
      const typeWithDots = rawType.replace(/_/g, '.');
      const typeWithUnderscores = rawType.replace(/\./g, '_');
      const typesToNotify = new Set([rawType, typeWithDots, typeWithUnderscores]);

      typesToNotify.forEach((t) => {
        const specific = this.listeners.get(t);
        if (specific) {
          specific.forEach((fn) => fn(eventPayload));
        }
      });

      // Dispatch to wildcard listeners
      const wildcard = this.listeners.get('*');
      if (wildcard) {
        wildcard.forEach((fn) => fn(eventPayload));
      }
    } catch (err) {
      console.warn('[EventStream] Failed to parse event JSON:', rawData, err);
    }
  }

  private setStatus(newStatus: ConnectionStatus): void {
    if (this.status !== newStatus) {
      this.status = newStatus;
      this.statusListeners.forEach((listener) => listener(newStatus));
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    const token = localStorage.getItem('agents_platform_auth_token');
    if (!token) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, 3000);
  }

  private closeEventSource(): void {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  public disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.closeEventSource();
    this.setStatus('disconnected');
    this.lastSequence = 0;
  }

  public subscribe(eventType: string, handler: EventHandler): () => void {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }
    this.listeners.get(eventType)!.add(handler);

    return () => {
      this.listeners.get(eventType)?.delete(handler);
    };
  }

  public subscribeAll(handler: EventHandler): () => void {
    return this.subscribe('*', handler);
  }

  public onStatusChange(callback: (status: ConnectionStatus) => void): () => void {
    this.statusListeners.add(callback);
    callback(this.status);
    return () => {
      this.statusListeners.delete(callback);
    };
  }
}

export const eventStream = new EventStreamService();

export interface QueueStatus {
  broker: string;
  connected: boolean;
  queues: Record<string, number>;
  dead_letter_count: number;
  worker_running: boolean;
  active_worker_tasks: number;
  timestamp: string;
}

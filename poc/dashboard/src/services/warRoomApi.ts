import { api } from './httpClient';
import type { WarRoomSession, WarRoomDetail, WarRoomCreateDto, WarRoomMessageCreateDto } from '../types/collab';

// Phase 3: Multi-Agent War Room & Deliberation
export const getWarRoomSessions = (projectId?: string) =>
  api.get<WarRoomSession[]>('/api/v1/war-room/', { params: { project_id: projectId } });
export const createWarRoomSession = (data: WarRoomCreateDto) =>
  api.post<WarRoomSession>('/api/v1/war-room/', data);
export const getWarRoomSession = (sessionId: string) =>
  api.get<WarRoomDetail>(`/api/v1/war-room/${sessionId}`);
export const sendWarRoomMessage = (sessionId: string, data: WarRoomMessageCreateDto) =>
  api.post('/api/v1/war-room/' + sessionId + '/messages', data);
export const synthesizeWarRoomPlan = (sessionId: string, synthesized_plan: string) =>
  api.post<WarRoomSession>(`/api/v1/war-room/${sessionId}/synthesize`, { synthesized_plan });

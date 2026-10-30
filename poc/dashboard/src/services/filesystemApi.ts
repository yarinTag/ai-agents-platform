import { api } from './httpClient';
import type { BrowseResponse, PickFolderResponse } from '../types/filesystem';

// Filesystem & Local Workspace Picker
export const browseDirectory = (path?: string) =>
  api.get<BrowseResponse>('/api/v1/fs/browse', { params: path ? { path } : {} });

export const pickFolderNative = (initialPath?: string) =>
  api.post<PickFolderResponse>('/api/v1/fs/pick-folder', { initial_path: initialPath }, { timeout: 180000 });

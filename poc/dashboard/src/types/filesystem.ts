export interface FolderItem {
  name: string;
  path: string;
  is_project: boolean;
  project_type?: string;
  has_children: boolean;
}

export interface QuickAccessItem {
  name: string;
  path: string;
  icon?: string;
}

export interface BrowseResponse {
  current_path: string;
  parent_path?: string | null;
  name: string;
  is_root: boolean;
  quick_access: QuickAccessItem[];
  folders: FolderItem[];
}

export interface PickFolderResponse {
  path?: string | null;
  name?: string | null;
  is_project: boolean;
  project_type?: string | null;
  cancelled: boolean;
  error?: string | null;
}

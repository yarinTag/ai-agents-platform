export interface Skill {
  id: string;
  name: string;
  description?: string;
  content: string;
  project_id?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface PluginSkill {
  id: string;
  name: string;
  filename: string;
  path: string;
  description: string;
  plugin: string;
  domain?: string;
  version?: string;
  role?: string;
  content_preview?: string;
  connected_skills?: string[];
}

export interface PluginPackage {
  name: string;
  display_name?: string;
  version?: string;
  description?: string;
  domain?: string;
  path: string;
  skills_count: number;
  skills: PluginSkill[];
}

export interface PluginsConfig {
  source_mode: 'local' | 'git';
  git_repo?: string;
  local_path?: string;
  updated_at?: string;
}

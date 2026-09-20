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
}

export interface PluginPackage {
  name: string;
  path: string;
  skills_count: number;
  skills: PluginSkill[];
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  working_directory?: string;
  instructions?: string;
  skills?: string[];
  allowed_tools?: string[];
  created_at?: string;
  updated_at?: string;
}

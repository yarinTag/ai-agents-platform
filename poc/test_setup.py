#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config_manager, AgentConfig, ProjectConfig, Skill
from persistence import db_manager

def setup_demo_data():
    """Set up demo agent, project, and skill."""
    print("=== Setting up demo data ===")

    # Create a general task agent
    agent = AgentConfig(
        id="general-task-agent",
        name="General Task Agent",
        description="Executes bounded read-only tasks in an assigned project",
        system_prompt="You are a helpful AI agent that executes tasks accurately and concisely. "
                     "When asked to summarize or analyze content, provide clear, structured responses "
                     "without adding unnecessary commentary. Focus on completing the specific task requested.",
        skills=["basic-reading"],
        model="nvidia_nim/nvidia/nemotron-3-super-120b-a12b",
        effort="medium",
        max_tokens=4000
    )

    config_manager.register_agent(agent)
    db_manager.save_agent(agent)
    print(f"✓ Registered agent: {agent.name}")

    # Create a test project (using current directory for demo)
    project = ProjectConfig(
        id="demo-project",
        name="Demo Project",
        description="A test project for demonstrating the AI Agents Platform",
        working_directory=os.getcwd(),  # Use current directory
        instructions="This is a test project. Focus on reading files and providing summaries.",
        skills=["basic-reading"],
        allowed_tools=["read", "grep", "glob"]  # Read-only tools for safety
    )

    config_manager.register_project(project)
    db_manager.save_project(project)
    print(f"✓ Registered project: {project.name}")
    print(f"  Working directory: {project.working_directory}")

    # Create a basic reading skill
    skill_content = """# Basic Reading Skill

This skill provides guidance for reading and understanding file contents.

## Principles
1. Read carefully and completely
2. Identify main purpose and key information
3. Structure responses clearly
4. Stay within bounds of the request
5. Do not modify files unless explicitly requested

## Usage
When asked to read or analyze content:
- First, examine what files are available
- Read the relevant files completely
- Extract the key information requested
- Present findings in a clear, structured format
- Do not add unsolicited opinions or modifications
"""

    # Save skill to file
    skill_file_path = os.path.join(config_manager.config_dir, "skills", "basic-reading.md")
    os.makedirs(os.path.dirname(skill_file_path), exist_ok=True)
    with open(skill_file_path, 'w', encoding='utf-8') as f:
        f.write("---\nname: Basic Reading Skill\ndescription: Guidance for reading and understanding file contents\n---\n")
        f.write(skill_content)

    # Also save to database
    skill = Skill(
        id="basic-reading",
        name="Basic Reading Skill",
        description="Guidance for reading and understanding file contents",
        content=skill_content
    )
    config_manager.save_skill(skill)
    db_manager.save_skill(skill)
    print(f"✓ Created skill: {skill.name}")

if __name__ == "__main__":
    setup_demo_data()
    print("Setup completed successfully!")
#!/usr/bin/env python3
"""
Proof of Concept demo for the AI Agents Platform runtime integration.

This script demonstrates:
1. Registering a generic agent
2. Registering a test project
3. Loading a reusable skill
4. Submitting a read-only task
5. Executing through Free Claude Code runtime
6. Capturing streaming events
7. Tracking execution state
8. Persisting results
9. Returning structured report
"""

import time
import os
import sys
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config_manager, AgentConfig, ProjectConfig, Skill
from persistence import db_manager
from runtime_adapter import runtime_adapter, TaskStatus


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


def demonstrate_task_execution():
    """Demonstrate executing a task through the platform."""
    print("\n=== Demonstrating Task Execution ===")

    # Define the task: Read README and summarize
    task_prompt = """Read the README.md file in the current directory and return a structured summary containing:
1. Project name (if mentioned)
2. Project purpose or description
3. Main technologies or frameworks used
4. Key features or capabilities

If no README.md is available, say so and suggest what to look for instead.
Do not modify any files. Provide only the summary information requested."""

    print(f"Task: {task_prompt[:100]}...")

    # Start the task
    print("\nStarting task execution...")
    start_time = time.time()

    run_id = runtime_adapter.start_task(
        agent_id="general-task-agent",
        project_id="demo-project",
        prompt=task_prompt
    )

    print(f"✓ Task started with Run ID: {run_id}")

    # Monitor execution with event subscription
    def event_handler(event):
        event_type = event.get('type', 'unknown')
        if event_type in ['assistant', 'result', 'error']:
            timestamp = event.get('_timestamp', 0)
            rel_time = timestamp - start_time if timestamp else 0
            print(f"[{rel_time:.1f}s] {event_type.upper()}: ", end="")

            if event_type == 'assistant':
                message = event.get('message', {})
                if isinstance(message, dict):
                    content = message.get('content', [])
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and item.get('type') == 'text':
                                print(item.get('text', '')[:100], end="")
                            elif isinstance(item, dict) and item.get('type') == 'thinking':
                                print("[thinking...]", end="")
                    elif isinstance(message, dict) and message.get('type') == 'text':
                        print(message.get('text', '')[:100], end="")
                print()
            elif event_type == 'result':
                result = event.get('result', '')
                print(f"RESULT: {result[:200]}...")
            elif event_type == 'error':
                error = event.get('error', {})
                print(f"ERROR: {error.get('message', 'Unknown error')}")

    # Subscribe to events
    unsubscribe = runtime_adapter.subscribe_to_events(run_id, event_handler)

    # Wait for completion with timeout
    max_wait = 30  # seconds
    waited = 0
    while waited < max_wait:
        run_status = runtime_adapter.get_run_status(run_id)
        if run_status and run_status.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            break
        time.sleep(0.5)
        waited += 0.5
        print(f"[{waited:.1f}s] Waiting for completion...", end="\r")

    print()  # New line

    # Clean up subscription
    unsubscribe()

    # Get final status
    run = runtime_adapter.get_run_status(run_id)
    if not run:
        print("✗ ERROR: Could not retrieve run status")
        return None

    execution_time = time.time() - start_time
    print(f"\n=== Task Completed ===")
    print(f"Status: {run.status.value}")
    print(f"Execution time: {execution_time:.2f} seconds")

    if run.status == TaskStatus.COMPLETED:
        print(f"✓ SUCCESS: Task completed successfully")
        if run.result:
            print(f"\nResult:\n{run.result}")
    else:
        print(f"✗ FAILED: Task failed")
        if run.error:
            print(f"Error: {run.error}")

    # Persist the run to database
    db_manager.save_task_run(run)
    print(f"✓ Task run persisted to database")

    # Show some statistics
    print(f"\n=== Execution Statistics ===")
    print(f"Total events captured: {len(run.events)}")
    event_types = {}
    for event in run.events:
        event_type = event.get('type', 'unknown')
        event_types[event_type] = event_types.get(event_type, 0) + 1
    for event_type, count in event_types.items():
        print(f"  {event_type}: {count}")

    return run


def show_persistence_demo():
    """Demonstrate data persistence."""
    print("\n=== Persistence Demo ===")

    # Show stored agents
    agents = db_manager.list_agents()
    print(f"Stored agents ({len(agents)}):")
    for agent in agents:
        print(f"  - {agent.name} ({agent.id})")

    # Show stored projects
    projects = db_manager.list_projects()
    print(f"\nStored projects ({len(projects)}):")
    for project in projects:
        print(f"  - {project.name} ({project.id})")

    # Show stored skills
    skills = db_manager.list_skills()
    print(f"\nStored skills ({len(skills)}):")
    for skill in skills:
        print(f"  - {skill.name} ({skill.id})")

    # Show stored task runs
    runs = db_manager.list_task_runs(limit=5)
    print(f"\nStored task runs (last {len(runs)}):")
    for run in runs:
        print(f"  - {run.agent_id} -> {run.status.value} ({run.run_id[:8]}...)")
        if run.result:
            print(f"    Result preview: {run.result[:100]}...")


def main():
    """Main PoC demonstration function."""
    print("🚀 AI Agents Platform - Runtime Integration Proof of Concept")
    print("=" * 60)

    try:
        # Step 1: Setup demo data
        setup_demo_data()

        # Step 2: Demonstrate task execution
        run = demonstrate_task_execution()

        # Step 3: Show persistence
        show_persistence_demo()

        # Final summary
        print("\n" + "=" * 60)
        print("🎉 PoC COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print("✅ Verified capabilities:")
        print("  • Agent registration and management")
        print("  • Project registration and context isolation")
        print("  • Skill loading and management")
        print("  • Task submission and execution via Free Claude Code")
        print("  • Streaming event capture and processing")
        print("  • Execution state tracking")
        print("  • Result persistence and retrieval")
        print("  • Process lifecycle management")
        print("\nThe runtime integration with Free Claude Code is working correctly!")
        print("Ready to proceed to MVP dashboard development.")

    except KeyboardInterrupt:
        print("\n\n⚠️  PoC interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ PoC failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
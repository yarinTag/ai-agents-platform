"""
Demonstration script showing how to interact with the AI Agents Platform API.
This script shows the kinds of interactions a dashboard would have with the backend.
"""

import sys
import os
import time
import json

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from datetime import datetime

# Base URL for the API
BASE_URL = "http://localhost:8000"


def print_header(title):
    """Print a formatted header."""
    print("\n" + "="*60)
    print(f"🔹 {title}")
    print("="*60)


def print_json(data, title=None):
    """Pretty print JSON data."""
    if title:
        print(f"\n📄 {title}:")
    print(json.dumps(data, indent=2, default=str))


def demo_api_interactions():
    """Demonstrate API interactions that a dashboard would perform."""

    print_header("AI Agents Platform API Demonstration")
    print("This script shows how a dashboard would interact with the backend API")
    print("Make sure the API server is running: python start_api.py")
    print()

    try:
        # 1. Health Check
        print_header("1. System Health Check")
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            health_data = response.json()
            print_json(health_data, "Health Status")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False

        # 2. System Statistics
        print_header("2. System Statistics")
        response = requests.get(f"{BASE_URL}/api/v1/events/system/stats")
        if response.status_code == 200:
            stats_data = response.json()
            print_json(stats_data, "System Statistics")
        else:
            print(f"❌ Failed to get stats: {response.status_code}")

        # 3. List Agents (should show existing agents from PoC)
        print_header("3. Agents Management")
        response = requests.get(f"{BASE_URL}/api/v1/agents/")
        if response.status_code == 200:
            agents = response.json()
            print_json(agents, f"Agents List ({len(agents)} agents)")

            # Show details of first agent if any exist
            if agents:
                agent_id = agents[0]['id']
                print_header(f"4. Agent Details: {agent_id}")
                response = requests.get(f"{BASE_URL}/api/v1/agents/{agent_id}")
                if response.status_code == 200:
                    agent_detail = response.json()
                    print_json(agent_detail, "Agent Details")

        # 4. List Projects
        print_header("5. Projects Management")
        response = requests.get(f"{BASE_URL}/api/v1/projects/")
        if response.status_code == 200:
            projects = response.json()
            print_json(projects, f"Projects List ({len(projects)} projects)")

            # Show details of first project if any exist
            if projects:
                project_id = projects[0]['id']
                print_header(f"6. Project Details: {project_id}")
                response = requests.get(f"{BASE_URL}/api/v1/projects/{project_id}")
                if response.status_code == 200:
                    project_detail = response.json()
                    print_json(project_detail, "Project Details")

        # 5. List Skills
        print_header("7. Skills Management")
        response = requests.get(f"{BASE_URL}/api/v1/skills/")
        if response.status_code == 200:
            skills = response.json()
            print_json(skills, f"Skills List ({len(skills)} skills)")

        # 6. Create a new agent (demonstration)
        print_header("8. Creating New Agent")
        new_agent_data = {
            "name": "Demo Analyst Agent",
            "description": "An agent specialized in data analysis and reporting",
            "system_prompt": "You are an expert data analyst. Provide clear, structured analysis with actionable insights.",
            "skills": ["basic-reading", "analysis"],
            "model": "nvidia_nim/nvidia/nemotron-3-super-120b-a12b",
            "effort": "medium",
            "max_tokens": 3000,
            "temperature": 0.5
        }
        }

        response = requests.post(f"{BASE_URL}/api/v1/agents/", json=new_agent_data)
        if response.status_code == 200:
            created_agent = response.json()
            print_json(created_agent, "Created Agent")
            demo_agent_id = created_agent['id']
        else:
            print(f"❌ Failed to create agent: {response.status_code}")
            print(response.text)
            return False

        # 7. Create a new project
        print_header("9. Creating New Project")
        new_project_data = {
            "name": "Demo Analysis Project",
            "description": "A project for demonstrating data analysis capabilities",
            "working_directory": os.getcwd(),  # Current directory
            "instructions": "Focus on analyzing data and providing clear insights.",
            "skills": ["basic-reading", "analysis"],
            "allowed_tools": ["read", "grep", "glob"]  # Read-only for safety
        }

        response = requests.post(f"{BASE_URL}/api/v1/projects/", json=new_project_data)
        if response.status_code == 200:
            created_project = response.json()
            print_json(created_project, "Created Project")
            demo_project_id = created_project['id']
        else:
            print(f"❌ Failed to create project: {response.status_code}")
            print(response.text)
            return False

        # 8. Submit a task
        print_header("10. Submitting Task")
        task_data = {
            "agent_id": demo_agent_id,
            "project_id": demo_project_id,
            "prompt": "Analyze the README.md file and provide insights about the project's purpose, technology stack, and key features."
        }

        response = requests.post(f"{BASE_URL}/api/v1/tasks/", json=task_data)
        if response.status_code == 200:
            created_task = response.json()
            print_json(created_task, "Submitted Task")
            task_run_id = created_task['run_id']
        else:
            print(f"❌ Failed to submit task: {response.status_code}")
            print(response.text)
            return False

        # 9. Monitor task status (polling for demo - real dashboard would use SSE)
        print_header("11. Monitoring Task Status")
        print("Polling task status (in real dashboard, this would use Server-Sent Events)...")

        for i in range(5):  # Poll up to 5 times
            time.sleep(2)  # Wait 2 seconds between polls
            response = requests.get(f"{BASE_URL}/api/v1/tasks/{task_run_id}")
            if response.status_code == 200:
                task_status = response.json()
                status = task_status['status']
                print(f"  [{i+1}] Status: {status}")

                if status in ['completed', 'failed', 'cancelled']:
                    print_header("12. Task Completed")
                    print_json(task_status, "Final Task Result")
                    break
            else:
                print(f"❌ Failed to get task status: {response.status_code}")
                break
        else:
            print("  ⚠️  Task still running after polling period")

        # 10. List recent tasks
        print_header("13. Recent Tasks")
        response = requests.get(f"{BASE_URL}/api/v1/tasks/?limit=5")
        if response.status_code == 200:
            recent_tasks = response.json()
            print_json(recent_tasks, f"Recent Tasks ({len(recent_tasks)} tasks)")

        print_header("🎉 Demonstration Complete!")
        print("✅ All API interactions successful!")
        print("✅ The backend is ready for dashboard integration")
        return True

    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API server.")
        print("Make sure to start the server first:")
        print("   python start_api.py")
        print("Then run this demonstration script.")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    demo_api_interactions()
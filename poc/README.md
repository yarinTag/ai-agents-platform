# AI Agents Platform - Proof of Concept

This is a proof of concept for a generic AI Agents Platform inspired by Agents Office and Free Claude Code.

## Project Purpose

The AI Agents Platform aims to provide a modular, extensible framework for building and managing AI agents that can execute tasks using various backends, with initial integration using Free Claude Code as the runtime.

## Main Technologies

- Python 3.x
- SQLite for persistence
- Free Claude Code (via subprocess management)
- JSON-based configuration for agents, projects, and skills

## Key Features

- Agent registration and management
- Project context isolation  
- Reusable skill system (markdown-based)
- Task execution with Free Claude Code runtime
- Streaming event capture and processing
- Execution state tracking (QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED)
- Result persistence and retrieval
- Process lifecycle management

## Components

1. **Config Manager** (`config.py`) - Handles agent, project, and skill configuration
2. **Persistence Layer** (`persistence.py`) - SQLite database for storing configuration and execution history
3. **Runtime Adapter** (`runtime_adapter.py`) - Manages Free Claude Code subprocesses and stream-json event parsing
4. **Demo PoC** (`demo_poc.py`) - Proof of concept demonstration

## Usage

See `demo_poc.py` for a complete demonstration of:
- Registering agents, projects, and skills
- Submitting read-only tasks
- Executing tasks through Free Claude Code
- Capturing streaming events
- Tracking execution state
- Persisting results

## Implementation Details

The platform uses Free Claude Code's managed session system by:
- Setting appropriate environment variables (ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN)
- Launching Claude Code subprocesses with `--output-format stream-json`
- Using `--add-dir` for working directory isolation
- Parsing structured events from stdout for monitoring
- Managing process lifecycle for task execution and cancellation

## Future Work

- MVC dashboard for agent/project/skill management
- Human approval workflows
- Advanced workflow orchestration (sequential, parallel, approval gates)
- MCP (Model Context Protocol) integration
- Additional tool adapters beyond Free Claude Code
- Enhanced security and access controls
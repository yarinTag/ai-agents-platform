#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Importing modules...")
from config import config_manager
print("✓ config_manager imported")

from persistence import db_manager
print("✓ db_manager imported")

from runtime_adapter import runtime_adapter
print("✓ runtime_adapter imported")

print("All imports successful!")
print("Testing basic functionality...")

# Test registering an agent
from config import AgentConfig
agent = AgentConfig(
    id="test-agent",
    name="Test Agent",
    description="A test agent",
    system_prompt="You are a test agent.",
    skills=["test"],
    model="nvidia_nim/nvidia/nemotron-3-super-120b-a12b"
)

config_manager.register_agent(agent)
print("✓ Agent registered")

retrieved = config_manager.get_agent("test-agent")
print(f"✓ Agent retrieved: {retrieved.name}")

print("Basic functionality test passed!")
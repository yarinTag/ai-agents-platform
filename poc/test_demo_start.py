#!/usr/bin/env python3
print("=== DEMO STARTING ===")
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Imports...")
from config import config_manager
print("✓ config_manager")

from persistence import db_manager
print("✓ db_manager")

from runtime_adapter import runtime_adapter
print("✓ runtime_adapter")

print("All imports successful!")

print("Calling setup_demo_data()...")
# Import the setup function from demo_poc
from demo_poc import setup_demo_data
setup_demo_data()
print("✓ setup_demo_data completed")

print("Demo start test completed!")
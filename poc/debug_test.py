#!/usr/bin/env python3
print("DEBUG: Script starting...")
import sys
print(f"DEBUG: Python path: {sys.path[:3]}...")

# Try importing
try:
    from config import config_manager
    print("DEBUG: Imported config_manager")
except Exception as e:
    print(f"DEBUG: Failed to import config_manager: {e}")
    import traceback
    traceback.print_exc()
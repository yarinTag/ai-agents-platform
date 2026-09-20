#!/usr/bin/env python3
"""
Explore Free Claude Code modules to understand how to use them for the PoC.
"""

import sys
import os

# Add the free-claude-code to Python path
fcc_path = r"C:\Users\taguo\AppData\Roaming\uv\tools\free-claude-code\Lib\site-packages"
if fcc_path not in sys.path:
    sys.path.insert(0, fcc_path)

print("Exploring Free Claude Code modules...")
print(f"Python path includes: {fcc_path}")

try:
    # Try to import the managed session modules
    import free_claude_code.cli.managed.session as session_module
    print("✓ Successfully imported session module")

    import free_claude_code.cli.managed.manager as manager_module
    print("✓ Successfully imported manager module")

    import free_claude_code.cli.managed.claude as claude_module
    print("✓ Successfully imported claude module")

    # Check what classes are available
    print("\nAvailable classes in session module:")
    for name in dir(session_module):
        if not name.startswith('_'):
            obj = getattr(session_module, name)
            if isinstance(obj, type):
                print(f"  - {name}")

    print("\nAvailable classes in manager module:")
    for name in dir(manager_module):
        if not name.startswith('_'):
            obj = getattr(manager_module, name)
            if isinstance(obj, type):
                print(f"  - {name}")

    # Try to understand the configuration needed
    print("\nExamining ManagedClaudeConfig:")
    config_class = getattr(session_module, 'ManagedClaudeConfig', None)
    if config_class:
        print(f"  Found: {config_class}")
        # Try to see init signature
        import inspect
        try:
            sig = inspect.signature(config_class.__init__)
            print(f"  Signature: {sig}")
        except Exception as e:
            print(f"  Could not get signature: {e}")

    print("\nExamining ManagedClaudeSession:")
    session_class = getattr(session_module, 'ManagedClaudeSession', None)
    if session_class:
        print(f"  Found: {session_class}")
        try:
            sig = inspect.signature(session_class.__init__)
            print(f"  Signature: {sig}")
        except Exception as e:
            print(f"  Could not get signature: {e}")

    print("\nExamining ManagedClaudeSessionManager:")
    manager_class = getattr(manager_module, 'ManagedClaudeSessionManager', None)
    if manager_class:
        print(f"  Found: {manager_class}")
        try:
            sig = inspect.signature(manager_class.__init__)
            print(f"  Signature: {sig}")
        except Exception as e:
            print(f"  Could not get signature: {e}")

except Exception as e:
    print(f"✗ Error importing modules: {e}")
    import traceback
    traceback.print_exc()

# Also check what environment variables or config is needed
print("\nChecking for .fcc directory and config:")
fcc_dir = r"C:\Users\taguo\.fcc"
if os.path.exists(fcc_dir):
    print(f"✓ Found .fcc directory: {fcc_dir}")
    env_file = os.path.join(fcc_dir, ".env")
    if os.path.exists(env_file):
        print(f"✓ Found .env file: {env_file}")
        # Don't read contents for security, just check existence
    else:
        print(f"✗ .env file not found")
else:
    print(f"✗ .fcc directory not found: {fcc_dir}")

print("\nExploration complete.")
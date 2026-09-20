#!/usr/bin/env python3
# Simple test to see if demo_poc.py has syntax errors
import ast
import sys

try:
    with open('demo_poc.py', 'r') as f:
        content = f.read()

    # Try to parse it
    tree = ast.parse(content)
    print("✓ demo_poc.py parses successfully")

    # Try to compile it
    code = compile(tree, 'demo_poc.py', 'exec')
    print("✓ demo_poc.py compiles successfully")

except SyntaxError as e:
    print(f"✗ Syntax error in demo_poc.py: {e}")
    print(f"   Line {e.lineno}: {e.text}")
except Exception as e:
    print(f"✗ Error checking demo_poc.py: {e}")
    import traceback
    traceback.print_exc()
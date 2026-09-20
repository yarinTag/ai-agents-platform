#!/usr/bin/env python3
# Check if demo_poc.py has the expected functions
import ast
import sys

with open('demo_poc.py', 'r') as f:
    content = f.read()

# Parse to see what functions are defined
tree = ast.parse(content)

functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
print("Functions defined in demo_poc.py:")
for func in functions:
    print(f"  - {func}")

# Also check if main function exists
if 'main' in functions:
    print("\n✓ main function found")
else:
    print("\n✗ main function NOT found")
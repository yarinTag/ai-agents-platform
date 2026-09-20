#!/usr/bin/env python3
# Show the last 20 lines of demo_poc.py
with open('demo_poc.py', 'r') as f:
    lines = f.readlines()

print("Last 20 lines of demo_poc.py:")
for i, line in enumerate(lines[-20:], len(lines)-19):
    print(f"{i:3d}: {line.rstrip()}")
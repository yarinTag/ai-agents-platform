#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


from demo_data import setup_demo_data

if __name__ == "__main__":
    setup_demo_data()
    print("Setup completed successfully!")
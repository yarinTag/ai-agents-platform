#!/usr/bin/env python3
"""
Script to start the AI Agents Platform API server.
"""

import uvicorn
import sys
import os

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)



def main():
    """Start the API server."""
    print("🚀 Starting AI Agents Platform API Server")
    print("📚 API Documentation: http://localhost:8000/docs")
    print("🔍 Alternative Docs: http://localhost:8000/redoc")
    print("💚 Health Check: http://localhost:8000/health")
    print("\nPress Ctrl+C to stop the server\n")

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[current_dir],
        app_dir=current_dir,
        env_file=os.path.join(os.path.dirname(current_dir), ".env")
        if os.path.isfile(os.path.join(os.path.dirname(current_dir), ".env")) else None,
        log_level="info"
    )


if __name__ == "__main__":
    main()
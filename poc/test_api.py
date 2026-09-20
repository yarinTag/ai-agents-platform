"""
Test script to verify the API can start and basic endpoints work.
"""

import sys
import os
import asyncio

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import httpx
from contextlib import asynccontextmanager

# Now we can import from backend
from backend.main import app


@asynccontextmanager
async def lifespan_test():
    """Test lifespan manager."""
    # Import and initialize services
    from backend.dependencies import init_services, shutdown_services
    await init_services()
    try:
        yield
    finally:
        await shutdown_services()


async def test_api_startup():
    """Test that the API application can be imported and initialized."""
    print("🧪 Testing API startup...")

    # Test lifespan
    async with lifespan_test():
        print("✅ Services initialized successfully")

        # Test that we can access the app
        assert app.title == "AI Agents Platform API"
        print("✅ FastAPI app configured correctly")

        # Test that routers are included
        assert len(app.routes) > 0
        print(f"✅ API has {len(app.routes)} routes registered")

    print("🎉 API startup test passed!")


async def test_api_endpoints():
    """Test API endpoints with a test client."""
    print("\n🧪 Testing API endpoints...")

    async with lifespan_test():
        # Create test client
        async with httpx.AsyncClient(app=app, base_url="http://test") as client:
            # Test root endpoint
            response = await client.get("/")
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert "AI Agents Platform API" in data["message"]
            print("✅ Root endpoint working")

            # Test health endpoint
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            print("✅ Health endpoint working")

            # Test agents endpoint (should return empty list initially)
            response = await client.get("/api/v1/agents/")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            print(f"✅ Agents endpoint working (found {len(data)} agents)")

            # Test projects endpoint
            response = await client.get("/api/v1/projects/")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            print(f"✅ Projects endpoint working (found {len(data)} projects)")

            # Test skills endpoint
            response = await client.get("/api/v1/skills/")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            print(f"✅ Skills endpoint working (found {len(data)} skills)")

            # Test stats endpoint
            response = await client.get("/api/v1/events/system/stats")
            assert response.status_code == 200
            data = response.json()
            assert "agents" in data
            assert "projects" in data
            assert "skills" in data
            assert "tasks" in data
            print("✅ System stats endpoint working")

    print("🎉 API endpoints test passed!")


async def main():
    """Run all tests."""
    print("🚀 Starting API tests...\n")

    try:
        await test_api_startup()
        await test_api_endpoints()
        print("\n🎉 All tests passed! The API foundation is working correctly.")
        return True
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
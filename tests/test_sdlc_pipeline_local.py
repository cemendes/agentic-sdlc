import os
import sys
import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ["LOCAL_DEV"] = "true"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

from test_pipeline_local import run_local_pipeline

@pytest.mark.asyncio
async def test_full_sdlc_pipeline_local():
    """Test full 5-agent SDLC pipeline locally in memory."""
    print("\n🧪 Running Pytest integration test for SCRUM-11...")
    await run_local_pipeline("SCRUM-11")
    assert True

if __name__ == "__main__":
    pytest.main(["-vs", __file__])

"""Root conftest — shared fixtures for all test categories."""
import json
import pytest
import pytest_asyncio
from pathlib import Path
from httpx import ASGITransport, AsyncClient

SEED_PATH = Path(__file__).parent.parent / "data" / "seeds" / "zarqa.json"


@pytest.fixture
def seed_data():
    """Load raw seed JSON."""
    return json.loads(SEED_PATH.read_text())


@pytest.fixture
def repos():
    """Get a fresh in-memory repo bundle seeded with Zarqa data."""
    from app.repositories.memory.seed_loader import load_seed
    from app.repositories.memory.bundle import MemoryBundle
    return MemoryBundle(load_seed(str(SEED_PATH)))


@pytest_asyncio.fixture
async def client():
    """Async HTTP client wired directly to the FastAPI app (no network).
    Manually seeds app.state.repos since ASGITransport doesn't run lifespan.
    """
    from app.main import create_app
    from app.repositories.factory import get_repos
    app = create_app()
    # Manually trigger what lifespan does
    app.state.repos = get_repos()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

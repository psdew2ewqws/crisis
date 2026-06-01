import json
import pytest
from app.engine.graph.store import CDG


@pytest.fixture
def seed():
    return json.load(open("data/seeds/zarqa.json"))


@pytest.fixture
def cdg(seed):
    return CDG.from_seed(seed["nodes"], seed["edges"])

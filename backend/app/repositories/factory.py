from app.core.config import get_settings


def get_repos():
    s = get_settings()
    if s.REPO_BACKEND == "memory":
        from app.repositories.memory.seed_loader import load_seed
        from app.repositories.memory.bundle import MemoryBundle
        return MemoryBundle(load_seed(s.SEED_PATH))
    if s.REPO_BACKEND == "postgres":
        raise NotImplementedError("DB deferred — implement repositories/postgres/*")
    raise ValueError(f"Unknown REPO_BACKEND: {s.REPO_BACKEND}")

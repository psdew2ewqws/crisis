"""Domain Pack registry — discover and load packs by key."""
from app.packs.base import DomainPack
from app.packs.water import WaterPack

_PACKS: dict[str, DomainPack] = {}


def _discover():
    global _PACKS
    _PACKS = {
        "water": WaterPack(),
    }


def get_pack(domain_key: str) -> DomainPack | None:
    if not _PACKS:
        _discover()
    return _PACKS.get(domain_key)


def list_packs() -> list[str]:
    if not _PACKS:
        _discover()
    return list(_PACKS.keys())

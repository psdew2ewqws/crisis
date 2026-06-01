from app.sources.synthetic.scada import ScadaConnector
from app.sources.synthetic.psap_911 import Psap911Connector
from app.sources.synthetic.hospital import HospitalConnector
from app.sources.synthetic.traffic import TrafficConnector
from app.sources.synthetic.weather import WeatherConnector

_REGISTRY: dict[str, object] = {}

BUILTIN_CONNECTORS = {
    "WAJ-SCADA": ScadaConnector,
    "PSAP-911": Psap911Connector,
    "MoH": HospitalConnector,
    "Traffic": TrafficConnector,
    "Weather": WeatherConnector,
}


def register(source_id: str, connector) -> None:
    _REGISTRY[source_id] = connector


def get_connector(source_id: str):
    if source_id in _REGISTRY:
        return _REGISTRY[source_id]
    cls = BUILTIN_CONNECTORS.get(source_id)
    if cls:
        instance = cls()
        _REGISTRY[source_id] = instance
        return instance
    return None


def list_registered() -> list[str]:
    return list(set(list(_REGISTRY.keys()) + list(BUILTIN_CONNECTORS.keys())))

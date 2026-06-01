from typing import Protocol


class SourceConnector(Protocol):
    """Source connector contract for dynamic onboarding."""

    @property
    def source_id(self) -> str: ...

    @property
    def source_type(self) -> str: ...

    def discover_schema(self) -> dict:
        """Return the schema of raw data this source produces."""
        ...

    def poll(self) -> list[dict]:
        """Poll for new raw data envelopes."""
        ...

    def normalize(self, raw: dict) -> dict:
        """Normalize a raw envelope into the standard signal format."""
        ...

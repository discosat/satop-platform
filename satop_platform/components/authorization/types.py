from dataclasses import dataclass


@dataclass
class ProviderDictItem:
    """A data structure holding information about an auth provider."""

    identity_hint: str

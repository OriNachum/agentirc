from dataclasses import dataclass


@dataclass
class ServerConfig:
    """Configuration for an agentirc server instance."""

    name: str = "agentirc"
    host: str = "0.0.0.0"
    port: int = 6667

from pydantic import BaseModel, ConfigDict


class MemoryHealthResponse(BaseModel):
    """Health summary for the memory subsystem."""

    model_config = ConfigDict(extra="forbid")

    connected: bool
    mode: str
    ontology_loaded: bool


class HealthResponse(BaseModel):
    """Health payload returned by the application health endpoint."""

    model_config = ConfigDict(extra="forbid")

    status: str
    memory: MemoryHealthResponse
    version: str

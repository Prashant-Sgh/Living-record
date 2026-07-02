from pydantic import BaseModel, ConfigDict


class StatusResponse(BaseModel):
    """Simple placeholder response used by the initial routers."""

    model_config = ConfigDict(extra="forbid")

    status: str

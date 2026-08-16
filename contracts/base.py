"""Common Pydantic behavior for public contracts."""

from pydantic import BaseModel, ConfigDict


class ContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        use_enum_values=True,
        allow_inf_nan=False,
    )

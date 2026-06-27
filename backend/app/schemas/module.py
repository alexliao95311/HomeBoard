from typing import Literal

from pydantic import BaseModel


class ModuleStatus(BaseModel):
    module: str
    status: Literal["planned", "active"]
    message: str

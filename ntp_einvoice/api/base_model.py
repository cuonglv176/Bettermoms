# customer error report for Odoo
import traceback
from typing import Any
from pydantic import BaseModel as _BaseModel, ValidationError

try:
    from odoo.exceptions import UserError
except (ModuleNotFoundError, ImportError) as e:
    class UserError(Exception):
        pass


class BaseModel(_BaseModel):
    def __init__(__pydantic_self__, **data: Any) -> None:
        try:
            super().__init__(**data)
        except ValidationError as e:
            raise UserError(
                f"""Response from server not wellformed to proceed, 
--- Detail Error ---
{traceback.format_exc()} 

--- Data Causing Error ---
{data}
"""
            ) from e

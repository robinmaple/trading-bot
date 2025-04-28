# core/config/spec.py
from typing import Type, Callable, Optional, Any
from pydantic import validate_arguments
from core.logger import logger

class ConfigSpec:
    """Self-validating configuration specification"""
    
    def __init__(
        self,
        type: Type = str,
        default: Any = None,
        validator: Optional[Callable[[Any], bool]] = None,
        description: str = ""
    ):
        self.type = type
        self.default = default
        self.validator = validator or (lambda x: True)
        self.description = description

    @validate_arguments
    def validate(self, value: Any) -> Any:
        """Convert and validate the value"""
        if value is None:
            logger.debug(f"Using default for config: {self.default}")
            return self.default
            
        try:
            # Special handling for bools
            if self.type == bool:
                converted = str(value).lower() in ('true', '1', 't')
            else:
                converted = self.type(value)
                
            if not self.validator(converted):
                raise ValueError(f"Validation failed for value: {value}")
                
            return converted
            
        except (ValueError, TypeError) as e:
            logger.warning(
                f"Config validation error (using default {self.default}): {str(e)}"
            )
            return self.default
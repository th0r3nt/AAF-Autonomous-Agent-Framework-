from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


# Класс для стандартизации результатов выполнения скиллов (инструментов)
class ToolResult(BaseModel):
    success: bool
    data: Any = Field(default=None, description="Сырые данные (dict, list, int и т.д.)")
    error: Optional[str] = Field(default=None, description="Технический трейсбек или код ошибки")
    llm_message: str = Field(default="", description="Отформатированный текст для контекста агента")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Служебная инфа")

    @classmethod
    def ok(cls, msg: str, data: Any = None, **kwargs):
        """Создание успешного результата."""
        return cls(success=True, llm_message=msg, data=data, metadata=kwargs)

    @classmethod
    def fail(cls, msg: str, error: str = None):
        """Создание результата с ошибкой."""
        return cls(success=False, llm_message=msg, error=error or msg)

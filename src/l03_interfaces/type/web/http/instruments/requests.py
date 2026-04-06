import json
import httpx
from typing import Optional, Dict, Any

from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.web.http.client import HTTPClient
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill

# Пытаемся импортировать парсер JSONPath
try:
    from jsonpath_ng import parse

    HAS_JSONPATH = True
except ImportError:
    HAS_JSONPATH = False
    system_logger.warning(
        "[HTTP Requests] Библиотека 'jsonpath-ng' не установлена. Фильтрация JSONPath будет недоступна."
    )


class HttpRequests(BaseInstrument):
    """Инструменты для выполнения HTTP-запросов к внешним API."""

    def __init__(self, http_client: HTTPClient):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry

        self.http = http_client.client

    @skill()
    async def send_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        form_data: Optional[Dict[str, Any]] = None,
        json_path_filter: Optional[str] = None,
    ) -> ToolResult:
        """
        Выполняет произвольный HTTP-запрос.
        Безопасно обрабатывает бинарные данные, форматирует JSON и защищает контекст LLM от переполнения.
        """
        method = method.upper()
        if method not in ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]:
            return ToolResult.fail(
                msg=f"Ошибка: Неподдерживаемый HTTP метод '{method}'",
                error="MethodNotAllowed",
            )

        system_logger.info(f"[HTTP Requests] Выполняется {method} запрос к {url}")

        try:
            response = await self.http.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_body,
                data=form_data,
            )

            status_code = response.status_code
            content_type = response.headers.get("content-type", "").lower()

            # Защита от бинарных файлов (картинки, pdf, архивы)
            binary_types = [
                "image/",
                "video/",
                "audio/",
                "application/pdf",
                "application/zip",
                "application/octet-stream",
            ]
            if any(bt in content_type for bt in binary_types):
                size_kb = len(response.content) / 1024
                msg = f"--- HTTP Response ---\nStatus: {status_code}\nContent-Type: {content_type}\nПолучен бинарный файл. Размер: {size_kb:.2f} KB.\nБинарные данные скрыты для защиты контекста."
                return ToolResult.ok(msg=msg, data={"status": status_code, "size_kb": size_kb})

            # Обработка JSON и фильтрация (если запрошена)
            resp_data = None
            if "application/json" in content_type:
                try:
                    resp_data = response.json()

                    # Если агент передал json_path_filter (например "$.users[*].name")
                    if json_path_filter and HAS_JSONPATH:
                        try:
                            jsonpath_expr = parse(json_path_filter)
                            matches = [match.value for match in jsonpath_expr.find(resp_data)]

                            # Если нашли только 1 совпадение - достаем его из массива для красоты
                            resp_data = matches if len(matches) != 1 else matches[0]
                            system_logger.debug(
                                f"[HTTP Requests] Применен фильтр JSONPath: {json_path_filter}"
                            )

                        except Exception as e:
                            return ToolResult.fail(
                                msg=f"Ошибка парсинга JSONPath '{json_path_filter}': {e}",
                                error=str(e),
                            )

                    elif json_path_filter and not HAS_JSONPATH:
                        system_logger.warning(
                            "[HTTP Requests] Агент запросил фильтр JSONPath, но библиотека не установлена."
                        )

                    # Форматируем обратно в строку
                    body_str = json.dumps(resp_data, ensure_ascii=False, indent=2)
                except json.JSONDecodeError:
                    # Если API обмануло и вернуло невалидный JSON
                    body_str = response.text
            else:
                body_str = response.text

            # Защита контекста LLM (обрезаем огромные ответы)
            max_length = 30000
            if len(body_str) > max_length:
                body_str = (
                    body_str[:max_length]
                    + f"\n\n...[ОТВЕТ ОБРЕЗАН: ПРЕВЫШЕН ЛИМИТ В {max_length} СИМВОЛОВ]..."
                )

            msg = f"--- HTTP Response ---\nStatus: {status_code}\nContent-Type: {content_type}\n--- Body ---\n{body_str}"
            return ToolResult.ok(msg=msg, data=resp_data if resp_data is not None else body_str)

        except httpx.TimeoutException:
            system_logger.warning(f"[HTTP Requests] Таймаут запроса к {url}")
            return ToolResult.fail(
                msg=f"Ошибка: Превышено время ожидания (таймаут) при запросе к {url}.",
                error="TimeoutException",
            )

        except httpx.RequestError as e:
            system_logger.error(f"[HTTP Requests] Ошибка сети при запросе к {url}: {e}")
            return ToolResult.fail(msg=f"Ошибка сети при выполнении запроса: {e}", error=str(e))

        except Exception as e:
            system_logger.error(f"[HTTP Requests] Непредвиденная ошибка: {e}")
            return ToolResult.fail(msg=f"Критическая ошибка при запросе: {e}", error=str(e))

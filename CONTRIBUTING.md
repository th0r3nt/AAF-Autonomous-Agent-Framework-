

# Руководство контрибьютора (Contributing to AAF)

Добро пожаловать в разработку **Autonomous Agent Framework (AAF)**! 🌌 
Мы рады любой помощи в развитии проекта: от исправления багов до создания новых инструментов (skills) для агентов.

Поскольку AAF - это тяжеловесный фреймворк со сложной архитектурой (EventBus, GraphRAG, Docker-in-Docker), добавление нового функционала требует соблюдения нескольких строгих, но логичных правил.

В этом гайде описано, **как правильно добавлять новые навыки (skills) для нейросети**, чтобы они автоматически подхватывались ядром и не ломали ReAct-циклы.

---

## 🛠 Как работают навыки в AAF?

Вам **не нужно** вручную писать огромные JSON-схемы для OpenAI API. В AAF встроена магия мета-программирования. За генерацию схем отвечает декоратор `@llm_skill` (находится в `src/layer03_brain/agent/skills/auto_schema.py`).

Он читает `inspect.signature` (аннотации типов) вашей функции и сам собирает правильный payload для LLM.

### Шаг 1. Создание логики навыка

Навыки группируются по смыслу в папке `src/layer03_brain/agent/skills/`. 
Вы можете добавить свою функцию в существующий файл (например, `web/logic.py` или `pc/logic.py`), либо создать свою папку с файлом `logic.py`.

**Правила написания функции:**
1. **Аннотация типов обязательна.** Фреймворк использует типы (`str`, `int`, `list`, `bool`) для построения схемы. Если тип не указан, он примет его за `string`.
2. **Асинхронность в приоритете.** Старайтесь использовать `async def`. Если вы используете блокирующую синхронную функцию (`def`), движок `BrainEngine` автоматически обернет её в `asyncio.to_thread`, чтобы не застопить весь Event Loop, но лучше сразу писать асинхронный код.
3. **Возвращаемый тип.** Функция должна возвращать `str` (или `dict`). Не возвращайте сложные объекты - LLM должна получить текстовый ответ (результат выполнения), чтобы продолжить ReAct-цикл.

### Шаг 2. Обертка в декоратор `@llm_skill`

Импортируйте декоратор и опишите функцию. Описание (`description`) - это то, что увидит LLM. Чем оно точнее, тем умнее агент будет использовать инструмент.

```python
import asyncio
from src.layer03_brain.agent.skills.auto_schema import llm_skill
from src.layer00_utils.logger import system_logger

@llm_skill(
    description="Выполняет пинг указанного IP-адреса и возвращает статус доступности.",
    parameters={
        "ip_address": "IP-адрес или домен (например, '8.8.8.8' или 'google.com').",
        "count": {"description": "Количество пакетов.", "enum": [1, 3, 5]} # Можно строго ограничить выбор LLM
    }
)
async def ping_network_host(ip_address: str, count: int = 3) -> str:
    system_logger.info(f"[Network Tool] Выполняю пинг {ip_address}")
    
    try:
        # Пример выполнения консольной команды
        process = await asyncio.create_subprocess_shell(
            f"ping -c {count} {ip_address}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            return f"Пинг успешен:\n{stdout.decode('utf-8')}"
        else:
            return f"Хост недоступен:\n{stderr.decode('utf-8')}"
            
    except Exception as e:
        # ВАЖНО: Возвращайте ошибки как текст, а не через `raise Exception`.
        # LLM должна прочитать текст ошибки, чтобы понять, что пошло не так, и исправить аргументы в следующем цикле.
        return f"Критическая ошибка при выполнении пинга: {e}"
```

### Шаг 3. Регистрация нового модуля

Если вы добавили функцию в уже существующий файл (например, `web/logic.py`), делать больше ничего не нужно. Декоратор `@llm_skill` сам при импорте добавит вашу функцию в глобальный реестр инструментов.

Если вы создали **новый файл** (например, `src/layer03_brain/agent/skills/network/logic.py`), его необходимо импортировать в реестр, чтобы декораторы сработали при старте системы.

Откройте файл `src/layer03_brain/agent/skills/registry.py` и добавьте свой модуль в список импортов:

```python
# src/layer03_brain/agent/skills/registry.py

from src.layer03_brain.agent.skills.auto_schema import global_skills_registry, global_openai_tools

import src.layer03_brain.agent.skills.web.logic
import src.layer03_brain.agent.skills.system.logic
# ...
import src.layer03_brain.agent.skills.network.logic  # <-- ВАШ НОВЫЙ МОДУЛЬ

openai_tools = global_openai_tools
skills_registry = global_skills_registry
```

---

## 🛡️ Правила безопасности

1. **Не ломайте песочницу (Sandbox):**
   Если ваш инструмент читает или пишет файлы по запросу агента, ВСЕГДА используйте `workspace_manager`. У агентов нет доступа к корню вашего хоста.
   
   ```python
   from src.layer00_utils.workspace import workspace_manager
   
   # Правильно (защита от path traversal включена под капотом):
   filepath = workspace_manager.get_sandbox_file(filename) 
   ```

2. **Не используйте `print()`:**
   AAF - это асинхронный микросервисный организм. Для вывода информации в консоль используйте единый Color-логгер проекта.
   
   ```python
   from src.layer00_utils.logger import system_logger
   system_logger.debug("Текст только для дебага")
   system_logger.info("[Название_Модуля] Что-то произошло")
   system_logger.error("Все сломалось")
   ```

3. **Не используйте `raise` внутри инструментов LLM:**
   Если выкинуть `Exception` из функции инструмента, он просто отвалится, а ReAct цикл сломается. Перехватывайте ошибки через `try/except` и возвращайте их в виде строки `return f"Ошибка: {e}"`. Движок передаст эту строку обратно в нейросеть, и та попробует исправить свои галлюцинации самостоятельно (Self-Healing).

# Испортируем сами функции + их схемы

from src.layer03_brain.agent.skills.web.logic import WEB_REGISTRY
from src.layer03_brain.agent.skills.web.schemas import WEB_SCHEMAS

from src.layer03_brain.agent.skills.system.logic import SYSTEM_REGISTRY
from src.layer03_brain.agent.skills.system.schemas import SYSTEM_SCHEMAS

from src.layer03_brain.agent.skills.swarm.logic import SWARM_REGISTRY
from src.layer03_brain.agent.skills.swarm.schemas import SWARM_SCHEMAS

from src.layer03_brain.agent.skills.sandbox.logic import SANDBOX_REGISTRY
from src.layer03_brain.agent.skills.sandbox.schemas import SANDBOX_SCHEMAS

from src.layer03_brain.agent.skills.memory.logic import MEMORY_REGISTRY
from src.layer03_brain.agent.skills.memory.schemas import MEMORY_SCHEMAS

from src.layer03_brain.agent.skills.pc.logic import PC_REGISTRY
from src.layer03_brain.agent.skills.pc.schemas import PC_SCHEMAS

from src.layer03_brain.agent.skills.telegram.logic import TELEGRAM_REGISTRY
from src.layer03_brain.agent.skills.telegram.schemas import TELEGRAM_SCHEMAS

# т.к. я изначально писал фреймворк под библиотеку от Google, все схемы написаны под стандарт google.genai
# Сейчас используется openai, поэтому этот скрипт автоматически подгоняет их под стандарт openai, а не google.genai
def _wrap_tool(schema):
    return {
        "type": "function",
        "function": schema
    }

raw_schemas = []
raw_schemas.extend(WEB_SCHEMAS)
raw_schemas.extend(SYSTEM_SCHEMAS)
raw_schemas.extend(SWARM_SCHEMAS)
raw_schemas.extend(SANDBOX_SCHEMAS)
raw_schemas.extend(MEMORY_SCHEMAS)
raw_schemas.extend(PC_SCHEMAS)
raw_schemas.extend(TELEGRAM_SCHEMAS)

# Здесь описаны схемы функций, которые может вызывать LLM
openai_tools = [_wrap_tool(schema) for schema in raw_schemas]

# Здесь описано, какой именно скрипт запускать (в зависимости от "name": "func_name" в схеме функции)
skills_registry = {}
skills_registry.update(WEB_REGISTRY)
skills_registry.update(SYSTEM_REGISTRY)
skills_registry.update(SWARM_REGISTRY)
skills_registry.update(SANDBOX_REGISTRY)
skills_registry.update(MEMORY_REGISTRY)
skills_registry.update(PC_REGISTRY)
skills_registry.update(TELEGRAM_REGISTRY)
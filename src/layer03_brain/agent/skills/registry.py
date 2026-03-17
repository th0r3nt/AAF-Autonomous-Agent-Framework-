# Файл: src/layer03_brain/agent/skills/registry.py

from src.layer03_brain.agent.skills.auto_schema import (
    global_l2_registry, 
    global_openai_tools, 
    global_l0_manifest, 
    global_l1_docs
)

# Импортируем модули логики
# При импорте срабатывают декораторы @llm_skill и сами автоматически заполняют списки выше
import src.layer03_brain.agent.skills.web.logic
import src.layer03_brain.agent.skills.system.logic
import src.layer03_brain.agent.skills.swarm.logic
import src.layer03_brain.agent.skills.sandbox.logic
import src.layer03_brain.agent.skills.memory.logic
import src.layer03_brain.agent.skills.pc.logic
import src.layer03_brain.agent.skills.telegram.logic  # noqa: F401

from src.layer03_brain.agent.skills.plugins_loader import load_custom_plugins
# Подгружаем кастомные плагины (они сольются с системными списками)
load_custom_plugins()

# Экспортируем готовые списки
openai_tools = global_openai_tools
skills_registry = global_l2_registry # Теперь здесь ключи в формате aaf://...
l0_manifest = global_l0_manifest
l1_docs = global_l1_docs
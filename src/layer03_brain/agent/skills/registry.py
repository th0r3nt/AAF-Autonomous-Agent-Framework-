from src.layer03_brain.agent.skills.auto_schema import global_skills_registry, global_openai_tools

# Импортируем модули логики. 
# При импорте срабатывают декораторы @llm_skill и сами автоматически заполняют списки выше.
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

# Экспортируем готовые списки для движка engine.py и react.py
openai_tools = global_openai_tools
skills_registry = global_skills_registry
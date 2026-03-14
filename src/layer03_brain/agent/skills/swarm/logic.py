
async def spawn_subagent(role: str, name: str, instructions: str, trigger_condition: str = None, interval_sec: int = None) -> str:
    """Обертка: создает субагента через SwarmManager"""
    from src.layer04_swarm.manager import swarm_manager
    return await swarm_manager.spawn_subagent(role, name, instructions, trigger_condition, interval_sec)

async def kill_subagent(name: str) -> str:
    """Обертка: убивает процесс субагента"""
    from src.layer04_swarm.manager import swarm_manager
    return await swarm_manager.kill_subagent(name)

async def update_subagent(name: str, instructions: str = None, trigger_condition: str = None, interval_sec: int = None) -> str:
    """Обертка: горячее обновление субагента"""
    from src.layer04_swarm.manager import swarm_manager
    return await swarm_manager.update_subagent(name, instructions, trigger_condition, interval_sec)

SWARM_REGISTRY = {
    "spawn_subagent": spawn_subagent,
    "kill_subagent": kill_subagent,
    "update_subagent": update_subagent,
}
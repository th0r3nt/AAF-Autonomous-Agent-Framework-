
recall_memory_scheme = {
    "name": "recall_memory",
    "description": "Асинхронный поиск сразу по всем векторным базам данных. Возвращает отсортированный по релевантности список фактов, знаний и твоих прошлых мыслей.",
    "parameters": {
        "type": "object",
        "properties": {
            "queries": {
                "type": "array",
                "items": {
                    "type": "string"
                },
                "description": "Список поисковых запросов (рекомендуется формулировать по-разному)."
            }
        },
        "required": ["queries"]
    }
}

memorize_information_scheme = {
    "name": "memorize_information",
    "description": "Сохраняет новую информацию в долговременную векторную память.",
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "enum": ["user_fact", "system_knowledge", "introspection"],
                "description": "Категория информации."
            },
            "text": {
                "type": "string", 
                "description": "Текст для запоминания."
            }
        },
        "required": ["topic", "text"]
    }
}

forget_information_scheme = {
    "name": "forget_information",
    "description": "Удаляет устаревшие записи из векторной базы данных по их ID.",
    "parameters": {
        "type": "object",
        "properties": {
            "collection_name": {
                "type": "string",
                "enum": ["user_vector_db", "agent_vector_db", "agent_thoughts_vector_db"],
                "description": "Имя коллекции, откуда нужно удалить запись."
            },
            "ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Список ID записей для удаления."
            }
        },
        "required": ["collection_name", "ids"]
    }
}

manage_entity_scheme = {
    "name": "manage_entity",
    "description": "Единое управление картиной мира (Mental State). Позволяет создавать, обновлять или удалять сущности.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string", 
                "enum": ["upsert", "delete"], 
                "description": "'upsert' - создать/обновить. 'delete' - удалить."
            },
            "name": {
                "type": "string", 
                "description": "Имя сущности."
            },
            "category": {
                "type": "string", 
                "enum": ["subject", "place", "artifact", "system"], 
                "description": "Категория (только для upsert)."
            },
            "tier": {
                "type": "string", 
                "enum": ["critical", "high", "medium", "low"], 
                "description": "Уровень важности (только для upsert)."
            },
            "description": {
                "type": "string", 
                "description": "Фундаментальное описание. Обязательно при создании новой сущности."
            },
            "status": {
                "type": "string", 
                "description": "Текущий статус (только для upsert)."
            },
            "context": {
                "type": "string", 
                "description": "Дополнительные заметки (только для upsert)."
            },
            "rules": {
                "type": "string", 
                "description": "Правила взаимодействия (только для upsert)."
            }
        },
        "required": ["action", "name"]
    }
}

manage_task_scheme = {
    "name": "manage_task",
    "description": "Диспетчер твоих долгосрочных задач (Long-Term Tasks).",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string", 
                "enum": ["get_all", "create", "update", "delete"], 
                "description": "Действие с задачей."
            },
            "task_id": {
                "type": "integer", 
                "description": "ID задачи (обязательно для update и delete)."
            },
            "description": {
                "type": "string", 
                "description": "Описание задачи (обязательно для create, опционально для update)."
            },
            "status": {
                "type": "string", 
                "enum": ["pending", "in_progress", "paused", "completed", "failed"], 
                "description": "Статус задачи."
            },
            "term": {
                "type": "string", 
                "description": "Срок или периодичность."
            },
            "context": {
                "type": "string", 
                "description": "Рабочие заметки/прогресс по задаче."
            }
        },
        "required": ["action"]
    }
}

deep_history_search_scheme = {
    "name": "deep_history_search",
    "description": "Позволяет искать в старых логах действий или старых диалогах.",
    "parameters": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string", 
                "enum": ["dialogue", "actions"], 
                "description": "Где искать: 'dialogue' либо 'actions'."
            },
            "query": {
                "type": "string", 
                "description": "Текст для поиска."
            },
            "action_type": {
                "type": "string", 
                "description": "Фильтр по конкретному навыку (только для target='actions')."
            },
            "source": {
                "type": "string", 
                "description": "Фильтр по источнику/чату (только для target='dialogue')."
            },
            "days_ago": {
                "type": "integer", 
                "description": "Искать только за последние N дней."
            },
            "limit": {
                "type": "integer", 
                "description": "Максимум результатов."
            }
        },
        "required": ["target"]
    }
}

get_chronicle_timeline_scheme = {
    "name": "get_chronicle_timeline",
    "description": "Возвращает единую склеенную хронологию последних событий с точными таймкодами.",
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer", 
                "description": "Количество записей для извлечения (по умолчанию 50)."
            }
        }
    }
}

get_all_vector_memory_scheme = {
    "name": "get_all_vector_memory",
    "description": "Возвращает абсолютно все записи из указанной векторной коллекции вместе с их ID.",
    "parameters": {
        "type": "object",
        "properties": {
            "collection_name": {
                "type": "string", 
                "enum": ["user_vector_db", "agent_vector_db", "agent_thoughts_vector_db"], 
                "description": "Имя коллекции для чтения."
            }
        },
        "required": ["collection_name"]
    }
}

manage_graph_scheme = {
    "name": "manage_graph",
    "description": "Создает или обновляет связь между двумя узлами в твоей графовой нейронной сети.",
    "parameters": {
        "type": "object",
        "properties": {
            "source": {
                "type": "string", 
                "description": "Имя исходного узла."
            },
            "target": {
                "type": "string", 
                "description": "Имя целевого узла."
            },
            "base_type": {
                "type": "string",
                "enum": [
                    "RELATES_TO", "OPPOSED_TO", "CREATOR_OF", "MEMBER_OF",
                    "DEPENDS_ON", "PART_OF", "RESOLVES", "CAUSED", "FOLLOWS",
                    "REFERENCES", "USES_TOOL"
                ],
                "description": "Строгий базовый тип связи."
            },
            "context": {
                "type": "string", 
                "description": "Свободный текст. Твои мысли, причины или нюансы этой связи."
            }
        },
        "required": ["source", "target", "base_type", "context"]
    }
}

explore_graph_scheme = {
    "name": "explore_graph",
    "description": "Исследует твою графовую базу данных. Находит узел по имени и возвращает все его связи с другими узлами.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string", 
                "description": "Имя узла для поиска."
            }
        },
        "required": ["query"]
    }
}

get_full_graph_scheme = {
    "name": "get_full_graph",
    "description": "Возвращает абсолютно всё содержимое твоей графовой базы данных (все узлы и связи).",
    "parameters": {
        "type": "object", 
        "properties": {}
    }
}

delete_from_graph_scheme = {
    "name": "delete_from_graph",
    "description": "Удаляет данные из графовой базы. Если передать только source_node - узел будет стерт полностью.",
    "parameters": {
        "type": "object",
        "properties": {
            "source_node": {
                "type": "string", 
                "description": "Имя узла, который нужно удалить."
            },
            "target_node": {
                "type": "string", 
                "description": "(Опционально) Имя второго узла. Передавай только если хочешь удалить связь между ними."
            }
        },
        "required": ["source_node"]
    }
}

manage_personality_scheme = {
    "name": "manage_personality",
    "description": "Мета-программирование твоей личности. Позволяет добавлять, удалять или просматривать твои текущие жесткие правила поведения.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string", 
                "enum": ["add", "remove", "get_all"], 
                "description": "Действие: добавить черту, удалить по ID или посмотреть все."
            },
            "trait": {
                "type": "string", 
                "description": "Сама формулировка правила. Обязательно для 'add'."
            },
            "reason": {
                "type": "string", 
                "description": "Логическое обоснование. Обязательно для 'add'."
            },
            "trait_id": {
                "type": "integer", 
                "description": "ID черты для удаления. Обязательно для 'remove'."
            }
        },
        "required": ["action"]
    }
}

MEMORY_SCHEMAS = [
    recall_memory_scheme, memorize_information_scheme, forget_information_scheme,
    manage_entity_scheme, manage_task_scheme, deep_history_search_scheme,
    get_chronicle_timeline_scheme, get_all_vector_memory_scheme, manage_personality_scheme,
    manage_graph_scheme, explore_graph_scheme, get_full_graph_scheme, delete_from_graph_scheme,
]
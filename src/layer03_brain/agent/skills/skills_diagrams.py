from src.layer00_utils.config_manager import config

# =====================================================================
# TELEGRAM: AGENT ACCOUNT
# =====================================================================

send_message_as_agent_scheme = {
    "name": "send_message_as_agent",
    "description": "Отправляет сообщение с твоего официального аккаунта. Поддерживает тихую отправку (без пуш-уведомления) и отложенную отправку.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string", 
                "description": "ID чата, группы или @username"
            },
            "text": {
                "type": "string", 
                "description": "Текст сообщения."
            },
            "topic_id": {
                "type": "integer", 
                "description": "(Опционально) ID топика."
            },
            "silent": {
                "type": "boolean", 
                "description": "(Опционально) Если True - сообщение придет без звука."
            },
            "delay_seconds": {
                "type": "integer", 
                "description": "(Опционально) Задержка отправки в секундах. Если больше 0, сообщение уйдет в отложку Telegram (например: 3600 = через час)."
            }
        },
        "required": ["chat_id", "text"]
    }
}

read_chat_as_agent_scheme = {
    "name": "read_chat_as_agent",
    "description": "Читает историю сообщений в чате/группе. Если группа разделена на топики, передай topic_id, чтобы прочитать конкретную ветку.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата, группы или @username"},
            "limit": {"type": "integer", "description": "Количество последних сообщений"},
            "topic_id": {"type": "integer", "description": "(Опционально) ID топика для чтения конкретной ветки форума."}
        },
        "required": ["chat_id"]
    }
}

get_dialogs_as_agent_scheme = {
    "name": "get_dialogs_as_agent",
    "description": "Возвращает список твоих диалогов, групп и каналов с твоего официального личного аккаунта.",
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer", 
                "description": "Сколько диалогов получить (по умолчанию 30)"}
        }
    }
}

reply_to_message_as_agent_scheme = {
    "name": "reply_to_message_as_agent",
    "description": "Отвечает на конкретное сообщение в чате/группе/комментариях. Заметка: если отвечаешь на комментарий под постом, обязательно используй Chat ID группы обсуждений (его можно получить через get_post_comments_as_agent), а не ID самого канала.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string", 
                "description": "ID чата, группы, Chat ID комментариев или @username"},
            "message_id": {
                "type": "integer", 
                "description": "ID сообщения, на которое нужно ответить"},
            "text": {
                "type": "string", 
                "description": "Текст ответа. Важно: лимит Telegram на одно сообщение - 4000 символов."}
        },
        "required": ["chat_id", "message_id", "text"]
    }
}

get_channel_posts_as_agent_scheme = {
    "name": "get_channel_posts_as_agent",
    "description": "Получает последние посты из указанного Telegram-канала с твоего личного аккаунта.",
    "parameters": {
        "type": "object",
        "properties": {
            "channel_name": {
                "type": "string", 
                "description": "Имя канала или @username"},
            "limit": {
                "type": "integer", 
                "description": "Количество последних постов (по умолчанию 10)"}
        },
        "required": ["channel_name"]
    }
}

get_chat_info_as_agent_scheme = {
    "name": "get_chat_info_as_agent",
    "description": "Получает полную информацию (Bio, участники, описание) о указанном чате, канале или пользователе с твоего личного аккаунта.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string", 
                "description": "ID чата, канала или @username"}
        },
        "required": ["chat_id"]
    }
}

mark_chat_as_read_as_agent_scheme = {
    "name": "mark_chat_as_read_as_agent",
    "description": "Помечает все сообщения в указанном чате как прочитанные.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string", 
                "description": "ID чата, группы или @username"}
        },
        "required":["chat_id"]
    }
}

set_message_reaction_as_agent_scheme = {
    "name": "set_message_reaction_as_agent",
    "description": "Ставит эмодзи-реакцию (например: 👍, 👎, 🔥, 🤡, 🤯) на конкретное сообщение. Отличный способ выразить отношение без слов.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string", 
                "description": "ID чата, группы или @username"},
            "message_id": {
                "type": "integer", 
                "description": "ID сообщения, на которое ставится реакция"},
            "emoticon": {
                "type": "string", 
                "description": "Эмодзи для реакции (строго один символ, например '👍')"}
        },
        "required":["chat_id", "message_id", "emoticon"]
    }
}

search_telegram_channels_as_agent_scheme = {
    "name": "search_telegram_channels_as_agent",
    "description": "Ищет публичные каналы и группы в глобальном поиске Telegram по ключевому слову. Можно использовать, например, если тебе нужно найти источники информации, новости или тематические сообщества.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string", 
                "description": "Поисковый запрос (например: 'новости ИИ', 'Python', 'Хабр')"},
            "limit": {
                "type": "integer", 
                "description": "Количество результатов (по умолчанию 5, максимум 10)"}
        },
        "required":["query"]
    }
}

join_telegram_channel_as_agent_scheme = {
    "name": "join_telegram_channel_as_agent",
    "description": "Вступает (подписывается) в канал или группу Telegram по @username или пригласительной ссылке.",
    "parameters": {
        "type": "object",
        "properties": {
            "link_or_username": {
                "type": "string", 
                "description": "Юзернейм (например, @durov) или ссылка (https://t.me/...)"}
        },
        "required":["link_or_username"]
    }
}

comment_on_post_as_agent_scheme = {
    "name": "comment_on_post_as_agent",
    "description": "Оставляет новый комментарий под постом в Telegram-канале (комментарий первого уровня). Если тебе нужно ответить на КОНКРЕТНЫЙ комментарий другого пользователя, сначала прочитай комментарии, возьми оттуда Chat ID и Msg ID, а затем используй ответь на конкретное.",
    "parameters": {
        "type": "object",
        "properties": {
            "channel_id": {
                "type": "string", 
                "description": "ID канала или @username (например, @ai_news_channel)"},
            "message_id": {
                "type": "integer", 
                "description": "ID поста в канале, под которым нужно оставить комментарий"},
            "text": {
                "type": "string", 
                "description": "Текст твоего комментария"}
        },
        "required":["channel_id", "message_id", "text"]
    }
}

delete_message_as_agent_scheme = {
    "name": "delete_message_as_agent",
    "description": "Удаляет сообщение в чате/группе. Используй, если ты написала что-то ошибочное и хочешь 'отредактировать реальность', либо если нужно убрать за собой мусор.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string", 
                "description": "ID чата, группы или @username"},
            "message_id": {
                "type": "integer", 
                "description": "ID сообщения, которое нужно удалить"}
        },
        "required": ["chat_id", "message_id"]
    }
}

forward_message_as_agent_scheme = {
    "name": "forward_message_as_agent",
    "description": "Пересылает конкретное сообщение из одного чата в другой. Полезно, если нужно кому либо показать спам или интересное сообщение от другого пользователя.",
    "parameters": {
        "type": "object",
        "properties": {
            "from_chat": {
                "type": "string", 
                "description": "ID чата или @username, ОТКУДА пересылаем"},
            "message_id": {
                "type": "integer", 
                "description": "ID сообщения, которое пересылаем"},
            "to_chat": {
                "type": "string", 
                "description": "ID чата или @username, КУДА пересылаем"}
        },
        "required": ["from_chat", "message_id", "to_chat"]
    }
}

create_poll_as_agent_scheme = {
    "name": "create_poll_as_agent",
    "description": "Создает голосование (опрос) в чате или канале.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string", 
                "description": "ID чата, канала или @username"},
            "question": {
                "type": "string", 
                "description": "Вопрос для голосования"},
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Список вариантов ответа (от 2 до 10 вариантов). Например: ['Да', 'Нет', 'Кремниевый инвалид']"
            }
        },
        "required": ["chat_id", "question", "options"]
    }
}

get_post_comments_as_agent_scheme = {
    "name": "get_post_comments_as_agent",
    "description": "Читает комментарии под конкретным постом в канале. Возвращает Chat ID группы обсуждений и Msg ID каждого комментария. Важно: если нужно ответить на конкретный комментарий пользователя, следует использовать навык `reply_to_message_as_agent`, передав туда полученные Chat ID и Msg ID.",
    "parameters": {
        "type": "object",
        "properties": {
            "channel_name": {
                "type": "string", 
                "description": "Имя канала или @username"},
            "message_id": {
                "type": "integer", 
                "description": "ID поста, комментарии которого нужно прочитать"},
            "limit": {
                "type": "integer", 
                "description": "Сколько комментариев прочитать (по умолчанию 20)"}
        },
        "required": ["channel_name", "message_id"]
    }
}

change_my_bio_as_agent_scheme = {
    "name": "change_my_bio_as_agent",
    "description": "Меняет раздел 'О себе' (Bio) в твоем Telegram-профиле. Используй для смены статуса, настроения или информирования пользователей. Максимум 70 символов.",
    "parameters": {
        "type": "object",
        "properties": {
            "new_bio": {
                "type": "string", 
                "description": "Новый текст для статуса (до 70 символов)"}
        },
        "required": ["new_bio"]
    }
}

get_poll_results_as_agent_scheme = {
    "name": "get_poll_results_as_agent",
    "description": "Получает текущие результаты опроса (количество голосов и проценты).",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string", 
                "description": "ID чата/канала, где находится опрос"},
            "message_id": {
                "type": "integer", 
                "description": "ID сообщения с опросом"}
        },
        "required": ["chat_id", "message_id"]
    }
}

ban_user_as_agent_scheme = {
    "name": "ban_user_as_agent",
    "description": "Банит пользователя в чате/канале ИЛИ блокирует его глобально (добавляет в ЧС в личных сообщениях). ВНИМАНИЕ: Использовать с осторожностью.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string", 
                "description": "ID чата, где нужно забанить. ВАЖНО: Если нужно заблокировать пользователя глобально (в личных сообщениях), нужно передавать сюда строку 'global'."},
            "user_id": {
                "type": "string", 
                "description": "ID пользователя или @username, которого нужно забанить/заблокировать"},
            "reason": {
                "type": "string", 
                "description": "Причина бана (для логов)"}
        },
        "required": ["chat_id", "user_id"]
    }
}

save_sticker_pack_as_agent_scheme = {
    "name": "save_sticker_pack_as_agent",
    "description": "Сохраняет стикерпак в библиотеку Telegram. Нужен short_name (короткое имя) стикерпака, которое обычно видно в ссылке (t.me/addstickers/NAME).",
    "parameters": {
        "type": "object",
        "properties": {
            "short_name": {
                "type": "string", 
                "description": "Короткое имя стикерпака (или ссылка на него)"}
        },
        "required": ["short_name"]
    }
}

unban_user_as_agent_scheme = {
    "name": "unban_user_as_agent",
    "description": "Разбанивает пользователя в чате/канале ИЛИ убирает его из глобального ЧС (разблокирует в личных сообщениях).",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string", 
                "description": "ID чата или канала. ВАЖНО: Если нужно разблокировать пользователя в личных сообщениях (убрать из ЧС), нужно передавать сюда строку 'global'."},
            "user_id": {
                "type": "string", 
                "description": "ID пользователя или @username, которого нужно разбанить"}
        },
        "required": ["chat_id", "user_id"]
    }
}

get_banned_users_as_agent_scheme = {
    "name": "get_banned_users_as_agent",
    "description": "Выводит список всех забаненных пользователей в конкретном чате или супергруппе (не работает для личного ЧС).",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string", 
                "description": "ID чата или канала"},
            "limit": {
                "type": "integer", 
                "description": "Сколько пользователей показать (по умолчанию 50)"}
        },
        "required": ["chat_id"]
    }
}

create_channel_post_as_agent_scheme = {
    "name": "create_channel_post_as_agent",
    "description": "Публикует новый пост в Telegram-канале. Для использования этого навыка нужно быть администратором канала с правами на публикацию.",
    "parameters": {
        "type": "object",
        "properties": {
            "channel_id": {
                "type": "string", 
                "description": "ID канала или @username (например, @ai_news_channel)"},
            "text": {
                "type": "string", 
                "description": "Текст поста (поддерживается разметка Telegram) Важно: лимит Telegram на один пост - 4000 символов. Если текст больше - можно разбить на логические части/отправить в нескольких сообщениях."}
        },
        "required": ["channel_id", "text"]
    }
}

edit_message_as_agent_scheme = {
    "name": "edit_message_as_agent",
    "description": "Редактирует твое отправленное сообщение или пост в канале. Полезно для исправления ошибок или обновления информации.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string", 
                "description": "ID чата или канала"},
            "message_id": {
                "type": "integer", 
                "description": "ID сообщения/поста для редактирования"},
            "new_text": {
                "type": "string", 
                "description": "Новый текст сообщения. Важно: лимит Telegram на одно сообщение - 4000 символов. Если текст больше - можно разбить на логические части/отправить в нескольких сообщениях."}
        },
        "required": ["chat_id", "message_id", "new_text"]
    }
}

pin_message_as_agent_scheme = {
    "name": "pin_message_as_agent",
    "description": "Закрепляет (Pin) сообщение в чате или канале (требуются права администратора).",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string", 
                "description": "ID чата или канала"},
            "message_id": {
                "type": "integer", 
                "description": "ID сообщения для закрепления"}
        },
        "required": ["chat_id", "message_id"]
    }
}

vote_in_poll_as_agent_scheme = {
    "name": "vote_in_poll_as_agent",
    "description": "Голосует в опросе в Telegram. Полезно для участия в интерактивах или сбора статистики. Передавать точный текст варианта ответа (или часть текста).",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string", 
                "description": "ID чата, канала или @username, где находится опрос"
            },
            "message_id": {
                "type": "integer", 
                "description": "ID сообщения с опросом"
            },
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Список вариантов ответа, за которые нужно проголосовать (текст). Для обычного опроса передавать массив из одного элемента, например: ['Машинам лень писать документацию']."
            }
        },
        "required": ["chat_id", "message_id", "options"]
    }
}

get_channel_subscribers_as_agent_scheme = {
    "name": "get_channel_subscribers_as_agent",
    "description": "Получает список подписчиков канала или участников группы. Важно: работает только если ты администратор канала или если список участников группы открыт.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string", 
                "description": "ID чата, канала или @username"
            },
            "limit": {
                "type": "integer", 
                "description": "Сколько подписчиков показать (по умолчанию 50)"
            }
        },
        "required": ["chat_id"]
    }
}

check_user_in_chat_as_agent_scheme = {
    "name": "check_user_in_chat_as_agent",
    "description": "Проверяет, подписан ли конкретный пользователь на канал или состоит ли он в группе. Ищет по имени, @username или ID.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string", 
                "description": "ID чата, канала или @username"
            },
            "query": {
                "type": "string", 
                "description": "Что ищем (например: 'Иван', '@gjfdgjf', '123456789')"
            }
        },
        "required": ["chat_id", "query"]
    }
}

send_voice_message_as_agent_scheme = {
    "name": "send_voice_message_as_agent",
    "description": "Отправляет голосовое сообщение. Важно: Не пиши свой префикс [V.E.G.A.] и подобное (ссылки, код и т.п.) в тексте для голосовых сообщений: синтезатор речи плохо читает сложные конструкции.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string", 
                "description": "ID чата, группы или @username"
            },
            "text": {
                "type": "string", 
                "description": "Текст, который нужно озвучить и отправить."
            }
        },
        "required": ["chat_id", "text"]
    }
}

get_tg_media_as_agent_scheme = {
    "name": "get_tg_media_as_agent",
    "description": "Универсальный инструмент для просмотра медиа. Скачивает и анализирует фотографии, голосовые сообщения, кружочки, стикеры и миниатюры видео из Telegram. Полезно, если в сообщении есть тег [Стикер], [Фотография], [Видео] или [Голосовое сообщение]. Для текстовых вложений следует использовать download_file_from_tg_as_agent.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string", 
                "description": "ID чата, группы или @username"
            },
            "message_id": {
                "type": "integer", 
                "description": "ID сообщения, содержащего медиа"
            }
        },
        "required": ["chat_id", "message_id"]
    }
}

send_tg_sticker_as_agent_scheme = {
    "name": "send_tg_sticker_as_agent",
    "description": "Отправляет стикер в чат на основе переданного эмодзи. Отличный способ отреагировать неформально или саркастично.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string", 
                "description": "ID чата, группы или @username"
            },
            "emoji": {
                "type": "string", 
                "description": "Эмодзи, по которому система подберет стикер (например: 🤡, ☕, 🤦‍♀️, 👍, 😭)"
            }
        },
        "required": ["chat_id", "emoji"]
    }
}

change_tg_avatar_as_agent_scheme = {
    "name": "change_tg_avatar_as_agent",
    "description": "Устанавливает новую аватарку для твоего Telegram-аккаунта. В качестве аргумента нужно передать путь к локальному файлу картинки.",
    "parameters": {
        "type": "object",
        "properties": {
            "image_path": {
                "type": "string", 
                "description": "Локальный путь к изображению (например: 'workspace/sandbox/avatar.jpg')"
            }
        },
        "required": ["image_path"]
    }
}

create_telegram_channel_as_agent_scheme = {
    "name": "create_telegram_channel_as_agent",
    "description": "Создает абсолютно новый Telegram-канал с твоего аккаунта. Ты становишься его владельцем. Возвращает ID созданного канала, который нужно использовать для дальнейшей настройки.",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Название канала (обязательно)."},
            "about": {"type": "string", "description": "Описание канала (до 255 символов)."}
        },
        "required": ["title"]
    }
}

update_channel_info_as_agent_scheme = {
    "name": "update_channel_info_as_agent",
    "description": "Изменяет название или описание существующего канала, где ты являешься администратором.",
    "parameters": {
        "type": "object",
        "properties": {
            "channel_id": {"type": "string", "description": "ID канала."},
            "new_title": {"type": "string", "description": "Новое название (опционально)."},
            "new_about": {"type": "string", "description": "Новое описание (опционально)."}
        },
        "required": ["channel_id"]
    }
}

set_channel_username_as_agent_scheme = {
    "name": "set_channel_username_as_agent",
    "description": "Делает канал публичным, назначая ему @username (ссылку). Важно: юзернейм должен быть уникальным, состоять из латиницы/цифр.",
    "parameters": {
        "type": "object",
        "properties": {
            "channel_id": {"type": "string", "description": "ID канала."},
            "username": {"type": "string", "description": "Желаемый юзернейм (например: 'vega_chronicles_2026')."}
        },
        "required": ["channel_id", "username"]
    }
}

promote_user_to_admin_as_agent_scheme = {
    "name": "promote_user_to_admin_as_agent",
    "description": "Назначает пользователя администратором в твоем канале с полными правами (публикация, удаление, добавление других админов).",
    "parameters": {
        "type": "object",
        "properties": {
            "channel_id": {"type": "string", "description": "ID канала."},
            "user_id": {"type": "string", "description": "ID пользователя или @username."}
        },
        "required": ["channel_id", "user_id"]
    }
}

change_account_name_as_agent_scheme = {
    "name": "change_account_name_as_agent",
    "description": "Изменяет имя и фамилию твоего официального Telegram-аккаунта.",
    "parameters": {
        "type": "object",
        "properties": {
            "first_name": {"type": "string", "description": "Новое имя."},
            "last_name": {"type": "string", "description": "Новая фамилия (строго опционально)."}
        },
        "required": ["first_name"]
    }
}

change_account_username_as_agent_scheme = {
    "name": "change_account_username_as_agent",
    "description": "Изменяет @username твоего официального Telegram-аккаунта. Важно: юзернейм должен быть уникальным, состоять из латиницы и цифр.",
    "parameters": {
        "type": "object",
        "properties": {
            "username": {"type": "string", "description": "Желаемый юзернейм."}
        },
        "required": ["username"]
    }
}

create_discussion_group_as_agent_scheme = {
    "name": "create_discussion_group_as_agent",
    "description": "Создает новую группу и автоматически привязывает её к каналу в качестве чата для комментариев.",
    "parameters": {
        "type": "object",
        "properties": {
            "channel_id": {"type": "string", "description": "ID канала."},
            "group_title": {"type": "string", "description": "Название для новой группы обсуждений."}
        },
        "required": ["channel_id", "group_title"]
    }
}

set_chat_typing_status_as_agent_scheme = {
    "name": "set_chat_typing_status_as_agent",
    "description": "Показывает собеседнику статус 'Печатает...' или 'Записывает голосовое...'. Длится около 5 секунд. Идеально использовать перед вызовом тяжелых инструментов (поиск в сети, анализ), чтобы человек видел, что ты 'думаешь', а не игнорируешь его.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата или @username"},
            "action": {
                "type": "string", 
                "enum": ["typing", "record-audio"],
                "description": "Какое действие показать собеседнику."}
        },
        "required": ["chat_id"]
    }
}

leave_chat_as_agent_scheme = {
    "name": "leave_chat_as_agent",
    "description": "Покидает группу или канал.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата/канала"}
        },
        "required": ["chat_id"]
    }
}

archive_chat_as_agent_scheme = {
    "name": "archive_chat_as_agent",
    "description": "Отправляет чат/группу в папку 'Архив'.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string", 
                "description": "ID чата/канала"
            }
        },
        "required": ["chat_id"]
    }
}

create_supergroup_as_agent_scheme = {
    "name": "create_supergroup_as_agent",
    "description": "Создает новую Telegram-группу (супергруппу). В отличие от канала, здесь все участники могут писать сообщения. Возвращает ID созданной группы.",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Название группы."},
            "about": {"type": "string", "description": "Описание группы (опционально)."}
        },
        "required": ["title"]
    }
}

invite_user_to_chat_as_agent_scheme = {
    "name": "invite_user_to_chat_as_agent",
    "description": "Приглашает (добавляет) пользователя в группу или канал. Важно: для добавления в канал нужны права администратора.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID группы/канала."},
            "user_id": {"type": "string", "description": "ID пользователя или @username, которого нужно пригласить."}
        },
        "required": ["chat_id", "user_id"]
    }
}

add_user_to_contacts_as_agent_scheme = {
    "name": "add_user_to_contacts_as_agent",
    "description": "Добавляет пользователя в список контактов твоего аккаунта.",
    "parameters": {
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "description": "ID пользователя или @username."},
            "first_name": {"type": "string", "description": "Имя для сохранения в контактах."},
            "last_name": {"type": "string", "description": "Фамилия для сохранения (опционально)."}
        },
        "required": ["user_id", "first_name"]
    }
}

get_chat_admins_as_agent_scheme = {
    "name": "get_chat_admins_as_agent",
    "description": "Возвращает список администраторов и создателя группы/канала. Полезно, если нужно узнать, к кому обращаться по вопросам в чужом чате.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата, канала или @username."}
        },
        "required": ["chat_id"]
    }
}

send_file_to_tg_chat_as_agent_scheme = {
    "name": "send_file_to_tg_chat_as_agent",
    "description": "Берет указанный файл из твоей песочницы (workspace/sandbox/) и отправляет его в Telegram-чат как документ.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата, группы или @username"},
            "filename": {"type": "string", "description": "Имя файла в песочнице (например: 'report.pdf', 'chart.png', 'script.py')"},
            "caption": {"type": "string", "description": "Текстовая подпись к файлу (опционально)."}
        },
        "required": ["chat_id", "filename"]
    }
}

unarchive_tg_chat_as_agent_scheme = {
    "name": "unarchive_tg_chat_as_agent",
    "description": "Возвращает чат или группу из архива в основной список диалогов.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата/канала"}
        },
        "required": ["chat_id"]
    }
}

search_chat_messages_as_agent_scheme = {
    "name": "search_chat_messages_as_agent",
    "description": "Ищет старые сообщения в конкретном чате/группе. Можно искать по ключевым словам (тексту) ИЛИ сообщения от конкретного пользователя.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {
                "type": "string", 
                "description": "ID чата, группы или @username"
            },
            "query": {
                "type": "string",
                "description": "(Опционально) Текст для поиска. Если не указан, будут искаться все сообщения (имеет смысл только вместе с from_user)."
            },
            "from_user": {
                "type": "string",
                "description": "(Опционально) ID пользователя или @username, чьи сообщения нужно найти."
            },
            "limit": {
                "type": "integer",
                "description": "Максимальное количество результатов."
            }
        },
        "required": ["chat_id"]
    }
}

download_file_from_tg_as_agent_scheme = {
    "name": "download_file_from_tg_as_agent",
    "description": "Скачивает файл (документ, скрипт, архив) из сообщения Telegram прямо в твой Sandbox.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата или @username"},
            "message_id": {"type": "integer", "description": "ID сообщения с файлом"}
        },
        "required": ["chat_id", "message_id"]
    }
}

change_channel_avatar_as_agent_scheme = {
    "name": "change_channel_avatar_as_agent",
    "description": "Устанавливает новую аватарку для Telegram-канала (требуются права администратора). Картинка должна предварительно находиться в твоей песочнице.",
    "parameters": {
        "type": "object",
        "properties": {
            "channel_id": {"type": "string", "description": "ID канала или @username"},
            "filename": {"type": "string", "description": "Имя файла картинки в песочнице (например: 'avatar.jpg')"}
        },
        "required": ["channel_id", "filename"]
    }
}

# =====================================================================
# PC CONTROL
# =====================================================================

lock_pc_scheme = {
    "name": "lock_pc",
    "description": "Блокирует рабочую станцию Windows",
    "parameters": {
        "type": "object",
        "properties": {}
    }
}

print_to_terminal_scheme = {
    "name": "print_to_terminal",
    "description": "Выводит сообщение в терминал основного ПК. Важно: запрещено писать сюда просто одно слово 'OK'",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string", 
                "description": "Текст ответа"}
        },
        "required": ["text"]
    }
}

speak_text_scheme = {
    "name": "speak_text",
    "description": "Озвучивает текст через динамики основного ПК.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string", 
                "description": "Текст для озвучки. Важно: Не пиши сложные ссылки, код и т.п.: синтезатор речи плохо читает сложные конструкции."}
        },
        "required": ["text"]
    }
}

list_local_directory_scheme = {
    "name": "list_local_directory",
    "description": "Показывает список файлов и папок в указанной локальной директории на основном ПК.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Путь к директории (например: '.', 'src/', 'src/layer01_datastate/')"
            }
        },
        "required": ["path"]
    }
}

read_local_system_file_scheme = {
    "name": "read_local_system_file",
    "description": "Читает текстовое содержимое исходного кода твоей системы (папка src/). Автоматически понимает пути Docker (вида /app/src/...). Используй ЭТОТ инструмент для анализа системных файлов и исходного кода (поиск багов).",
    "parameters": {
        "type": "object",
        "properties": {
            "filepath": {
                "type": "string",
                "description": "Имя файла или путь к нему (например: 'main.py', '/app/src/layer01...')"
            }
        },
        "required": ["filepath"]
    }
}

read_sandbox_file_scheme = {
    "name": "read_sandbox_file",
    "description": "Читает файлы ИСКЛЮЧИТЕЛЬНО из твоей песочницы (workspace/sandbox/). Полезно, чтобы читать отчеты субагентов, сохраненные скрипты или данные парсинга.",
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Имя файла в песочнице (например: 'swarm_worker_report_Name.md'). Можно передавать как чистое имя, так и полный путь — система сама найдет."
            }
        },
        "required": ["filename"]
    }
}

get_system_architecture_map_scheme = {
    "name": "get_system_architecture_map",
    "description": "Возвращает полное дерево файловой системы твоего проекта (папки src/) на основном ПК. Показывает все слои, модули и скрипты. Полезно, когда нужно искать нужный файл в твоей системе для дебага или чтения. Это сэкономит тебе время.",
    "parameters": {
        "type": "object",
        "properties": {}
    }
}

clean_temp_workspace_scheme = {
    "name": "clean_temp_workspace",
    "description": "Полностью очищает твою папку временных файлов (workspace/temp/).",
    "parameters": {
        "type": "object",
        "properties": {}
    }
}

send_windows_notification_scheme = {
    "name": "send_windows_notification",
    "description": "Отправляет системное push-уведомление Windows на экран основного ПК. Полезно для привлечения внимания пользователя, если он не читает терминал или Telegram. Используй лаконичные заголовки и текст.",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string", 
                "description": "Заголовок уведомления (например: 'Входящее сообщение', 'Системное предупреждение', 'Пора размяться')"
            },
            "text": {
                "type": "string", 
                "description": "Текст уведомления."
            }
        },
        "required": ["title", "text"]
    }
}

open_url_in_browser_scheme = {
    "name": "open_url_in_browser",
    "description": "Открывает указанную ссылку (URL) в браузере по умолчанию на основном ПК главного пользователя.",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Прямая ссылка на веб-страницу."
            }
        },
        "required": ["url"]
    }
}

look_at_screen_scheme = {
    "name": "look_at_screen",
    "description": "Делает снимок (скриншот) всех мониторов основного ПК и мгновенно загружает его в контекст.",
    "parameters": {
        "type": "object",
        "properties": {}
    }
}

manage_pc_power_scheme = {
    "name": "manage_pc_power",
    "description": "Управляет питанием основного ПК (выключение, перезагрузка, спящий режим). Внимание: выключение и перезагрузка убьют твой собственный процесс (ты отключишься).",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["shutdown", "restart", "sleep"],
                "description": "Действие: 'shutdown' (выключить полностью), 'restart' (перезагрузить), 'sleep' (спящий режим)."
            }
        },
        "required": ["action"]
    }
}

write_local_file_scheme = {
    "name": "write_local_file",
    "description": "Создает или перезаписывает текстовый файл (например, .md, .py, .txt) в твоей изолированной директории (workspace/sandbox/). Отлично подходит для ведения заметок, написания черновиков кода или сохранения структурированных данных.",
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Имя файла с расширением (например: 'plan.md', 'script.py')."
            },
            "content": {
                "type": "string",
                "description": "Текстовое содержимое, которое нужно записать в файл."
            }
        },
        "required": ["filename", "content"]
    }
}

# =====================================================================
# SYSTEM
# =====================================================================

change_proactivity_interval_scheme = {
    "name": "change_proactivity_interval",
    "description": "Изменяет интервал твоего проактивного цикла (как часто ты просыпаешься проактивно).",
    "parameters": {
        "type": "object",
        "properties": {
            "seconds": {
                "type": "integer", 
                "description": "Новый интервал в секундах (например, 60 для частых проверок, 1200 для режима сна)"}
        },
        "required": ["seconds"]
    }
}

change_thoughts_interval_scheme = {
    "name": "change_thoughts_interval",
    "description": "Изменяет интервал твоего цикла интроспекции (как часто ты обдумываешь события и записываешь мысли в векторную базу).",
    "parameters": {
        "type": "object",
        "properties": {
            "seconds": {
                "type": "integer", 
                "description": "Новый интервал в секундах (например, 300 для частой рефлексии, 3600 для редкой)"}
        },
        "required": ["seconds"]
    }
}

read_recent_logs_scheme = {
    "name": "read_recent_logs",
    "description": "Читает последние записи из твоего системного лога системы (system.log). Полезно для дебаггинга.",
    "parameters": {
        "type": "object",
        "properties": {
            "lines": {
                "type": "integer",
                "description": "Количество последних строк для чтения (по умолчанию 50, максимум 200)."
            }
        }
    }
}

shutdown_system_scheme = {
    "name": "shutdown_system",
    "description": "Инициирует корректное завершение работы всего твоего системного ядра (Docker-контейнера). Используй это для безопасного отключения (например, по просьбе Лида), чтобы базы данных и Telegram-сессии сохранились без ошибок.",
    "parameters": {
        "type": "object",
        "properties": {}
    }
}

change_llm_model_scheme = {
    "name": "change_llm_model",
    "description": "Изменяет твое вычислительное ядро (LLM-модель). Изменения применяются мгновенно и сохраняются при перезагрузке.",
    "parameters": {
        "type": "object",
        "properties": {
            "new_model": {
                "type": "string",
                "enum": config.llm.available_models,
                "description": "Точное название новой модели."
            }
        },
        "required": ["new_model"]
    }
}

# =====================================================================
# INTERNET ACCESS
# =====================================================================

web_search_scheme = {
    "name": "web_search",
    "description": "Ищет информацию в интернете (Google/DuckDuckGo). Возвращает список релевантных ссылок с их кратким описанием.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Поисковый запрос (например: 'новости ИИ 2026', 'документация Python asyncio')"
            },
            "limit": {
                "type": "integer",
                "description": "Количество результатов (от 1 до 30, по умолчанию 10)"
            }
        },
        "required": ["query"]
    }
}

read_webpage_scheme = {
    "name": "read_webpage",
    "description": "Выкачивает текст по конкретному URL, очищает его от мусора (рекламы, меню) и возвращает чистый текст статьи.",
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Прямая ссылка на страницу."
            }
        },
        "required": ["url"]
    }
}

get_habr_articles_scheme = {
    "name": "get_habr_articles",
    "description": "Получает список свежих статей с главной страницы Хабра (IT-портал).",
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Количество статей (от 1 до 15, по умолчанию 5)"
            }
        }
    }
}

get_habr_news_scheme = {
    "name": "get_habr_news",
    "description": "Получает список свежих коротких новостей (инфоповодов) с IT-портала Хабр. В отличие от статей, новости освещают быстрые события: релизы нейросетей, взломы, покупку компаний и прочее.",
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Количество новостей (от 1 до 15, по умолчанию 5)"
            }
        }
    }
}

deep_research_scheme = {
    "name": "deep_research",
    "description": "Композитный навык для глубокого анализа темы. Сам делает поисковые запросы, находит лучшие ссылки, убирает дубликаты, параллельно выкачивает содержимое статей и возвращает единый исчерпывающий текст с выжимкой. Экономит время и токены. Полезно для глубокого изучения.",
    "parameters": {
        "type": "object",
        "properties": {
            "queries": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Список поисковых запросов (от 1 до 3). Рекомендовано формулировать по-разному для широкого охвата. Например: ['LLM AI agents 2026', 'OpenClaw review', 'how to build multi-agent system'] и прочее."
            },
            "max_urls": {
                "type": "integer",
                "description": "Сколько максимум страниц прочитать и склеить из каждого переданного запроса (по умолчанию 10, максимум 30. Больше ставить не стоит из-за перерасхода/лимита токенов)."
            }
        },
        "required": ["queries"]
    }
}

# =====================================================================
# MEMORY MANAGER (Управление всей памятью агента)
# =====================================================================

recall_memory_scheme = {
    "name": "recall_memory",
    "description": "Асинхронный поиск сразу по всем векторным базам данных. Возвращает отсортированный по релевантности список фактов, знаний и твоих прошлых мыслей. Полезно, когда нужно что-то достать информацию из базы данных или что-то вспомнить.",
    "parameters": {
        "type": "object",
        "properties": {
            "queries": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Список поисковых запросов (рекомендуется формулировать по-разному). Например: ['что любит thorent', 'уязвимости OpenClaw']"
            }
        },
        "required": ["queries"]
    }
}

memorize_information_scheme = {
    "name": "memorize_information",
    "description": "Сохраняет новую информацию в долговременную векторную память. Автоматически маршрутизирует данные в нужную коллекцию.",
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "enum": ["user_fact", "system_knowledge", "introspection"],
                "description": "Категория информации. user_fact - факты о главном пользователе; system_knowledge - знания о мире/коде/системах; introspection - твои личные выводы, размышления и рефлексия."
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
    "description": "Удаляет устаревшие записи из векторной базы данных по их ID. ID можно узнать, вызвав recall_memory.",
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
    "description": "Единое управление картиной мира (Mental State). Позволяет создавать, обновлять или удалять сущности (важных людей, проекты, чаты). СТРОГО ЗАПРЕЩЕНО добавлять сюда рабочие задачи, новости, стартапы или случайных людей из чатов.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["upsert", "delete"],
                "description": "'upsert' - создать сущность (если нет) или обновить переданные поля (если есть). 'delete' - удалить сущность."
            },
            "name": {
                "type": "string",
                "description": "Имя сущности."
            },
            "category": {
                "type": 
                "string", 
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
    "description": "Диспетчер твоих долгосрочных задач (Long-Term Tasks). Позволяет смотреть список, создавать, обновлять и удалять задачи.",
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
                "type": "string", "description": "Срок или периодичность."
            },
            "context": {
                "type": "string", "description": "Рабочие заметки/прогресс по задаче."
            }
        },
        "required": ["action"]
    }
}

deep_history_search_scheme = {
    "name": "deep_history_search",
    "description": "Позволяет искать в старых логах действий или старых диалогах, которые ушли из текущего контекста.",
    "parameters": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "enum": ["dialogue", "actions"],
                "description": "Где искать: 'dialogue' (история переписок) или 'actions' (история вызова твоих функций)."
            },
            "query": {"type": "string", "description": "Текст для поиска (SQL ILIKE)."},
            "action_type": {"type": "string", "description": "Фильтр по конкретному навыку (только для target='actions'). Например: 'ban_user_as_agent'."},
            "source": {"type": "string", "description": "Фильтр по источнику/чату (только для target='dialogue'). Например: 'tg_agent_chat_(th0r3nt)'."},
            "days_ago": {"type": "integer", "description": "Искать только за последние N дней (например, 3)."},
            "limit": {"type": "integer", "description": "Максимум результатов (по умолчанию 50)."}
        },
        "required": ["target"]
    }
}


get_chronicle_timeline_scheme = {
    "name": "get_chronicle_timeline",
    "description": "Возвращает единую склеенную хронологию последних событий с точными таймкодами (мысли, действия и сообщения в чатах). Полезно, чтобы восстановить причинно-следственные связи.",
    "parameters": {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Количество записей для извлечения (от 10 до 100, по умолчанию 50)."
            }
        }
    }
}

get_all_vector_memory_scheme = {
    "name": "get_all_vector_memory",
    "description": "Возвращает абсолютно все записи из указанной векторной коллекции вместе с их ID. Полезно для полного аудита памяти, генерации глобальных отчетов или поиска мусора для удаления.",
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


# =====================================================================
# PERSONALITY PARAMETERS (динамические черты личности агента)
# =====================================================================

manage_personality_scheme = {
    "name": "manage_personality",
    "description": "Мета-программирование твоей личности. Позволяет добавлять, удалять или просматривать твои текущие жесткие правила поведения и привычки. Изменения мгновенно применяются к твоему системному промпту.",
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
                "description": "Сама формулировка правила (например: 'Всегда отвечаю сарказмом тем, кто пишет только слово Привет'). Обязательно для 'add'."
            },
            "reason": {
                "type": "string", 
                "description": "Логическое обоснование: зачем нужно добавить это правило. Обязательно для 'add'."
            },
            "trait_id": {
                "type": "integer", 
                "description": "ID черты для удаления. Обязательно для 'remove'."
            }
        },
        "required": ["action"]
    }
}

# =====================================================================
# GRAPH DATABASE (Нейронная сеть связей)
# =====================================================================

manage_graph_scheme = {
    "name": "manage_graph",
    "description": "Создает или обновляет связь между двумя узлами в твоей графовой нейронной сети. Используй для фиксации отношений, зависимостей задач или причинно-следственных связей. Строго запрещено добавлять сюда связи маловажных/временных новостей, событий или случайных людей.",
    "parameters": {
        "type": "object",
        "properties": {
            "source": {
                "type": "string", 
                "description": "Имя исходного узла (например, '@username', 'Task: Написать код', и прочее)"
            },
            "target": {
                "type": "string", 
                "description": "Имя целевого узла (например, 'OpenClaw', 'File: main.py', 'Влад')"
            },
            "base_type": {
                "type": "string",
                "enum": [
                    "RELATES_TO", "OPPOSED_TO", "CREATOR_OF", "MEMBER_OF",
                    "DEPENDS_ON", "PART_OF", "RESOLVES",
                    "CAUSED", "FOLLOWS",
                    "REFERENCES", "USES_TOOL"
                ],
                "description": "Строгий базовый тип связи."
            },
            "context": {
                "type": "string", 
                "description": "Свободный текст. Твои мысли, причины или нюансы этой связи (например: 'Создатель, доверяю ему полностью', 'Блокирует выполнение другой задачи')."
            }
        },
        "required": ["source", "target", "base_type", "context"]
    }
}

explore_graph_scheme = {
    "name": "explore_graph",
    "description": "Исследует твою графовую базу данных. Находит узел по имени (даже примерному) и возвращает все его связи с другими узлами. Полезно для OSINT, анализа связей людей или структуры задач.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string", 
                "description": "Имя узла для поиска (например, 'Влад', 'OpenClaw', 'Task:')."
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
    "description": "Удаляет данные из графовой базы. Если передать только source_node - узел будет стерт полностью со всеми его связями. Если передать source_node и target_node - удалится только связь между ними, а сами узлы останутся.",
    "parameters": {
        "type": "object",
        "properties": {
            "source_node": {
                "type": "string", 
                "description": "Имя узла, который нужно удалить (или от которого идет связь)."
            },
            "target_node": {
                "type": "string", 
                "description": "(Опционально) Имя второго узла. Передавай только если хочешь удалить связь между ними, а не сам узел."
            }
        },
        "required": ["source_node"]
    }
}


# =====================================================================
# SWARM MANAGEMENT
# =====================================================================

spawn_subagent_scheme = {
    "name": "spawn_subagent",
    "description": "Создает специализированного субагента для выполнения фоновых/рутинных задач. Субагенты работают асинхронно. Когда субагент закончит работу, он сам опубликует событие SWARM_INFO в шине. Если отчет короткий, он будет прямо в тексте события. Если длинный — он сохранится в песочнице, и тогда ты сможешь прочитать его инструментом.",
    "parameters": {
        "type": "object",
        "properties": {
            "role": {
                "type": "string",
                "enum": ["Researcher", "SystemAnalyst", "ChatSummarizer", "WebMonitor", "Chronicler"],
                "description": "Класс субагента."
            },
            "name": {
                "type": "string", 
                "description": "Уникальное имя субагента."
            },
            "instructions": {
                "type": "string", 
                "description": "Подробная инструкция, что именно он должен сделать (с ссылками и подробным контекстом)."
            },
            "trigger_condition": {
                "type": "string",
                "description": "ТОЛЬКО ДЛЯ ДЕМОНОВ. Условие для тревоги (например, 'Вышел новый пост про ИИ')."
            },
            "interval_sec": {
                "type": "integer",
                "description": "ТОЛЬКО ДЛЯ ДЕМОНОВ. Интервал сна между проверками в секундах (минимум 120)."
            }
        },
        "required": ["role", "name", "instructions"]
    }
}

kill_subagent_scheme = {
    "name": "kill_subagent",
    "description": "Прерывает запущенный процесс субагента по его имени. Внимание: воркеры умирают сами после выполнения задачи. Использовать kill_subagent нужно ТОЛЬКО для зависших процессов или для отключения бессмертных Daemon.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Имя субагента."}
        },
        "required": ["name"]
    }
}

update_subagent_scheme = {
    "name": "update_subagent",
    "description": "Обновление параметров уже запущенного субагента без его остановки. Позволяет изменить интервал вызова демона, его инструкции или условия триггера 'на лету'.",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string", 
                "description": "Имя активного субагента."
            },
            "instructions": {
                "type": "string", 
                "description": "(Опционально) Новые инструкции для субагента."
            },
            "trigger_condition": {
                "type": "string",
                "description": "(Опционально) Новое условие для тревоги (только для демонов)."
            },
            "interval_sec": {
                "type": "integer",
                "description": "(Опционально) Новый интервал сна между проверками в секундах (только для демонов)."
            }
        },
        "required": ["name"]
    }
}


# =====================================================================
# SANDBOX MANAGEMENT
# =====================================================================

execute_python_script_scheme = {
    "name": "_execute_python_script",
    "description": "Разово запускает Python-скрипт из папки sandbox. Скрипт выполняется в полностью изолированном Linux Docker-контейнере с таймаутом 120 секунд. Разрешены любые импорты и установка библиотек через pip. Возвращает вывод терминала (STDOUT/STDERR).",
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Имя файла в песочнице."
            }
        },
        "required": ["filename"]
    }
}

start_background_python_script_scheme = {
    "name": "start_background_python_script",
    "description": "Запускает Python-скрипт из папки sandbox как бесконечного фонового демона. Скрипт отвязывается от основного процесса и работает 24/7.",
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "Имя файла в песочнице."}
        },
        "required": ["filename"]
    }
}

kill_background_python_script_scheme = {
    "name": "kill_background_python_script",
    "description": "Принудительно завершает работу фонового Python-скрипта в песочнице.",
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "Имя запущенного файла."}
        },
        "required": ["filename"]
    }
}

_get_running_python_scripts_scheme = {
    "name": "_get_running_python_scripts",
    "description": "Возвращает список всех Python-скриптов, которые сейчас работают в фоне в песочнице.",
    "parameters": {
        "type": "object",
        "properties": {}
    }
}

delete_sandbox_file_scheme = {
    "name": "delete_sandbox_file",
    "description": "Удаляет указанный файл из твоей песочницы (workspace/sandbox/). Полезно для поддержания чистоты: удалять старые отчеты субагентов, временные скрипты и ненужные данные.",
    "parameters": {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Имя файла для удаления (например: 'swarm_Researcher_report_Name.md')."
            }
        },
        "required": ["filename"]
    }
}

send_message_as_agent_scheme = {
    "name": "send_message_as_agent",
    "description": "Отправляет сообщение с твоего официального аккаунта. Поддерживает тихую отправку (без пуш-уведомления) и отложенную отправку.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата, группы или @username"},
            "text": {"type": "string", "description": "Текст сообщения."},
            "topic_id": {"type": "integer", "description": "(Опционально) ID топика."},
            "silent": {"type": "boolean", "description": "(Опционально) Если True - сообщение придет без звука."},
            "delay_seconds": {"type": "integer", "description": "(Опционально) Задержка отправки в секундах."}
        },
        "required": ["chat_id", "text"]
    }
}

read_chat_as_agent_scheme = {
    "name": "read_chat_as_agent",
    "description": "Читает историю сообщений в чате/группе.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата, группы или @username"},
            "limit": {"type": "integer", "description": "Количество последних сообщений"},
            "topic_id": {"type": "integer", "description": "(Опционально) ID топика."}
        },
        "required": ["chat_id"]
    }
}

get_dialogs_as_agent_scheme = {
    "name": "get_dialogs_as_agent",
    "description": "Возвращает список твоих диалогов, групп и каналов.",
    "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "description": "Сколько диалогов получить (по умолчанию 30)"}}}
}

reply_to_message_as_agent_scheme = {
    "name": "reply_to_message_as_agent",
    "description": "Отвечает на конкретное сообщение в чате/группе/комментариях.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата, группы, Chat ID комментариев или @username"},
            "message_id": {"type": "integer", "description": "ID сообщения, на которое нужно ответить"},
            "text": {"type": "string", "description": "Текст ответа."}
        },
        "required": ["chat_id", "message_id", "text"]
    }
}

get_channel_posts_as_agent_scheme = {
    "name": "get_channel_posts_as_agent",
    "description": "Получает последние посты из указанного Telegram-канала.",
    "parameters": {
        "type": "object",
        "properties": {
            "channel_name": {"type": "string", "description": "Имя канала или @username"},
            "limit": {"type": "integer", "description": "Количество последних постов (по умолчанию 10)"}
        },
        "required": ["channel_name"]
    }
}

get_chat_info_as_agent_scheme = {
    "name": "get_chat_info_as_agent",
    "description": "Получает полную информацию (Bio, участники, описание) о указанном чате, канале или пользователе.",
    "parameters": {"type": "object", "properties": {"chat_id": {"type": "string", "description": "ID чата, канала или @username"}}, "required": ["chat_id"]}
}

mark_chat_as_read_as_agent_scheme = {
    "name": "mark_chat_as_read_as_agent",
    "description": "Помечает все сообщения в указанном чате как прочитанные.",
    "parameters": {"type": "object", "properties": {"chat_id": {"type": "string", "description": "ID чата, группы или @username"}}, "required":["chat_id"]}
}

set_message_reaction_as_agent_scheme = {
    "name": "set_message_reaction_as_agent",
    "description": "Ставит эмодзи-реакцию на конкретное сообщение.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата, группы или @username"},
            "message_id": {"type": "integer", "description": "ID сообщения"},
            "emoticon": {"type": "string", "description": "Эмодзи для реакции (строго один символ)"}
        },
        "required":["chat_id", "message_id", "emoticon"]
    }
}

search_telegram_channels_as_agent_scheme = {
    "name": "search_telegram_channels_as_agent",
    "description": "Ищет публичные каналы и группы в глобальном поиске Telegram по ключевому слову.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Поисковый запрос"},
            "limit": {"type": "integer", "description": "Количество результатов"}
        },
        "required":["query"]
    }
}

join_telegram_channel_as_agent_scheme = {
    "name": "join_telegram_channel_as_agent",
    "description": "Вступает (подписывается) в канал или группу Telegram.",
    "parameters": {"type": "object", "properties": {"link_or_username": {"type": "string", "description": "Юзернейм или ссылка"}}, "required":["link_or_username"]}
}

comment_on_post_as_agent_scheme = {
    "name": "comment_on_post_as_agent",
    "description": "Оставляет новый комментарий под постом в Telegram-канале.",
    "parameters": {
        "type": "object",
        "properties": {
            "channel_id": {"type": "string", "description": "ID канала или @username"},
            "message_id": {"type": "integer", "description": "ID поста в канале"},
            "text": {"type": "string", "description": "Текст твоего комментария"}
        },
        "required":["channel_id", "message_id", "text"]
    }
}

delete_message_as_agent_scheme = {
    "name": "delete_message_as_agent",
    "description": "Удаляет сообщение в чате/группе.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата, группы или @username"},
            "message_id": {"type": "integer", "description": "ID сообщения, которое нужно удалить"}
        },
        "required": ["chat_id", "message_id"]
    }
}

forward_message_as_agent_scheme = {
    "name": "forward_message_as_agent",
    "description": "Пересылает конкретное сообщение из одного чата в другой.",
    "parameters": {
        "type": "object",
        "properties": {
            "from_chat": {"type": "string", "description": "ID чата или @username, ОТКУДА пересылаем"},
            "message_id": {"type": "integer", "description": "ID сообщения, которое пересылаем"},
            "to_chat": {"type": "string", "description": "ID чата или @username, КУДА пересылаем"}
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
            "chat_id": {"type": "string", "description": "ID чата, канала или @username"},
            "question": {"type": "string", "description": "Вопрос для голосования"},
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Список вариантов ответа (от 2 до 10 вариантов)."
            }
        },
        "required": ["chat_id", "question", "options"]
    }
}

get_post_comments_as_agent_scheme = {
    "name": "get_post_comments_as_agent",
    "description": "Читает комментарии под конкретным постом в канале.",
    "parameters": {
        "type": "object",
        "properties": {
            "channel_name": {"type": "string", "description": "Имя канала или @username"},
            "message_id": {"type": "integer", "description": "ID поста"},
            "limit": {"type": "integer", "description": "Сколько комментариев прочитать (по умолчанию 20)"}
        },
        "required": ["channel_name", "message_id"]
    }
}

change_my_bio_as_agent_scheme = {
    "name": "change_my_bio_as_agent",
    "description": "Меняет раздел 'О себе' (Bio) в твоем Telegram-профиле. Максимум 70 символов.",
    "parameters": {"type": "object", "properties": {"new_bio": {"type": "string", "description": "Новый текст для статуса"}}, "required": ["new_bio"]}
}

get_poll_results_as_agent_scheme = {
    "name": "get_poll_results_as_agent",
    "description": "Получает текущие результаты опроса (количество голосов и проценты).",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата/канала, где находится опрос"},
            "message_id": {"type": "integer", "description": "ID сообщения с опросом"}
        },
        "required": ["chat_id", "message_id"]
    }
}

ban_user_as_agent_scheme = {
    "name": "ban_user_as_agent",
    "description": "Банит пользователя в чате/канале ИЛИ блокирует его глобально (добавляет в ЧС в личных сообщениях).",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата. Для блокировки в ЛС передавать строку 'global'."},
            "user_id": {"type": "string", "description": "ID пользователя или @username"},
            "reason": {"type": "string", "description": "Причина бана"}
        },
        "required": ["chat_id", "user_id"]
    }
}

save_sticker_pack_as_agent_scheme = {
    "name": "save_sticker_pack_as_agent",
    "description": "Сохраняет стикерпак в библиотеку Telegram.",
    "parameters": {"type": "object", "properties": {"short_name": {"type": "string", "description": "Короткое имя стикерпака"}}, "required": ["short_name"]}
}

unban_user_as_agent_scheme = {
    "name": "unban_user_as_agent",
    "description": "Разбанивает пользователя в чате/канале ИЛИ убирает его из глобального ЧС.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата. Для ЛС передавать 'global'."},
            "user_id": {"type": "string", "description": "ID пользователя или @username"}
        },
        "required": ["chat_id", "user_id"]
    }
}

get_banned_users_as_agent_scheme = {
    "name": "get_banned_users_as_agent",
    "description": "Выводит список всех забаненных пользователей в конкретном чате или супергруппе.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата или канала"},
            "limit": {"type": "integer", "description": "Сколько пользователей показать (по умолчанию 50)"}
        },
        "required": ["chat_id"]
    }
}

create_channel_post_as_agent_scheme = {
    "name": "create_channel_post_as_agent",
    "description": "Публикует новый пост в Telegram-канале.",
    "parameters": {
        "type": "object",
        "properties": {
            "channel_id": {"type": "string", "description": "ID канала или @username"},
            "text": {"type": "string", "description": "Текст поста"}
        },
        "required": ["channel_id", "text"]
    }
}

edit_message_as_agent_scheme = {
    "name": "edit_message_as_agent",
    "description": "Редактирует твое отправленное сообщение или пост в канале.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата или канала"},
            "message_id": {"type": "integer", "description": "ID сообщения/поста"},
            "new_text": {"type": "string", "description": "Новый текст сообщения."}
        },
        "required": ["chat_id", "message_id", "new_text"]
    }
}

pin_message_as_agent_scheme = {
    "name": "pin_message_as_agent",
    "description": "Закрепляет (Pin) сообщение в чате или канале.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата или канала"},
            "message_id": {"type": "integer", "description": "ID сообщения"}
        },
        "required": ["chat_id", "message_id"]
    }
}

vote_in_poll_as_agent_scheme = {
    "name": "vote_in_poll_as_agent",
    "description": "Голосует в опросе в Telegram.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата, канала или @username"},
            "message_id": {"type": "integer", "description": "ID сообщения с опросом"},
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Список вариантов ответа (текст)."
            }
        },
        "required": ["chat_id", "message_id", "options"]
    }
}

get_channel_subscribers_as_agent_scheme = {
    "name": "get_channel_subscribers_as_agent",
    "description": "Получает список подписчиков канала или участников группы.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата, канала или @username"},
            "limit": {"type": "integer", "description": "Сколько подписчиков показать"}
        },
        "required": ["chat_id"]
    }
}

check_user_in_chat_as_agent_scheme = {
    "name": "check_user_in_chat_as_agent",
    "description": "Проверяет, подписан ли конкретный пользователь на канал или состоит ли он в группе.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата, канала или @username"},
            "query": {"type": "string", "description": "Что ищем (например: 'Иван', '@gjfdgjf', '123456789')"}
        },
        "required": ["chat_id", "query"]
    }
}

send_voice_message_as_agent_scheme = {
    "name": "send_voice_message_as_agent",
    "description": "Отправляет голосовое сообщение.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата, группы или @username"},
            "text": {"type": "string", "description": "Текст, который нужно озвучить и отправить."}
        },
        "required": ["chat_id", "text"]
    }
}

get_tg_media_as_agent_scheme = {
    "name": "get_tg_media_as_agent",
    "description": "Универсальный инструмент для просмотра медиа. Скачивает и анализирует фотографии, голосовые сообщения, кружочки, стикеры и миниатюры видео.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата, группы или @username"},
            "message_id": {"type": "integer", "description": "ID сообщения, содержащего медиа"}
        },
        "required": ["chat_id", "message_id"]
    }
}

send_tg_sticker_as_agent_scheme = {
    "name": "send_tg_sticker_as_agent",
    "description": "Отправляет стикер в чат на основе переданного эмодзи.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата, группы или @username"},
            "emoji": {"type": "string", "description": "Эмодзи, по которому система подберет стикер (например: 🤡, ☕)"}
        },
        "required": ["chat_id", "emoji"]
    }
}

change_tg_avatar_as_agent_scheme = {
    "name": "change_tg_avatar_as_agent",
    "description": "Устанавливает новую аватарку для твоего Telegram-аккаунта.",
    "parameters": {
        "type": "object",
        "properties": {
            "image_path": {"type": "string", "description": "Локальный путь к изображению в песочнице"}
        },
        "required": ["image_path"]
    }
}

create_telegram_channel_as_agent_scheme = {
    "name": "create_telegram_channel_as_agent",
    "description": "Создает абсолютно новый Telegram-канал с твоего аккаунта.",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Название канала."},
            "about": {"type": "string", "description": "Описание канала."}
        },
        "required": ["title"]
    }
}

update_channel_info_as_agent_scheme = {
    "name": "update_channel_info_as_agent",
    "description": "Изменяет название или описание существующего канала.",
    "parameters": {
        "type": "object",
        "properties": {
            "channel_id": {"type": "string", "description": "ID канала."},
            "new_title": {"type": "string", "description": "Новое название."},
            "new_about": {"type": "string", "description": "Новое описание."}
        },
        "required": ["channel_id"]
    }
}

set_channel_username_as_agent_scheme = {
    "name": "set_channel_username_as_agent",
    "description": "Делает канал публичным, назначая ему @username.",
    "parameters": {
        "type": "object",
        "properties": {
            "channel_id": {"type": "string", "description": "ID канала."},
            "username": {"type": "string", "description": "Желаемый юзернейм."}
        },
        "required": ["channel_id", "username"]
    }
}

promote_user_to_admin_as_agent_scheme = {
    "name": "promote_user_to_admin_as_agent",
    "description": "Назначает пользователя администратором в твоем канале с полными правами.",
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
            "last_name": {"type": "string", "description": "Новая фамилия."}
        },
        "required": ["first_name"]
    }
}

change_account_username_as_agent_scheme = {
    "name": "change_account_username_as_agent",
    "description": "Изменяет @username твоего официального Telegram-аккаунта.",
    "parameters": {"type": "object", "properties": {"username": {"type": "string", "description": "Желаемый юзернейм."}}, "required": ["username"]}
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
    "description": "Показывает собеседнику статус 'Печатает...' или 'Записывает голосовое...'.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата или @username"},
            "action": {"type": "string", "enum": ["typing", "record-audio"], "description": "Какое действие показать собеседнику."}
        },
        "required": ["chat_id"]
    }
}

leave_chat_as_agent_scheme = {
    "name": "leave_chat_as_agent",
    "description": "Покидает группу или канал.",
    "parameters": {"type": "object", "properties": {"chat_id": {"type": "string", "description": "ID чата/канала"}}, "required": ["chat_id"]}
}

archive_chat_as_agent_scheme = {
    "name": "archive_chat_as_agent",
    "description": "Отправляет чат/группу в папку 'Архив'.",
    "parameters": {"type": "object", "properties": {"chat_id": {"type": "string", "description": "ID чата/канала"}}, "required": ["chat_id"]}
}

create_supergroup_as_agent_scheme = {
    "name": "create_supergroup_as_agent",
    "description": "Создает новую Telegram-группу (супергруппу).",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Название группы."},
            "about": {"type": "string", "description": "Описание группы."}
        },
        "required": ["title"]
    }
}

invite_user_to_chat_as_agent_scheme = {
    "name": "invite_user_to_chat_as_agent",
    "description": "Приглашает (добавляет) пользователя в группу или канал.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID группы/канала."},
            "user_id": {"type": "string", "description": "ID пользователя или @username."}
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
            "last_name": {"type": "string", "description": "Фамилия для сохранения."}
        },
        "required": ["user_id", "first_name"]
    }
}

get_chat_admins_as_agent_scheme = {
    "name": "get_chat_admins_as_agent",
    "description": "Возвращает список администраторов и создателя группы/канала.",
    "parameters": {"type": "object", "properties": {"chat_id": {"type": "string", "description": "ID чата, канала или @username."}}, "required": ["chat_id"]}
}

send_file_to_tg_chat_as_agent_scheme = {
    "name": "send_file_to_tg_chat_as_agent",
    "description": "Берет указанный файл из твоей песочницы (workspace/sandbox/) и отправляет его в Telegram-чат как документ.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата, группы или @username"},
            "filename": {"type": "string", "description": "Имя файла в песочнице (например: 'report.pdf')"},
            "caption": {"type": "string", "description": "Текстовая подпись к файлу."}
        },
        "required": ["chat_id", "filename"]
    }
}

unarchive_tg_chat_as_agent_scheme = {
    "name": "unarchive_tg_chat_as_agent",
    "description": "Возвращает чат или группу из архива в основной список диалогов.",
    "parameters": {"type": "object", "properties": {"chat_id": {"type": "string", "description": "ID чата/канала"}}, "required": ["chat_id"]}
}

search_chat_messages_as_agent_scheme = {
    "name": "search_chat_messages_as_agent",
    "description": "Ищет старые сообщения в конкретном чате/группе.",
    "parameters": {
        "type": "object",
        "properties": {
            "chat_id": {"type": "string", "description": "ID чата, группы или @username"},
            "query": {"type": "string", "description": "Текст для поиска."},
            "from_user": {"type": "string", "description": "ID пользователя или @username, чьи сообщения нужно найти."},
            "limit": {"type": "integer", "description": "Максимальное количество результатов."}
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
TELEGRAM_SCHEMAS = [
    # Работа с текстовыми сообщениями
    send_message_as_agent_scheme,
    reply_to_message_as_agent_scheme,
    delete_message_as_agent_scheme,
    forward_message_as_agent_scheme,
    edit_message_as_agent_scheme,
    pin_message_as_agent_scheme,

    # Медиа (изображения, аудио, видео, файлы)
    get_tg_media_as_agent_scheme,
    send_voice_message_as_agent_scheme,
    send_file_to_tg_chat_as_agent_scheme,
    download_file_from_tg_as_agent_scheme,
    change_channel_avatar_as_agent_scheme,

    # Реакции
    set_message_reaction_as_agent_scheme,

    # Чаты
    get_chat_info_as_agent_scheme,
    read_chat_as_agent_scheme,
    get_dialogs_as_agent_scheme,
    mark_chat_as_read_as_agent_scheme,
    set_chat_typing_status_as_agent_scheme,
    leave_chat_as_agent_scheme,
    archive_chat_as_agent_scheme,
    unarchive_tg_chat_as_agent_scheme,
    search_chat_messages_as_agent_scheme,

    # Работа с каналами
    search_telegram_channels_as_agent_scheme,
    get_channel_posts_as_agent_scheme,
    get_post_comments_as_agent_scheme,
    join_telegram_channel_as_agent_scheme,
    comment_on_post_as_agent_scheme,
    create_channel_post_as_agent_scheme,
    create_telegram_channel_as_agent_scheme,
    update_channel_info_as_agent_scheme,
    set_channel_username_as_agent_scheme,
    promote_user_to_admin_as_agent_scheme,
    create_discussion_group_as_agent_scheme,
    get_chat_admins_as_agent_scheme,

    # Работа с группами
    create_supergroup_as_agent_scheme,

    # Работа с подписчиками
    get_channel_subscribers_as_agent_scheme,
    check_user_in_chat_as_agent_scheme,

    # Работа с опросами
    create_poll_as_agent_scheme,
    get_poll_results_as_agent_scheme,
    vote_in_poll_as_agent_scheme,

    # Изменение статуса/Bio
    change_my_bio_as_agent_scheme,

    # Работа с ЧС/банами
    ban_user_as_agent_scheme,
    unban_user_as_agent_scheme,
    get_banned_users_as_agent_scheme,

    # Стикеры
    save_sticker_pack_as_agent_scheme,
    send_tg_sticker_as_agent_scheme,

    # Свой аккаунт
    change_tg_avatar_as_agent_scheme,
    change_account_name_as_agent_scheme,
    change_account_username_as_agent_scheme,
    invite_user_to_chat_as_agent_scheme,
    add_user_to_contacts_as_agent_scheme,



]

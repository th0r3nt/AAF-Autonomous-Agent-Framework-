import platform
import ctypes
import asyncio 
from collections import deque
import os
import ast
from datetime import datetime, timedelta
from pathlib import Path
from config.config_manager import config
from src.layer00_utils.logger import system_logger
from src.layer00_utils.image_tools import compress_and_encode_image
from src.layer01_datastate.sql_db.management.dialogue import create_dialogue_entry
from src.layer02_sensors.telegram.agent_account.client import agent_client


# ИМПОРТ НАВЫКОВ

from src.layer00_utils.workspace import (
    workspace_manager
)
from src.layer00_utils.web_tools import (
    _web_search, _read_webpage, _get_habr_articles, _get_habr_news
)

from src.layer00_utils._tools import (
    make_screenshot
)
from src.layer00_utils.sandbox_env.executor import (
    execute_once
)
from src.layer00_utils.sandbox_env.manager import (
    _start_background_python_script, _kill_background_python_script, _get_running_python_scripts
)
from src.layer01_datastate.memory_manager import (
    memory_manager
)
from src.layer01_datastate.graph_db.graph_db_management import (
    manage_graph, explore_graph, get_full_graph, delete_from_graph
)
from src.layer02_sensors.pc.terminal.output import (
    terminal_output
)
from src.layer02_sensors.pc.voice.tts import (
    generate_voice
)
from src.layer02_sensors.pc.windows_control import (
    show_windows_notification
)
from src.layer02_sensors.telegram.shared_tools.telethon_tools import (
    tg_send_message, tg_reply_to_message, tg_get_recent_messages, 
    tg_get_dialogs, tg_get_channel_posts, tg_get_chat_info,
    tg_mark_as_read, tg_set_reaction, tg_search_channels, 
    tg_join_channel, tg_comment_on_post, tg_get_unread_chats_summary,
    tg_delete_message, tg_forward_message, tg_create_poll,
    tg_get_post_comments, tg_change_bio, tg_get_poll_results,
    tg_ban_user, tg_save_sticker_set, tg_unban_user, tg_get_banned_users,
    tg_create_channel_post, tg_edit_message, tg_pin_message, tg_vote_in_poll,
    tg_get_channel_subscribers, tg_check_user_in_chat, tg_send_voice_message,
    tg_get_media, tg_send_sticker, tg_change_avatar, tg_create_channel, 
    tg_update_channel_info, tg_set_channel_username, tg_promote_to_admin,
    tg_change_account_name, tg_change_account_username, tg_create_discussion_group,
    tg_set_typing_status, tg_leave_chat, tg_archive_chat, tg_create_supergroup, 
    tg_invite_to_chat, tg_add_to_contacts, tg_get_chat_admins, tg_send_file,
    tg_unarchive_chat, tg_search_chat_messages, tg_download_file, tg_change_channel_avatar
)

def _format_chat_source(chat_id: str | int, topic_id: int = None) -> str:
    """Вспомогательная функция: очищает ID и формирует тег источника для БД"""
    clean_id = str(chat_id).replace('@', '')
    topic_str = f" [Топик ID: {topic_id}]" if topic_id else ""
    if clean_id.startswith('-'):
        return f"tg_agent_group_({clean_id}){topic_str}"
    return f"tg_agent_chat_({clean_id}){topic_str}"

# =====================================================================
# НАВЫКИ: ЛИЧНЫЙ АККАУНТ АГЕНТА В TELEGRAM
# =====================================================================

async def send_message_as_agent(chat_id: str, text: str, topic_id: int = None, silent: bool = False, delay_seconds: int = 0) -> str:
    """Обертка: отправляет сообщение (с поддержкой silent и отложки)"""
    schedule_date = None
    if delay_seconds > 0:
        schedule_date = datetime.now() + timedelta(seconds=delay_seconds)
        
    result = await tg_send_message(agent_client, chat_id, text, topic_id, silent, schedule_date)
    
    chat_source = _format_chat_source(chat_id, topic_id)
    delay_str = f" [Отложено на {delay_seconds} сек]" if delay_seconds > 0 else ""
    silent_str = " [Без звука]" if silent else ""
    
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"{silent_str}{delay_str} {text}".strip(), source=chat_source)
    return result

async def set_chat_typing_status_as_agent(chat_id: str, action: str = "typing") -> str:
    """Обертка: Отправляет статус 'Печатает...' или 'Записывает аудио...' (длится ~5 секунд)"""
    return await tg_set_typing_status(agent_client, chat_id, action)

async def leave_chat_as_agent(chat_id: str) -> str:
    """Обертка: покидает Telegram-чат"""
    return await tg_leave_chat(agent_client, chat_id)

async def archive_chat_as_agent(chat_id: str) -> str:
    """Обертка: архивирует Telegram-чат"""
    return await tg_archive_chat(agent_client, chat_id)

async def read_chat_as_agent(chat_id: str, limit: int = 50, topic_id: int = None) -> str:
    """Обертка: читает последние n сообщений с чата"""
    return await tg_get_recent_messages(agent_client, chat_id, limit, topic_id)

async def get_dialogs_as_agent(limit: int = 30) -> str:
    """Обертка: получает список последних диалогов/групп"""
    return await tg_get_dialogs(agent_client, limit)

async def reply_to_message_as_agent(chat_id: str, message_id: int, text: str) -> str:
    """Обертка: отвечает на конкретное сообщение"""
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=text, source=chat_source)
    return await tg_reply_to_message(agent_client, chat_id, message_id, text)

async def get_channel_posts_as_agent(channel_name: str, limit: int = 10) -> str:
    """Обертка: получает последние посты из канала"""
    return await tg_get_channel_posts(agent_client, channel_name, limit)

async def get_chat_info_as_agent(chat_id: str) -> str:
    """Обертка: получает полную информацию (Bio, участники) о чате/юзере"""
    return await tg_get_chat_info(agent_client, chat_id)

async def mark_chat_as_read_as_agent(chat_id: str) -> str:
    """Обертка: помечает чат как прочитанный"""
    return await tg_mark_as_read(agent_client, chat_id)

async def set_message_reaction_as_agent(chat_id: str, message_id: int, emoticon: str) -> str:
    """Обертка: ставит реакцию на сообщение"""
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Поставлена реакция {emoticon} на сообщение ID {message_id}]", source=chat_source)
    return await tg_set_reaction(agent_client, chat_id, message_id, emoticon)

async def search_telegram_channels_as_agent(query: str, limit: int = 5) -> str:
    """Обертка: ищет каналы в ТГ"""
    return await tg_search_channels(agent_client, query, limit)

async def join_telegram_channel_as_agent(link_or_username: str) -> str:
    """Обертка: вступает в канал"""
    return await tg_join_channel(agent_client, link_or_username)

async def comment_on_post_as_agent(channel_id: str, message_id: int, text: str) -> str:
    """Обертка: оставляет комментарий под постом в канале"""
    chat_source = _format_chat_source(channel_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Комментарий к посту {message_id}]: {text}", source=chat_source)
    return await tg_comment_on_post(agent_client, channel_id, message_id, text)

async def get_unread_tg_summary() -> str:
    """Вспомогательная функция для контекста: возвращает список чатов с непрочитанными сообщениями"""
    return await tg_get_unread_chats_summary(agent_client)

async def delete_message_as_agent(chat_id: str, message_id: int) -> str:
    """Обертка: удаляет сообщение"""
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Системное действие: Удаление своего сообщения ID {message_id}]", source=chat_source)
    return await tg_delete_message(agent_client, chat_id, message_id)

async def forward_message_as_agent(from_chat: str, message_id: int, to_chat: str) -> str:
    """Обертка: пересылает сообщение"""
    chat_source = _format_chat_source(to_chat) # Логируем туда, КУДА переслали
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Системное действие: Пересылка сообщения ID {message_id} из чата {from_chat}]", source=chat_source)
    return await tg_forward_message(agent_client, from_chat, message_id, to_chat)

async def create_poll_as_agent(chat_id: str, question: str, options: list) -> str:
    """Обертка: создает опрос"""
    return await tg_create_poll(agent_client, chat_id, question, options)

async def get_post_comments_as_agent(channel_name: str, message_id: int, limit: int = 20) -> str:
    """Обертка: читает комментарии"""
    return await tg_get_post_comments(agent_client, channel_name, message_id, limit)

async def change_my_bio_as_agent(new_bio: str) -> str:
    """Обертка: меняет био"""
    return await tg_change_bio(agent_client, new_bio)

async def get_poll_results_as_agent(chat_id: str, message_id: int) -> str:
    """Обертка: результаты опроса"""
    return await tg_get_poll_results(agent_client, chat_id, message_id)

async def ban_user_as_agent(chat_id: str, user_id: str, reason: str = "Нарушение правил") -> str:
    """Обертка: бан пользователя"""
    return await tg_ban_user(agent_client, chat_id, user_id, reason)

async def save_sticker_pack_as_agent(short_name: str) -> str:
    """Обертка: сохранение стикеров"""
    return await tg_save_sticker_set(agent_client, short_name)

async def unban_user_as_agent(chat_id: str, user_id: str) -> str:
    """Обертка: разбан пользователя"""
    return await tg_unban_user(agent_client, chat_id, user_id)

async def get_banned_users_as_agent(chat_id: str, limit: int = 50) -> str:
    """Обертка: просмотр забаненных"""
    return await tg_get_banned_users(agent_client, chat_id, limit)

async def create_channel_post_as_agent(channel_id: str, text: str) -> str:
    """Обертка: публикует пост в канал"""
    chat_source = _format_chat_source(channel_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Опубликован пост]: {text}", source=chat_source)
    return await tg_create_channel_post(agent_client, channel_id, text)

async def edit_message_as_agent(chat_id: str, message_id: int, new_text: str) -> str:
    """Обертка: редактирует сообщение/пост"""
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Редактирование сообщения ID {message_id}]: {new_text}", source=chat_source)
    return await tg_edit_message(agent_client, chat_id, message_id, new_text)

async def pin_message_as_agent(chat_id: str, message_id: int) -> str:
    """Обертка: закрепляет сообщение"""
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Системное действие: Закрепление сообщения ID {message_id}]", source=chat_source)
    return await tg_pin_message(agent_client, chat_id, message_id)

async def vote_in_poll_as_agent(chat_id: str, message_id: int, options: list) -> str:
    """Обертка: голосует в опросе"""
    return await tg_vote_in_poll(agent_client, chat_id, message_id, options)

async def get_channel_subscribers_as_agent(chat_id: str, limit: int = 50) -> str:
    """Обертка: получает список подписчиков"""
    return await tg_get_channel_subscribers(agent_client, chat_id, limit)

async def check_user_in_chat_as_agent(chat_id: str, query: str) -> str:
    """Обертка: проверяет наличие юзера в чате"""
    return await tg_check_user_in_chat(agent_client, chat_id, query)

async def send_voice_message_as_agent(chat_id: str, text: str) -> str:
    """Обертка: отправляет голосовое сообщение в чат"""
    result = await tg_send_voice_message(agent_client, chat_id, text)
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Голосовое сообщение]: {text}", source=chat_source)
    return result

async def get_tg_media_as_agent(chat_id: str, message_id: int) -> dict | str:
    """Обертка: скачивает медиа (фото, гс, кружок, стикер, превью видео) и кидает в ReAct цикл"""
    result = await tg_get_media(agent_client, chat_id, message_id)
    return result

async def send_tg_sticker_as_agent(chat_id: str, emoji: str) -> str:
    """Обертка: отправляет стикер по эмодзи"""
    result = await tg_send_sticker(agent_client, chat_id, emoji)
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Отправлен стикер, соответствующий эмодзи: {emoji}]", source=chat_source)
    return result

async def change_tg_avatar_as_agent(image_path: str) -> str:
    """Обертка: меняет аватарку профиля"""
    return await tg_change_avatar(agent_client, image_path)

async def create_telegram_channel_as_agent(title: str, about: str = "") -> str:
    """Обертка: создает канал"""
    result = await tg_create_channel(agent_client, title, about)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Системное действие: Создан новый канал '{title}']", source="system")
    return result

async def update_channel_info_as_agent(channel_id: str, new_title: str = None, new_about: str = None) -> str:
    """Обертка: обновляет инфу канала"""
    return await tg_update_channel_info(agent_client, channel_id, new_title, new_about)

async def set_channel_username_as_agent(channel_id: str, username: str) -> str:
    """Обертка: ставит публичный юзернейм"""
    return await tg_set_channel_username(agent_client, channel_id, username)

async def promote_user_to_admin_as_agent(channel_id: str, user_id: str) -> str:
    """Обертка: выдает права админа"""
    return await tg_promote_to_admin(agent_client, channel_id, user_id)

async def change_account_name_as_agent(first_name: str, last_name: str = "") -> str:
    """Обертка: меняет имя аккаунта"""
    return await tg_change_account_name(agent_client, first_name, last_name)

async def change_account_username_as_agent(username: str) -> str:
    """Обертка: меняет юзернейм аккаунта"""
    return await tg_change_account_username(agent_client, username)

async def create_discussion_group_as_agent(channel_id: str, group_title: str) -> str:
    """Обертка: создает привязанную группу для комментариев"""
    return await tg_create_discussion_group(agent_client, channel_id, group_title)

async def create_supergroup_as_agent(title: str, about: str = "") -> str:
    return await tg_create_supergroup(agent_client, title, about)

async def invite_user_to_chat_as_agent(chat_id: str, user_id: str) -> str:
    return await tg_invite_to_chat(agent_client, chat_id, user_id)

async def add_user_to_contacts_as_agent(user_id: str, first_name: str, last_name: str = "") -> str:
    return await tg_add_to_contacts(agent_client, user_id, first_name, last_name)

async def get_chat_admins_as_agent(chat_id: str) -> str:
    return await tg_get_chat_admins(agent_client, chat_id)

async def send_file_to_tg_chat_as_agent(chat_id: str, filename: str, caption: str = "") -> str:
    """Обертка: отправляет файл из песочницы в Telegram"""
    try:
        clean_filename = os.path.basename(filename.replace("file:///", "").replace("/app/", ""))
        filepath = workspace_manager.get_sandbox_file(clean_filename)
        
        if not filepath.exists() or not filepath.is_file():
            return f"Ошибка: Файл '{clean_filename}' не найден в песочнице."
        
        result = await tg_send_file(agent_client, chat_id, str(filepath), caption)
        
        chat_source = _format_chat_source(chat_id)
        await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Отправлен файл: {clean_filename}] {caption}".strip(), source=chat_source)
        return result
    except Exception as e:
        return f"Системная ошибка при отправке файла: {e}"
    
async def unarchive_tg_chat_as_agent(chat_id: str) -> str:
    """Обертка: возвращает чат из архива"""
    return await tg_unarchive_chat(agent_client, chat_id)

async def search_chat_messages_as_agent(chat_id: str, query: str = None, from_user: str = None, limit: int = 20) -> str:
    """Обертка: ищет сообщения в чате по тексту или автору"""
    return await tg_search_chat_messages(agent_client, chat_id, query, from_user, limit)

async def download_file_from_tg_as_agent(chat_id: str, message_id: int) -> str:
    """Обертка: скачивает файл из ТГ в песочницу"""
    result = await tg_download_file(agent_client, chat_id, message_id)
    chat_source = _format_chat_source(chat_id)
    await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Системное действие: Скачивание файла из сообщения ID {message_id}]", source=chat_source)
    return result

async def change_channel_avatar_as_agent(channel_id: str, filename: str) -> str:
    """Обертка: меняет аватарку канала"""
    try:
        clean_filename = os.path.basename(filename.replace("file:///", "").replace("/app/", ""))
        filepath = workspace_manager.get_sandbox_file(clean_filename)
        
        result = await tg_change_channel_avatar(agent_client, channel_id, str(filepath))
        chat_source = _format_chat_source(channel_id)
        await create_dialogue_entry(actor=config.identity.agent_name, message=f"[Системное действие: Обновлена аватарка канала файлом {clean_filename}]", source=chat_source)
        return result
    except Exception as e:
        return f"Ошибка обработки пути к файлу: {e}"

# =====================================================================
# PC CONTROL
# =====================================================================

def lock_pc():
    """Блокирует Windows"""
    if config.system.flags.headless_mode or platform.system() != "Windows":
        return "Ошибка: Данное действие недоступно в серверном (Headless) режиме."
    
    if platform.system() == "Windows":
        try:
            ctypes.windll.user32.LockWorkStation()
            system_logger.debug("Рабочая станция Windows заблокирована.")
            return "Рабочая станция Windows заблокирована."
        except Exception as e:
            return f"Ошибка при блокировке рабочей станции: {e}"
    else:
        return "Данная команда работает только в операционной системе Windows."

async def print_to_terminal(text: str) -> str:
    """Пишет в терминал основного ПК"""
    await terminal_output(text)
    return "Сообщение успешно выведено в терминал."

async def speak_text(text: str) -> str:
    """Озвучивает текст"""
    # Запускаем генерацию и озвучку как независимую фоновую задачу
    asyncio.create_task(generate_voice(text))
    return "Процесс генерации голоса и озвучки запущен в фоновом режиме."

def list_local_directory(path: str = ".") -> str:
    """Показывает содержимое директории"""
    try:
        # Resolve делает путь абсолютным и убирает всякие '../'
        target_path = Path(path).resolve()
        
        if not target_path.exists():
            return f"Ошибка: Директория '{path}' не существует."
        if not target_path.is_dir():
            return f"Ошибка: '{path}' не является директорией."

        items = os.listdir(target_path)
        dirs = [d for d in items if (target_path / d).is_dir()]
        files = [f for f in items if (target_path / f).is_file()]

        dirs.sort()
        files.sort()

        result = f"Содержимое директории '{target_path}':\n"
        result += "Папки:\n" + ("\n".join([f" - {d}/" for d in dirs]) if dirs else " (нет)") + "\n"
        result += "Файлы:\n" + ("\n".join([f" - {f}" for f in files]) if files else " (нет)")
        return result
    except Exception as e:
        return f"Ошибка при чтении директории: {e}"

def read_local_system_file(filepath: str) -> str:
    """Читает содержимое файла с умным поиском по проекту и защитой путей Docker"""
    try:
        # 1. Очистка пути от артефактов LLM и Docker
        clean_path = filepath.strip()
        if clean_path.startswith("file:///"):
            clean_path = clean_path.replace("file:///", "", 1)
        if clean_path.startswith("/app/"):
            clean_path = clean_path.replace("/app/", "", 1)
            
        # 2. Жестко определяем корень проекта 
        current_dir = Path(__file__).resolve()
        project_root = current_dir.parents[4]
        requested_path = Path(clean_path)
        
        # 3. Сначала пробуем склеить корень проекта и запрошенный путь
        target_path = (project_root / requested_path).resolve()

        # Защита от выхода за пределы проекта 
        if not str(target_path).startswith(str(project_root)):
            system_logger.warning(f"[Security] Агент попытался выйти за пределы проекта: {target_path}")
            return "Ошибка безопасности: Доступ за пределы корневой директории проекта запрещен."

        # Защита от чтения песочницы через системный инструмент
        if "workspace" in target_path.parts and "sandbox" in target_path.parts:
            return "Ошибка: Для чтения файлов из песочницы (sandbox/отчеты субагентов) используй специализированный инструмент 'read_sandbox_file'."

        # 4. Если по прямому пути файла нет, включаем "Умный поиск"
        if not target_path.exists():
            filename = requested_path.name
            
            # Игнорируем виртуальные окружения, кэш, гит и ПЕСОЧНИЦУ
            exclude_dirs = {'.venv', 'venv', 'env', '__pycache__', '.git', '.idea', 'build', 'logs', 'workspace'}
            
            matches = [
                p for p in project_root.rglob(filename)
                if p.is_file() and not any(part in p.parts for part in exclude_dirs)
            ]

            if not matches:
                return f"Ошибка: Файл '{filename}' не найден ни по указанному пути, ни где-либо еще в проекте."

            if len(matches) > 1:
                match_list = "\n".join([f"- {m.relative_to(project_root).as_posix()}" for m in matches])
                return f"Найдено несколько файлов с именем '{filename}'. Уточните путь, вызвав функцию еще раз с одним из этих путей:\n{match_list}"

            # Если нашли ровно один файл — берем его!
            target_path = matches[0]
            system_logger.debug(f"[Smart Search] Файл '{filename}' найден по пути: {target_path.relative_to(project_root)}")

        # 5. Секьюрити чек: жесткий блок на .env и .log
        if target_path.name == ".env" or target_path.suffix == ".env":
            system_logger.warning(f"[Security] Агент попытался прочитать файл конфигурации: {target_path}")
            return "Ошибка безопасности: В доступе отказано. Чтение файлов конфигурации (.env) строго запрещено."
        
        if target_path.suffix == ".log":
            return "Ошибка: Для чтения логов системы строго используй специализированный инструмент 'read_recent_logs'."

        if not target_path.is_file():
            return f"Ошибка: '{target_path.relative_to(project_root).as_posix()}' не является файлом."

        # 6. Читаем файл
        content = None
        encodings_to_try = ['utf-8', 'utf-16', 'windows-1251', 'latin-1']
        
        for enc in encodings_to_try:
            try:
                with open(target_path, 'r', encoding=enc) as f:
                    content = f.read()
                break # Если прочиталось без ошибок, выходим из цикла
            except UnicodeDecodeError:
                continue # Пробуем следующую кодировку
                
        if content is None:
            return f"Ошибка: Невозможно прочитать '{filepath}'. Похоже, это бинарный файл (или используется неизвестная кодировка)."

        display_path = target_path.relative_to(project_root).as_posix()

        # 7. Защита контекста LLM
        MAX_CHARS = config.llm.limits.max_file_read_chars
        if len(content) > MAX_CHARS:
            truncated_content = content[:MAX_CHARS]
            return f"Содержимое файла '{display_path}' (Обрезано, слишком большой):\n\n{truncated_content}\n\n... [ОСТАЛЬНАЯ ЧАСТЬ ФАЙЛА ОБРЕЗАНА]"
        
        return f"Содержимое файла '{display_path}':\n\n{content}"
        
    except Exception as e:
        return f"Ошибка при чтении файла: {e}"
    
def read_sandbox_file(filename: str) -> str:
    """Обертка: читает файл исключительно из песочницы (workspace/sandbox)"""
    try:
        # Убираем пути, оставляем только имя (защита)
        clean_filename = os.path.basename(filename.replace("file:///", "").replace("/app/", ""))
        
        filepath = workspace_manager.get_sandbox_file(clean_filename)
        
        if not filepath.exists() or not filepath.is_file():
            return f"Ошибка: Файл '{clean_filename}' не найден в песочнице (sandbox)."
            
        content = None
        for enc in ['utf-8', 'utf-16', 'windows-1251', 'latin-1']:
            try:
                with open(filepath, 'r', encoding=enc) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
                
        if content is None:
            return f"Ошибка: Файл '{clean_filename}' является бинарным или имеет неизвестную кодировку."
            
        # Лимит для песочницы
        if len(content) > 80000:
            content = content[:80000] + "\n\n... [ОСТАЛЬНАЯ ЧАСТЬ ФАЙЛА ОБРЕЗАНА ИЗ-ЗА ЛИМИТОВ]"
            
        return f"Содержимое файла '{clean_filename}' из песочницы:\n\n{content}"
    except Exception as e:
        return f"Ошибка при чтении файла из песочницы: {e}"
    

def get_system_architecture_map(*args, **kwargs) -> str:
    """Генерирует дерево проекта (корень + src/), показывая .py и .md файлы"""
    try:
        # 1. Находим корень проекта
        current_dir = Path(__file__).resolve()
        src_dir = next((p for p in current_dir.parents if p.name == "src"), None)
        if src_dir:
            project_root = src_dir.parent
        else:
            return "Ошибка: Не удалось найти корневую директорию проекта."
                
        if not project_root.exists():
            return "Ошибка: Не удалось найти корневую директорию проекта."

        # Жесткий фильтр папок, куда вообще не надо лезть (экономим токены LLM)
        EXCLUDE_DIRS = {
            'venv', '.venv', 'env', '__pycache__', '.git', '.idea', '.vscode', 
            'build', 'dist', '.pytest_cache', 'BAAI--bge-m3', 'vosk_model',
            'chroma_db', 'telegram_sessions', 'embedding_model', 'phrases',
            'logs' # Логи тоже исключаем, там огромные файлы контекста
        }
        
        # Разрешенные файлы для отображения в дереве
        ALLOWED_EXTENSIONS = {'.py', '.md', '.yaml', '.json', '.txt'}
        
        def build_tree(dir_path: Path, prefix: str = "") -> str:
            tree_str = ""
            
            # Пытаемся прочитать docstring из __init__.py (если это Python-модуль)
            docstring = ""
            init_file = dir_path / "__init__.py"
            if init_file.exists() and init_file.is_file():
                try:
                    with open(init_file, 'r', encoding='utf-8') as f:
                        module = ast.parse(f.read())
                        doc = ast.get_docstring(module)
                        if doc:
                            first_line = doc.split('\n')[0].strip()
                            docstring = f"  # {first_line}"
                except Exception:
                    pass

            # Имя текущей папки + её описание
            tree_str += f"{prefix}📂 {dir_path.name}/{docstring}\n"
            
            try:
                items = sorted(dir_path.iterdir(), key=lambda x: (x.is_file(), x.name))
            except PermissionError:
                return tree_str
                
            # Фильтруем мусорные папки
            items = [item for item in items if item.name not in EXCLUDE_DIRS]
            
            # Оставляем только папки и разрешенные файлы (.py, .md)
            filtered_items = []
            for item in items:
                if item.is_dir():
                    filtered_items.append(item)
                elif item.is_file() and item.suffix in ALLOWED_EXTENSIONS:
                    filtered_items.append(item)

            for i, item in enumerate(filtered_items):
                is_last = (i == len(filtered_items) - 1)
                connector = "└── " if is_last else "├── "
                
                if item.is_dir():
                    extension = "    " if is_last else "│   "
                    tree_str += build_tree(item, prefix + extension)
                else:
                    tree_str += f"{prefix}{connector}📄 {item.name}\n"
                    
            return tree_str

        # Запускаем сборку дерева от корня проекта
        map_str = build_tree(project_root)
        system_logger.debug("[System Map] Сгенерирована архитектурная карта проекта (включая .md).")
        return f"Архитектурная карта проекта (корень '{project_root.name}'):\n\n{map_str}"

    except Exception as e:
        system_logger.error(f"Ошибка при генерации карты проекта: {e}")
        return f"Ошибка при генерации карты проекта: {e}"

def clean_temp_workspace() -> str:
    """Обертка: очищает временные файлы"""
    return workspace_manager.clean_temp_workspace()

async def send_windows_notification(title: str, text: str) -> str:
    """Обертка: отправляет push-уведомление Windows"""
    # Запускаем синхронную функцию в фоне, хотя win10toast и так юзает потоки,
    # это дополнительная страховка для asyncio
    return await asyncio.to_thread(show_windows_notification, title, text)

async def look_at_screen() -> dict | str:
    """Обертка: делает скриншот и передает его в контекст LLM"""
    try:
        filepath = await make_screenshot()
        b64_string = await asyncio.to_thread(compress_and_encode_image, filepath)
        # Магический словарь, который react.py превратит в картинку для Gemini
        return {"__image_base64__": b64_string}
    except Exception as e:
        return f"Не удалось получить изображение с экрана: {e}"


async def write_local_file(filename: str, content: str) -> str:
    """Обертка: пишет текстовый файл в изолированную песочницу (sandbox)"""
    try:
        # Очищаем путь, оставляя только имя файла (защита от двойных путей)
        clean_filename = os.path.basename(filename) 
        
        filepath = workspace_manager.get_sandbox_file(clean_filename)
        
        # Запускаем I/O операцию в отдельном потоке
        def _write():
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        
        await asyncio.to_thread(_write)
        return f"Файл успешно сохранен/перезаписан по пути: {filepath}"
    except Exception as e:
        return f"Ошибка при записи файла: {e}"

# =====================================================================
# SYSTEM
# =====================================================================

def change_proactivity_interval(seconds: int) -> str:
    """Изменяет частоту вызова проактивного цикла агента"""
    from src.layer03_brain.agent.engine.engine import brain_engine
    try:
        # Учитываем min_cooldown, чтобы агент случайно не поставил интервал меньше жесткого лимита
        if seconds < brain_engine.min_cooldown:
            return f"Ошибка: Интервал не может быть меньше минимального кулдауна ({brain_engine.min_cooldown} сек) во избежание перерасхода бюджета."
        
        old_interval = brain_engine.proactivity_interval
        brain_engine.proactivity_interval = seconds
        
        # Корректируем цель с учетом нового интервала
        brain_engine.target_proactive_time = brain_engine.last_proactive_time + seconds
        
        system_logger.info(f"[Proactivity ReAct] Интервал проактивности успешно изменен с {old_interval} сек. на {seconds} сек.")
        return f"[Proactivity ReAct] Интервал проактивности успешно изменен с {old_interval} сек. на {seconds} сек."
    except Exception as e:
        return f"Ошибка при изменении интервала: {e}"
    
def change_thoughts_interval(seconds: int) -> str:
    """Изменяет частоту вызова цикла интроспекции (мыслей) агента"""
    from src.layer03_brain.agent.engine.engine import brain_engine # Локальный импорт во избежание цикличности
    try:
        if seconds < 10:
            return "Ошибка: Интервал не может быть меньше 10 секунд (во избежание перегрузки БД)."
        
        old_interval = brain_engine.thoughts_interval
        brain_engine.thoughts_interval = seconds
        
        system_logger.info(f"[Thoughts ReAct] Интервал интроспекции успешно изменен с {old_interval} сек. на {seconds} сек.")
        return f"[Thoughts ReAct] Интервал интроспекции успешно изменен с {old_interval} сек. на {seconds} сек."
    except Exception as e:
        return f"[Thoughts ReAct] Ошибка при изменении интервала интроспекции: {e}"

async def read_recent_logs(lines: int = 50) -> str:
    """Обертка: читает последние N строк из системного лога"""
    log_path = "logs/system.log"
    
    def _read_tail():
        if not os.path.exists(log_path):
            return "Файл логов не найден."
        
        with open(log_path, 'r', encoding='utf-8') as f:
            # deque эффективно сохранит только последние N строк, не загружая весь файл в память
            tail = deque(f, maxlen=lines)
        
        if not tail:
            return "Файл логов пуст."
            
        return "".join(tail)
        
    try:
        result = await asyncio.to_thread(_read_tail)
        return f"Последние {lines} строк из логов системы:\n\n{result}"
    except Exception as e:
        return f"Ошибка при чтении логов: {e}"
    
async def shutdown_system() -> str:
    """Корректно завершает работу агента (Docker-контейнера)"""
    import os
    import signal
    from src.layer01_datastate.event_bus.event_bus import event_bus
    from src.layer01_datastate.event_bus.events import Events
    
    system_logger.warning("[System] Агент инициировал завершение работы системы.")
    
    # 1. Публикуем событие для корректного закрытия баз и смены статуса ТГ на offline
    await event_bus.publish(Events.STOP_SYSTEM)
    
    # 2. Даем системе секунду на обработку ивента
    await asyncio.sleep(5)
    
    # 3. Отправляем SIGTERM для завершения процесса
    os.kill(os.getpid(), signal.SIGTERM)
    return "Сигнал на завершение работы отправлен. Базы сохранены, система отключается..."

async def change_llm_model(new_model: str) -> str:
    """Изменяет текущую LLM-модель в памяти и в конфиге"""
    if new_model not in config.llm.available_models:
        return f"Ошибка: Модель '{new_model}' не поддерживается. Доступные: {', '.join(config.llm.available_models)}"
    try:
        # 1. Изменяем в памяти, чтобы заработало прямо сейчас
        config.llm.model_name = new_model
        import src.layer03_brain.agent.engine.react as react_module
        react_module.LLM_MODEL = new_model
        
        # 2. Изменяем в файле settings.yaml, чтобы сохранить при рестарте
        current_dir = Path(__file__).resolve()
        yaml_path = current_dir.parents[4] / "config" / "settings.yaml"
        
        if not yaml_path.exists():
            return f"Модель изменена в памяти на '{new_model}', но файл settings.yaml не найден для сохранения."
            
        # Аккуратно читаем файл и заменяем только нужную строку, чтобы не убить комментарии
        def _update_yaml():
            with open(yaml_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            with open(yaml_path, 'w', encoding='utf-8') as f:
                for line in lines:
                    if line.strip().startswith("model_name:"):
                        # Сохраняем оригинальные отступы
                        indent = line[:len(line) - len(line.lstrip())]
                        f.write(f'{indent}model_name: "{new_model}"\n')
                    else:
                        f.write(line)
                        
        await asyncio.to_thread(_update_yaml)
        
        system_logger.warning(f"[System] LLM-модель успешно изменена на: {new_model}")
        return f"Системная архитектура обновлена. Новая модель '{new_model}' активирована и сохранена в конфигурации."
        
    except Exception as e:
        return f"Ошибка при смене модели: {e}"


# =====================================================================
# INTERNET ACCESS
# =====================================================================

def web_search(query: str, limit: int = 10) -> str:
    """Обертка: поиск в интернете"""
    return _web_search(query, limit)

def read_webpage(url: str) -> str:
    """Обертка: чтение страницы"""
    return _read_webpage(url)

def get_habr_articles(limit: int = 5) -> str:
    """Обертка: чтение последних n статей с Хабра"""
    return _get_habr_articles(limit)

def get_habr_news(limit: int = 5) -> str:
    """Обертка: чтение новостной ленты Хабра"""
    return _get_habr_news(limit)


# =====================================================================
# MEMORY MANAGER (Фасад для всей памяти)
# =====================================================================

async def recall_memory(queries: list) -> str:
    """Обертка: Асинхронный поиск по всем векторным базам"""
    return await memory_manager.recall_memory(queries)

async def memorize_information(topic: str, text: str) -> str:
    """Обертка: Сохранение информации в векторную базу по топикам"""
    return await memory_manager.memorize_information(topic, text)

async def forget_information(collection_name: str, ids: list) -> str:
    """Обертка: Удаление информации из векторной базы"""
    return await memory_manager.forget_information(collection_name, ids)

async def manage_entity(action: str, name: str, category: str = None, tier: str = None, description: str = None, status: str = None, context: str = None, rules: str = None) -> str:
    """Обертка: Управление Картиной Мира (Mental State)"""
    return await memory_manager.manage_entity(action, name, category, tier, description, status, context, rules)

async def manage_task(action: str, task_id: int = None, description: str = None, status: str = None, term: str = None, context: str = None) -> str:
    """Обертка: Диспетчер долгосрочных задач"""
    return await memory_manager.manage_task(action, task_id, description, status, term, context)

async def deep_history_search(target: str, query: str = None, action_type: str = None, source: str = None, days_ago: int = None, limit: int = 50) -> str:
    """Обертка: Поиск по старым логам действий и диалогам"""
    return await memory_manager.deep_history_search(target, query, action_type, source, days_ago, limit)

async def get_chronicle_timeline(limit: int = 50) -> str:
    """Обертка: Получение единого таймлайна событий"""
    return await memory_manager.get_chronicle_timeline(limit)

async def get_all_vector_memory(collection_name: str) -> str:
    """Обертка: Получение абсолютно всех записей из векторной базы"""
    return await memory_manager.get_all_vector_memory(collection_name)


# =====================================================================
# PERSONALITY PARAMETERS (динамические черты личности агента)
# =====================================================================

async def manage_personality(action: str, trait: str = None, trait_id: int = None, reason: str = None) -> str:
    """Обертка: Управление личностью"""
    return await memory_manager.manage_personality(action, trait, trait_id, reason)


# =====================================================================
# GRAPH DATABASE (Нейронная сеть связей)
# =====================================================================

async def manage_graph_db(source: str, target: str, base_type: str, context: str = "[Нет контекста]") -> str:
    """Обертка: Управление графом связей"""
    return await manage_graph(source, target, base_type, context)

async def explore_graph_db(query: str) -> str:
    """Обертка: Исследование графа"""
    return await explore_graph(query)

async def get_full_graph_db() -> str:
    """Обертка: Полный дамп графа"""
    return await get_full_graph()

async def delete_from_graph_db(source_node: str, target_node: str = None) -> str:
    """Обертка: Удаление из графа"""
    return await delete_from_graph(source_node, target_node)


# =====================================================================
# SWARM MANAGEMENT
# =====================================================================

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

# =====================================================================
# SANDBOX MANAGEMENT
# =====================================================================

async def execute_python_script(filename: str) -> str:
    """Обертка: разовый запуск скрипта в песочнице"""
    return await execute_once(filename)

async def start_background_python_script(filename: str) -> str:
    """Обертка: запуск фонового демона"""
    return await asyncio.to_thread(_start_background_python_script, filename)

async def kill_background_python_script(filename: str) -> str:
    """Обертка: убийство фонового демона"""
    return await asyncio.to_thread(_kill_background_python_script, filename)

async def get_running_python_scripts() -> str:
    """Обертка: просмотр запущенных скриптов"""
    running = await asyncio.to_thread(_get_running_python_scripts)
    if not running:
        return "В песочнице нет запущенных фоновых скриптов."
    
    lines = ["Запущенные фоновые скрипты:"]
    for fname, pid in running.items():
        lines.append(f"- {fname} (PID: {pid})")
    return "\n".join(lines)

async def delete_sandbox_file(filename: str) -> str:
    """Удаляет файл из Sandbox"""
    try:
        # Очищаем путь, оставляя только имя файла (защита от выхода из директории)
        clean_filename = os.path.basename(filename.replace("file:///", "").replace("/app/", ""))
        
        filepath = workspace_manager.get_sandbox_file(clean_filename)
        
        if not filepath.exists() or not filepath.is_file():
            return f"Ошибка: Файл '{clean_filename}' не найден в песочнице."
            
        # Удаляем файл в отдельном потоке, так как это I/O операция
        await asyncio.to_thread(filepath.unlink)
        return f"Файл '{clean_filename}' успешно удален из песочницы."
    except Exception as e:
        return f"Ошибка при удалении файла: {e}"
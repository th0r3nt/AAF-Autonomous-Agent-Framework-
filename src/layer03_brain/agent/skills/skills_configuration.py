from src.layer03_brain.agent.skills import skills
from src.layer03_brain.agent.skills import skills_diagrams as sd
from src.layer03_brain.agent.skills import composite_skills

def _wrap_tool(schema):
    return {
        "type": "function",
        "function": schema
    }

# Список схем для передачи в OpenAI API
openai_tools =[
    # =========================================================
    # Telegram Telethon
    # =========================================================

    # Работа с текстовыми сообщениями
    _wrap_tool(sd.send_message_as_agent_scheme),
    _wrap_tool(sd.reply_to_message_as_agent_scheme),
    _wrap_tool(sd.delete_message_as_agent_scheme),
    _wrap_tool(sd.forward_message_as_agent_scheme),
    _wrap_tool(sd.edit_message_as_agent_scheme),
    _wrap_tool(sd.pin_message_as_agent_scheme),

    # Медиа (изображения, аудио, видео, файлы)
    _wrap_tool(sd.get_tg_media_as_agent_scheme),
    _wrap_tool(sd.send_voice_message_as_agent_scheme),
    _wrap_tool(sd.send_file_to_tg_chat_as_agent_scheme),
    _wrap_tool(sd.download_file_from_tg_as_agent_scheme),
    _wrap_tool(sd.change_channel_avatar_as_agent_scheme),

    # Реакции
    _wrap_tool(sd.set_message_reaction_as_agent_scheme),

    # Чаты
    _wrap_tool(sd.get_chat_info_as_agent_scheme),
    _wrap_tool(sd.read_chat_as_agent_scheme),
    _wrap_tool(sd.get_dialogs_as_agent_scheme),
    _wrap_tool(sd.mark_chat_as_read_as_agent_scheme),
    _wrap_tool(sd.set_chat_typing_status_as_agent_scheme),
    _wrap_tool(sd.leave_chat_as_agent_scheme),
    _wrap_tool(sd.archive_chat_as_agent_scheme),
    _wrap_tool(sd.unarchive_tg_chat_as_agent_scheme),
    _wrap_tool(sd.search_chat_messages_as_agent_scheme),

    # Работа с каналами
    _wrap_tool(sd.search_telegram_channels_as_agent_scheme),
    _wrap_tool(sd.get_channel_posts_as_agent_scheme),
    _wrap_tool(sd.get_post_comments_as_agent_scheme),
    _wrap_tool(sd.join_telegram_channel_as_agent_scheme),
    _wrap_tool(sd.comment_on_post_as_agent_scheme),
    _wrap_tool(sd.create_channel_post_as_agent_scheme),
    _wrap_tool(sd.create_telegram_channel_as_agent_scheme),
    _wrap_tool(sd.update_channel_info_as_agent_scheme),
    _wrap_tool(sd.set_channel_username_as_agent_scheme),
    _wrap_tool(sd.promote_user_to_admin_as_agent_scheme),
    _wrap_tool(sd.create_discussion_group_as_agent_scheme),
    _wrap_tool(sd.get_chat_admins_as_agent_scheme),

    # Работа с группами
    _wrap_tool(sd.create_supergroup_as_agent_scheme),

    # Работа с подписчиками
    _wrap_tool(sd.get_channel_subscribers_as_agent_scheme),
    _wrap_tool(sd.check_user_in_chat_as_agent_scheme),

    # Работа с опросами
    _wrap_tool(sd.create_poll_as_agent_scheme),
    _wrap_tool(sd.get_poll_results_as_agent_scheme),
    _wrap_tool(sd.vote_in_poll_as_agent_scheme),

    # Изменение статуса/Bio
    _wrap_tool(sd.change_my_bio_as_agent_scheme),

    # Работа с ЧС/банами
    _wrap_tool(sd.ban_user_as_agent_scheme),
    _wrap_tool(sd.unban_user_as_agent_scheme),
    _wrap_tool(sd.get_banned_users_as_agent_scheme),

    # Стикеры
    _wrap_tool(sd.save_sticker_pack_as_agent_scheme),
    _wrap_tool(sd.send_tg_sticker_as_agent_scheme),

    # Свой аккаунт
    _wrap_tool(sd.change_tg_avatar_as_agent_scheme),
    _wrap_tool(sd.change_account_name_as_agent_scheme),
    _wrap_tool(sd.change_account_username_as_agent_scheme),
    _wrap_tool(sd.invite_user_to_chat_as_agent_scheme),
    _wrap_tool(sd.add_user_to_contacts_as_agent_scheme),


    # =========================================================
    # PC Control
    # =========================================================

    _wrap_tool(sd.print_to_terminal_scheme),
    _wrap_tool(sd.list_local_directory_scheme),
    _wrap_tool(sd.read_local_system_file_scheme),
    _wrap_tool(sd.get_system_architecture_map_scheme),
    _wrap_tool(sd.clean_temp_workspace_scheme),
    _wrap_tool(sd.write_local_file_scheme),
    _wrap_tool(sd.read_sandbox_file_scheme),

    # =========================================================
    # SYSTEM
    # =========================================================

    _wrap_tool(sd.change_proactivity_interval_scheme),
    _wrap_tool(sd.change_thoughts_interval_scheme),
    _wrap_tool(sd.read_recent_logs_scheme),
    _wrap_tool(sd.shutdown_system_scheme),
    _wrap_tool(sd.change_llm_model_scheme),


    # =========================================================
    # Internet
    # =========================================================

    _wrap_tool(sd.web_search_scheme),
    _wrap_tool(sd.read_webpage_scheme),
    _wrap_tool(sd.get_habr_articles_scheme),
    _wrap_tool(sd.get_habr_news_scheme),
    _wrap_tool(sd.deep_research_scheme),


    # =========================================================
    # Memory Manager
    # =========================================================

    _wrap_tool(sd.recall_memory_scheme),
    _wrap_tool(sd.memorize_information_scheme),
    _wrap_tool(sd.forget_information_scheme),
    _wrap_tool(sd.manage_entity_scheme),
    _wrap_tool(sd.manage_task_scheme),
    _wrap_tool(sd.deep_history_search_scheme),
    _wrap_tool(sd.get_chronicle_timeline_scheme),
    _wrap_tool(sd.get_all_vector_memory_scheme),


    # =========================================================
    # PERSONALITY PARAMETERS
    # =========================================================

    _wrap_tool(sd.manage_personality_scheme),


    # =========================================================
    # GRAPH DATABASE
    # =========================================================

    _wrap_tool(sd.manage_graph_scheme),
    _wrap_tool(sd.explore_graph_scheme),
    _wrap_tool(sd.get_full_graph_scheme),
    _wrap_tool(sd.delete_from_graph_scheme),


    # =========================================================
    # SWARM MANAGEMENT
    # =========================================================

    _wrap_tool(sd.spawn_subagent_scheme),
    _wrap_tool(sd.kill_subagent_scheme),
    _wrap_tool(sd.update_subagent_scheme),

    # =========================================================
    # SANDBOX MANAGEMENT
    # =========================================================

    _wrap_tool(sd.execute_python_script_scheme),
    _wrap_tool(sd.start_background_python_script_scheme),
    _wrap_tool(sd.kill_background_python_script_scheme),
    _wrap_tool(sd._get_running_python_scripts_scheme),
    _wrap_tool(sd.delete_sandbox_file_scheme),

]


# Маппинг строковых имен из Gemini на реальные функции Python
skills_registry = {
    
    # =========================================================
    # Telegram Telethon
    # =========================================================

    # Работа сообщениями
    "send_message_as_agent": skills.send_message_as_agent,
    "reply_to_message_as_agent": skills.reply_to_message_as_agent,
    "delete_message_as_agent": skills.delete_message_as_agent,
    "forward_message_as_agent": skills.forward_message_as_agent,
    "edit_message_as_agent": skills.edit_message_as_agent,
    "pin_message_as_agent": skills.pin_message_as_agent,

    # Медиа (изображение, аудио, видео, файлы)
    "get_tg_media_as_agent": skills.get_tg_media_as_agent,
    "send_voice_message_as_agent": skills.send_voice_message_as_agent,
    "send_file_to_tg_chat_as_agent": skills.send_file_to_tg_chat_as_agent,
    "download_file_from_tg_as_agent": skills.download_file_from_tg_as_agent,
    "change_channel_avatar_as_agent": skills.change_channel_avatar_as_agent,

    # Реакции
    "set_message_reaction_as_agent": skills.set_message_reaction_as_agent,

    # Чаты
    "read_chat_as_agent": skills.read_chat_as_agent,
    "get_dialogs_as_agent": skills.get_dialogs_as_agent,
    "get_chat_info_as_agent": skills.get_chat_info_as_agent,
    "mark_chat_as_read_as_agent": skills.mark_chat_as_read_as_agent,
    "set_chat_typing_status_as_agent": skills.set_chat_typing_status_as_agent,
    "leave_chat_as_agent": skills.leave_chat_as_agent,
    "archive_chat_as_agent": skills.archive_chat_as_agent,
    "unarchive_tg_chat_as_agent": skills.unarchive_tg_chat_as_agent,
    "search_chat_messages_as_agent": skills.search_chat_messages_as_agent,

    # Работа с каналами
    "get_channel_posts_as_agent": skills.get_channel_posts_as_agent,
    "search_telegram_channels_as_agent": skills.search_telegram_channels_as_agent,
    "join_telegram_channel_as_agent": skills.join_telegram_channel_as_agent,
    "comment_on_post_as_agent": skills.comment_on_post_as_agent,
    "get_post_comments_as_agent": skills.get_post_comments_as_agent,
    "create_channel_post_as_agent": skills.create_channel_post_as_agent,
    "create_telegram_channel_as_agent": skills.create_telegram_channel_as_agent,
    "update_channel_info_as_agent": skills.update_channel_info_as_agent,
    "set_channel_username_as_agent": skills.set_channel_username_as_agent,
    "promote_user_to_admin_as_agent": skills.promote_user_to_admin_as_agent,
    "create_discussion_group_as_agent": skills.create_discussion_group_as_agent,
    "get_chat_admins_as_agent": skills.get_chat_admins_as_agent,

    # Работа с группами
    "create_supergroup_as_agent": skills.create_supergroup_as_agent,

    # Работа с подписчиками
    "get_channel_subscribers_as_agent": skills.get_channel_subscribers_as_agent,
    "check_user_in_chat_as_agent": skills.check_user_in_chat_as_agent,

    # Работа с опросами
    "create_poll_as_agent": skills.create_poll_as_agent,
    "get_poll_results_as_agent": skills.get_poll_results_as_agent,
    "vote_in_poll_as_agent": skills.vote_in_poll_as_agent,
    
    # Изменение статуса/Bio
    "change_my_bio_as_agent": skills.change_my_bio_as_agent,

    # Работа с ЧС/банами
    "ban_user_as_agent": skills.ban_user_as_agent,
    "unban_user_as_agent": skills.unban_user_as_agent,
    "get_banned_users_as_agent": skills.get_banned_users_as_agent,

    # Стикеры
    "save_sticker_pack_as_agent": skills.save_sticker_pack_as_agent,
    "send_tg_sticker_as_agent": skills.send_tg_sticker_as_agent,

    # Свой аккаунт
    "change_tg_avatar_as_agent": skills.change_tg_avatar_as_agent,
    "change_account_name_as_agent": skills.change_account_name_as_agent,
    "change_account_username_as_agent": skills.change_account_username_as_agent,
    "invite_user_to_chat_as_agent": skills.invite_user_to_chat_as_agent,
    "add_user_to_contacts_as_agent": skills.add_user_to_contacts_as_agent,


    # =========================================================
    # PC Control
    # =========================================================

    "print_to_terminal": skills.print_to_terminal,
    "list_local_directory": skills.list_local_directory,
    "read_local_system_file": skills.read_local_system_file,
    "get_system_architecture_map": skills.get_system_architecture_map,
    "clean_temp_workspace": skills.clean_temp_workspace,
    "write_local_file": skills.write_local_file,
    "read_sandbox_file": skills.read_sandbox_file,


    # =========================================================
    # SYSTEM
    # =========================================================

    "change_proactivity_interval": skills.change_proactivity_interval,
    "change_thoughts_interval": skills.change_thoughts_interval,
    "read_recent_logs": skills.read_recent_logs,
    "shutdown_system": skills.shutdown_system,
    "change_llm_model": skills.change_llm_model,
    

    # =========================================================
    # Internet
    # =========================================================

    "web_search": skills.web_search,
    "read_webpage": skills.read_webpage,
    "get_habr_articles": skills.get_habr_articles,
    "get_habr_news": skills.get_habr_news,
    "deep_research": composite_skills.deep_research,


    # =========================================================
    # Memory Manager
    # =========================================================

    "recall_memory": skills.recall_memory,
    "memorize_information": skills.memorize_information,
    "forget_information": skills.forget_information,
    "manage_entity": skills.manage_entity,
    "manage_task": skills.manage_task,
    "deep_history_search": skills.deep_history_search,
    "get_chronicle_timeline": skills.get_chronicle_timeline,
    "get_all_vector_memory": skills.get_all_vector_memory,


    # =========================================================
    # PERSONALITY PARAMETERS
    # =========================================================

    "manage_personality": skills.manage_personality,


    # =====================================================================
    # GRAPH DATABASE (Нейронная сеть связей)
    # =====================================================================
    
    "manage_graph": skills.manage_graph_db,
    "explore_graph": skills.explore_graph_db,
    "get_full_graph": skills.get_full_graph_db,
    "delete_from_graph": skills.delete_from_graph_db,


    # =========================================================
    # SWARM MANAGEMENT
    # =========================================================

    "spawn_subagent": skills.spawn_subagent,
    "kill_subagent": skills.kill_subagent,
    "update_subagent": skills.update_subagent,


    # =========================================================
    # SANDBOX MANAGEMENT (Песочница)
    # =========================================================

    "_execute_python_script": skills.execute_python_script,
    "start_background_python_script": skills.start_background_python_script,
    "kill_background_python_script": skills.kill_background_python_script,
    "_get_running_python_scripts": skills._get_running_python_scripts,
    "delete_sandbox_file": skills.delete_sandbox_file,

}
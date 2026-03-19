def clean_peer_id(chat_id: str | int) -> str | int:
    """Конвертирует ID, очищает @username и вытаскивает юзернейм из ссылок t.me"""
    if isinstance(chat_id, int):
        return chat_id
        
    chat_id = chat_id.strip()
    
    # Защита от дурака (нейросети): Агент передал ссылку
    if "t.me/" in chat_id:
        chat_id = chat_id.split("t.me/")[-1].split("/")[0].split("?")[0]
        
    # Если это юзернейм с собачкой - убираем её
    if chat_id.startswith("@"):
        chat_id = chat_id[1:]
        
    # Если это просто цифры (возможно с минусом) - конвертируем в int
    if chat_id.lstrip('-').isdigit():
        return int(chat_id)
        
    return chat_id

def _get_content(msg):
    """Вспомогательная функция для парсинга медиа/текста/пересылок и системных действий"""
    
    # Проверяем, переслано ли сообщение
    fwd_prefix = ""
    if msg.fwd_from:
        if msg.fwd_from.from_name:
            fwd_prefix = f"[Переслано от: {msg.fwd_from.from_name}] "
        else:
            fwd_prefix = "[Переслано] "

    content = ""
    
    # Сначала проверяем системные действия (вступление, выход, закрепление и т.д.)
    if msg.action:
        action_type = type(msg.action).__name__
        if action_type in ['MessageActionChatAddUser', 'MessageActionChatJoinedByLink']:
            content = "[Системное сообщение: Пользователь присоединился к чату]"
        elif action_type == 'MessageActionChatDeleteUser':
            content = "[Системное сообщение: Пользователь покинул чат / был исключен]"
        elif action_type == 'MessageActionPinMessage':
            content = "[Системное сообщение: Сообщение закреплено]"
        else:
            content = f"[Служебное действие: {action_type}]"
            
    # Если это обычное сообщение
    elif msg.text: 
        content = msg.text.replace('\n', ' ')
    elif msg.poll:
        question = getattr(msg.poll.poll.question, 'text', str(msg.poll.poll.question))
        content = f"[Опрос: {question}]"
    elif msg.photo: 
        content = "[Фото]"
    elif msg.video: 
        content = "[Видео]"
    elif msg.voice: 
        content = "[Голосовое сообщение]"
    elif msg.audio: 
        content = "[Аудиозапись]"
    elif msg.sticker: 
        content = "[Стикер]"
    elif msg.gif: 
        content = "[GIF]"
    elif msg.document: 
        content = f"[Файл: {msg.file.name or 'без названия'}]"
    else:
        content = "[Неизвестный формат/Медиа]"
        
    return fwd_prefix + content
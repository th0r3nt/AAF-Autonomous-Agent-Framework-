import json
import socket
import uuid
from src.layer00_utils.env_manager import AGENT_NAME
from src.layer00_utils.workspace import workspace_manager
from src.layer00_utils.sandbox_env.executor import execute_once
from src.layer03_brain.agent.skills.auto_schema import llm_skill

@llm_skill(
    description="Универсальный HTTP-клиент. Выполняет безопасный запрос из изолированной песочницы. Позволяет парсить API, отправлять данные и взаимодействовать с микросервисами. Важно: для доступа к внутренним микросервисам - использовать их имена.",
    parameters={
        "method": {"description": "HTTP метод", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"]},
        "url": "Полный URL (например, https://api.github.com/users).",
        "headers": "(Опционально) Словарь заголовков. Например: {'Authorization': 'Bearer 123', 'Content-Type': 'application/json'}",
        "json_body": "(Опционально) Словарь с телом запроса для POST/PUT.",
        "json_path_filter": "(Опционально) Строка с ключами для фильтрации большого ответа (например, 'items.0.name'). Спасает контекст от переполнения."
    }
)
async def send_request(method: str, url: str, headers: dict = None, json_body: dict = None, json_path_filter: str = None) -> str:
    headers = headers or {}
    
    # 1. Формируем безопасный JSON-пакет данных для проброса в скрипт
    # Мы используем json.dumps(), чтобы Python сам экранировал все кавычки и переносы
    request_payload = json.dumps({
        "url": url,
        "method": method.upper(),
        "headers": headers,
        "body": json_body,
        "filter": json_path_filter
    }, ensure_ascii=False)

    # 2. Генерируем код скрипта для выполнения в песочнице
    # Скрипт использует только встроенные библиотеки urllib и json, чтобы не зависеть от pip
    script_code = f"""
import urllib.request
import json
import ssl
import sys

# Распаковка проброшенных данных
payload = json.loads('''{request_payload}''')

url = payload['url']
method = payload['method']
headers = payload['headers']
body = payload['body']
json_filter = payload['filter']

if body and not any(k.lower() == 'content-type' for k in headers.keys()):
    headers['Content-Type'] = 'application/json'

data = json.dumps(body).encode('utf-8') if body else None

# Отключаем проверку SSL на случай внутренних кривых сертификатов
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(url, data=data, headers=headers, method=method)

try:
    with urllib.request.urlopen(req, context=ctx, timeout=25) as response:
        resp_body = response.read().decode('utf-8', errors='replace')
        status = response.status
except urllib.error.HTTPError as e:
    resp_body = e.read().decode('utf-8', errors='replace')
    status = e.code
except Exception as e:
    print(f"Connection Error: {{e}}")
    sys.exit(1)

# Логика фильтрации (JSON Path)
if json_filter and resp_body.strip().startswith(('{{', '[')):
    try:
        parsed = json.loads(resp_body)
        keys = json_filter.split('.')
        for k in keys:
            if isinstance(parsed, dict) and k in parsed:
                parsed = parsed[k]
            elif isinstance(parsed, list) and k.isdigit() and int(k) < len(parsed):
                parsed = parsed[int(k)]
            else:
                parsed = f"[Фильтр не нашел ключ/индекс: '{{k}}']"
                break
        print(f"Status: {{status}}\\nFiltered Response:\\n{{json.dumps(parsed, indent=2, ensure_ascii=False)}}")
    except Exception as e:
        print(f"Status: {{status}}\\nError applying json_path_filter: {{e}}\\nRaw Response:\\n{{resp_body}}")
else:
    print(f"Status: {{status}}\\nResponse:\\n{{resp_body}}")
"""
    # 3. Сохраняем скрипт во временный файл песочницы
    temp_filename = f"http_req_{uuid.uuid4().hex[:6]}.py"
    temp_vfs_path = f"temp/{temp_filename}"
    temp_abs_path = workspace_manager.resolve_vfs_path(temp_vfs_path, mode='write')
    
    try:
        temp_abs_path.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_abs_path, 'w', encoding='utf-8') as f:
            f.write(script_code.strip())
            
        # 4. Выполняем скрипт в изолированном контейнере
        result = await execute_once(temp_vfs_path, timeout=35)
        
        # 5. Зачищаем за собой
        if temp_abs_path.exists():
            temp_abs_path.unlink()
            
        return result
        
    except Exception as e:
        return f"Системная ошибка выполнения HTTP-запроса: {e}"


@llm_skill(
    description="Генерирует уникальный URL (вебхук), который можно передать внешним сервисам. Когда внешний сервис отправит данные - опубликуется входящее событие.",
    parameters={
        "topic_name": "Уникальное имя для вебхука (только латиница и '_', например: 'payment_callback_123')."
    }
)
async def generate_webhook(topic_name: str) -> str:
    agent_alias = f"agent_{AGENT_NAME.lower()}"
    try:
        agent_ip = socket.gethostbyname(agent_alias)
    except Exception:
        agent_ip = agent_alias # Фоллбэк на алиас

    # 18790 - порт нашего sandbox_listener
    url = f"http://{agent_ip}:18790/webhook/{topic_name}"
    return f"Вебхук успешно сгенерирован: {url}\nПередай этот URL целевому сервису. Когда данные придут, они будут доставлены тебе в виде системного прерывания (уровень HIGH)."
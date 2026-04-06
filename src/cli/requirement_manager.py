import sys
import subprocess
import importlib.util

# Словарь: "имя_модуля_в_коде": "имя_пакета_в_pip"
CLI_DEPENDENCIES = {
    "typer": "typer",
    "rich": "rich",
    "dotenv": "python-dotenv",
    "yaml": "pyyaml",
    "docker": "docker", # Добавим docker, так как мы импортируем его для чтения логов
    "questionary": "questionary"
}

def check_and_install_dependencies():
    """
    Проверяет наличие базовых библиотек для работы CLI лаунчера.
    Использует только стандартную библиотеку Python.
    """
    missing_packages = []
    
    for module_name, pip_name in CLI_DEPENDENCIES.items():
        # importlib.util.find_spec проверяет наличие модуля без его фактического импорта
        if importlib.util.find_spec(module_name) is None:
            missing_packages.append(pip_name)
            
    if missing_packages:
        print("\n[AAF Bootstrapper] Обнаружено отсутствие базовых библиотек для запуска.")
        print(f"[AAF Bootstrapper] Установка: {', '.join(missing_packages)}\n")
        
        try:
            # Запускаем pip install через текущий интерпретатор
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", *missing_packages],
                stdout=sys.stdout,
                stderr=sys.stderr
            )
            print("\n[AAF Bootstrapper] ✔ Библиотеки успешно установлены.\n")
            
            # Сбрасываем кэш импортов, чтобы интерпретатор увидел новые библиотеки
            importlib.invalidate_caches()
            
        except subprocess.CalledProcessError as e:
            print(f"\n[AAF Bootstrapper] ✖ Ошибка автоматической установки (Код: {e.returncode}).")
            print("Пожалуйста, установите их вручную командой:\n")
            print(f"pip install {' '.join(missing_packages)}\n")
            sys.exit(1)
        except Exception as e:
            print(f"\n[AAF Bootstrapper] ✖ Непредвиденная ошибка: {e}")
            sys.exit(1)
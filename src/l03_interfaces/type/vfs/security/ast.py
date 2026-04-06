import ast
import traceback
from src.l00_utils.managers.logger import system_logger


class ASTValidator:
    """
    Анализатор абстрактных синтаксических деревьев (AST).
    Защищает фреймворк от синтаксического суицида при изменении кода агентом.
    """

    @staticmethod
    def validate_python_syntax(code_string: str) -> tuple[bool, str]:
        """
        Прогоняет код через парсер Python.
        Возвращает кортеж: (Успешно ли, Текст ошибки для LLM).
        """
        try:
            # Пытаемся построить AST-дерево. Если код кривой, вылетит SyntaxError
            ast.parse(code_string)
            return True, "Syntax OK"

        except SyntaxError as e:
            # Вытаскиваем красивый трейсбек (где конкретно агент забыл скобку),
            # чтобы потом вернуть это прямо в контекст LLM.
            error_msg = "".join(traceback.format_exception_only(type(e), e)).strip()
            system_logger.warning(
                f"[AST Validator] Заблокировано сохранение из-за синтаксической ошибки:\n{error_msg}"
            )

            return False, f"SyntaxError: {error_msg}"

    @staticmethod
    def censor_system_calls(code_string: str) -> tuple[bool, str]:
        """
        Опциональная защита (для уровня 3: god_mode).
        Ищет откровенно разрушительные системные команды даже если синтаксис верен.
        """
        try:
            tree = ast.parse(code_string)
        except SyntaxError:
            return False, "Синтаксическая ошибка. Проверка безопасности невозможна."

        for node in ast.walk(tree):
            # Ищем вызовы функций: shutil.rmtree('/', C:\)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    module_name = node.func.value.id
                    func_name = node.func.attr

                    if module_name == "shutil" and func_name == "rmtree":
                        # Если аргумент — это корень диска
                        for arg in node.args:
                            if isinstance(arg, ast.Constant) and str(arg.value).strip() in [
                                "/",
                                "C:\\",
                                "C:/",
                            ]:
                                msg = "SECURITY WARNING: Попытка удаления корневой директории диска заблокирована."
                                system_logger.error(f"[AST Validator] {msg}")
                                return False, msg

                    # Здесь в будущем можно добавить запрет на os.system, если посчитаем нужным
                    # Но пока оставим свободу

        return True, "Safety check passed"

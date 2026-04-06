from src.l00_utils.managers.logger import system_logger
from collections import deque


class TokenTracker:
    def __init__(self, maxlen=100):
        self.input_history = deque(maxlen=maxlen)
        self.output_history = deque(maxlen=maxlen)

    def add_input_record(
        self,
        cycle_type: str,
        prompt_tokens: int,
        context_tokens: int,
        tools_tokens: int = 0,
    ) -> str:
        """Записывает входящие токены текущего цикла"""
        total = prompt_tokens + context_tokens + tools_tokens
        self.input_history.append({"type": cycle_type, "total": total})

        tokens = f"Input tokens: {total} (prompt: {prompt_tokens}, context: {context_tokens}, tools: {tools_tokens})."
        system_logger.info(tokens)
        return tokens

    def add_output_record(self, cycle_type: str, tokens: int) -> str:
        """Записывает исходящие (сгенерированные) токены текущего цикла"""
        self.output_history.append({"type": cycle_type, "total": tokens})

        result = f"Output tokens: {tokens}."
        system_logger.info(result)
        return result

    def get_token_statistics(self) -> str:
        """Возвращает статистику входящих и исходящих токенов"""
        stats_lines = []

        # Подсчет Input токенов
        if self.input_history:
            total_in = sum(item["total"] for item in self.input_history)
            avg_in = total_in // len(self.input_history)
            stats_lines.append(
                f"Input: Over the last {len(self.input_history)} API calls: {total_in} tokens (average {avg_in}/call)."
            )
        else:
            stats_lines.append("Input: No data yet.")

        # Подсчет Output токенов
        if self.output_history:
            total_out = sum(item["total"] for item in self.output_history)
            avg_out = total_out // len(self.output_history)
            stats_lines.append(
                f"Output: Over the last {len(self.output_history)} API calls: {total_out} tokens (average {avg_out}/call)."
            )
        else:
            stats_lines.append("Output: No data yet.")

        return "\n".join(stats_lines)

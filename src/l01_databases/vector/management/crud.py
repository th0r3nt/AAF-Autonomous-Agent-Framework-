from datetime import datetime
import uuid
from src.l00_utils.managers.logger import system_logger
from src.l00_utils.managers.config import settings


class VectorCollectionCRUD:
    def __init__(self, collection, similarity_threshhold: float):
        self.collection = collection
        self.similarity_threshhold = similarity_threshhold or settings.memory.similarity_threshold

    # ==========================================
    # 🟢 CREATE
    # ==========================================

    def add_new_entry(self, text: str) -> str:
        """
        Добавляет запись в коллекцию базы данных с уникальным ID и текущей датой в метаданных.
        """
        try:
            current_date = datetime.now().strftime("%d.%m.%Y %H:%M")
            record_id = str(uuid.uuid4())
            metadata = {"creation_date": current_date}

            self.collection.add(documents=[text], ids=[record_id], metadatas=[metadata])
            system_logger.debug(
                f"[Vector DB] Новая запись добавлена (коллекция: {self.collection.name}): '{text}'"
            )
            return (
                f"[Vector DB] Новая запись добавлена (коллекция: {self.collection.name}): '{text}'"
            )
        except Exception as e:
            system_logger.error(f"[Vector DB] Ошибка при добавлении записи: {e}")
            return f"[Vector DB] Ошибка при добавлении записи: {e}"

    # ==========================================
    # 🔵 READ
    # ==========================================

    def find_entries(self, query: str) -> str:
        """
        Ищет записи в коллекции базы данных по запросу и возвращает отформатированные результаты.
        """
        try:
            if self.collection.count() == 0:
                system_logger.debug(
                    f"[Vector DB] Коллекция {self.collection.name} пуста. Поиск отменен."
                )
                return f"[Vector DB] В коллекции {self.collection.name} ничего не найдено."

            limit = settings.memory.vector_rag.max_results

            results = self.collection.query(query_texts=[query], n_results=limit)

            # Собираем данные в удобный список словарей или строк
            formatted_results = []

            system_logger.debug(
                f"[Vector DB] Поиск записей (коллекция: {self.collection.name}) по запросу '{query}'..."
            )

            # Проходимся по результатам (индекс [0], так как запрос один)
            for i in range(len(results["documents"][0])):
                text = results["documents"][0][i]
                date = results["metadatas"][0][i]["creation_date"]
                distance = results["distances"][0][i]
                id = results["ids"][0][i]

                if (
                    distance <= self.similarity_threshhold
                ):  # Если записи близки (например, если расстояние равно ~0.5403) - добавляем
                    formatted_results.append(
                        f"ID: '{id}' | [{date}] (схожесть: {distance:.4f}): {text}"
                    )

                # else:
                # system_logger.debug(f"Запись недостаточно релевантна (схожесть: {distance:.4f}). Содержание записи: {text} ")

            result = "\n".join(formatted_results)

            if formatted_results:  # Проверяем, что список не пуст
                # Логируем только первые 200 символов, чтобы не забить лог
                display_result = (result[:200] + "...") if len(result) > 200 else result
                system_logger.debug(f"Найденные записи в {self.collection.name}: {display_result}")
                return result
            else:
                system_logger.debug(
                    f"[Vector DB] В коллекции {self.collection.name} ничего не найдено."
                )
                return f"[Vector DB] В коллекции {self.collection.name} ничего не найдено."

        except Exception as e:
            system_logger.error(
                f"[Vector DB] Ошибка при поиске записей (коллекция: {self.collection.name}): {e}"
            )
            return f"[Vector DB] Ошибка при поиске записей (коллекция: {self.collection.name}): {e}"

    def get_all_entries(self) -> str:
        """
        Возвращает все существующие записи в коллекции базы данных.
        Формат: список словарей с id, текстом и метаданными.
        """
        try:
            results = self.collection.get()  # Метод get() без параметров возвращает всё

            all_entries = []

            for i in range(len(results["ids"])):
                id = results["ids"][i]
                text = results["documents"][i]
                metadata = results["metadatas"][i]

                all_entries.append(f"ID: {id} | [{metadata}]: {text}")

            result = "\n".join(all_entries)
            system_logger.debug(
                f"[Vector DB] Все записи (коллекция: {self.collection.name}): \n{result}"
            )
            return result
        except Exception as e:
            system_logger.error(
                f"[Vector DB] Ошибка при получении всех записей (коллекция: {self.collection.name}): {e}"
            )
            return f"[Vector DB] Ошибка при получении всех записей (коллекция: {self.collection.name}): {e}"

    # ==========================================
    # 🟡 UPDATE
    # ==========================================

    def update_entry(self, entry_id: str, new_text: str) -> str:
        """
        Обновляет содержимое существующей записи по её ID.
        """
        try:
            # Проверяем, существует ли запись
            existing = self.collection.get(ids=[entry_id])
            if not existing["ids"]:
                return f"[Vector DB] Запись с ID '{entry_id}' не найдена в коллекции '{self.collection.name}'."

            # Оставляем старые метаданные, но добавляем пометку об обновлении
            metadata = existing["metadatas"][0]
            metadata["updated_date"] = datetime.now().strftime("%d.%m.%Y %H:%M")

            self.collection.update(ids=[entry_id], documents=[new_text], metadatas=[metadata])

            msg = (
                f"[Vector DB] Запись '{entry_id}' успешно обновлена. Новое содержание: '{new_text}'"
            )
            system_logger.debug(msg)
            return msg

        except Exception as e:
            error_msg = f"[Vector DB] Ошибка при обновлении записи '{entry_id}': {e}"
            system_logger.error(error_msg)
            return error_msg

    # ==========================================
    # 🔴 DELETE
    # ==========================================

    def delete_entries(self, ids_list: list) -> str:
        """
        Принимает список ID, извлекает их данные для отчета и удаляет из коллекции базы данных.
        """
        if not ids_list:
            return "Список ID пуст, ничего не удалено."

        try:
            records_to_delete = self.collection.get(
                ids=ids_list
            )  # Получаем данные записей перед удалением

            if not records_to_delete["ids"]:
                return f"[Vector DB] Записи с указанными ID не найдены (коллекция: {self.collection.name})."

            # Формируем список строк с описанием каждой записи
            deleted_details = []
            for i in range(len(records_to_delete["ids"])):
                record_id = records_to_delete["ids"][i]
                text = records_to_delete["documents"][i]
                date = records_to_delete["metadatas"][i].get("creation_date", "Дата неизвестна")

                deleted_details.append(f"ID: {record_id} | [{date}]: {text}")

            self.collection.delete(ids=ids_list)

            report = (
                f"[Vector DB] Успешно удаленные записи (коллекция: {self.collection.name}):\n"
                + "\n".join(deleted_details)
            )
            system_logger.debug(report)
            return report

        except Exception as e:
            system_logger.error(
                f"[Vector DB] Ошибка при удалении записей (коллекция: {self.collection.name}): {e}"
            )
            return (
                f"[Vector DB] Ошибка при удалении записей (коллекция: {self.collection.name}): {e}"
            )

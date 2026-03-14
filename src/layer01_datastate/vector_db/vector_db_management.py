from datetime import datetime
import uuid
from src.layer00_utils.logger import system_logger
from src.layer00_utils.watchdog.watchdog import vector_db_module
from src.layer00_utils.watchdog.watchdog_decorator import watchdog_decorator
from src.layer00_utils.config_manager import config

from src.layer01_datastate.vector_db.vector_db import _get_col

SIMILARITY_THRESHOLD = config.memory.similarity_threshold

@watchdog_decorator(vector_db_module)
def add_new_entry_in_vector_db(collection_name, text: str) -> str:
    """Добавляет запись в коллекцию базы данных с уникальным ID и текущей датой в метаданных"""
    try:
        # ДОБАВЛЕНО ВРЕМЯ %H:%M
        current_date = datetime.now().strftime("%d.%m.%Y %H:%M") 
        record_id = str(uuid.uuid4()) # Генерируем уникальный ID для записи
        
        metadata = {"creation_date": current_date}
        
        collection = _get_col(collection_name)

        collection.add(
            documents=[text], 
            ids=[record_id], 
            metadatas=[metadata]
        )
        system_logger.debug(f"[Vector DB] Новая запись добавлена (коллекция: {collection.name}): '{text}'")
        return f"[Vector DB] Новая запись добавлена (коллекция: {collection.name}): '{text}'"
    except Exception as e:
        system_logger.error(f"[Vector DB] Ошибка при добавлении записи: {e}")
        return f"[Vector DB] Ошибка при добавлении записи: {e}"

@watchdog_decorator(vector_db_module)
def find_entries_in_vector_db(collection_name, query: str) -> str:
    """Ищет записи в коллекции базы данных по запросу и возвращает отформатированные результаты"""
    try:
        collection = _get_col(collection_name)

        if collection.count() == 0:
            system_logger.debug(f"[Vector DB] Коллекция {collection.name} пуста. Поиск отменен.")
            return f"[Vector DB] В коллекции {collection.name} ничего не найдено."
        
        results = collection.query(
            query_texts=[query], 
            n_results=5
        )
        
        # Собираем данные в удобный список словарей или строк
        formatted_results = []

        system_logger.debug(f"[Vector DB] Поиск записей (коллекция: {collection.name}) по запросу '{query}'...")
        
        # Проходимся по результатам (индекс [0], так как запрос один)
        for i in range(len(results['documents'][0])):
            text = results['documents'][0][i]
            date = results['metadatas'][0][i]['creation_date']
            distance = results['distances'][0][i]
            id = results['ids'][0][i]

            if distance <= SIMILARITY_THRESHOLD: # Если записи близки (например, если расстояние равно ~0.5403) - добавляем
                formatted_results.append(f"ID: '{id}' | [{date}] (схожесть: {distance:.4f}): {text}")

            # else:
                # system_logger.debug(f"Запись недостаточно релевантна (схожесть: {distance:.4f}). Содержание записи: {text} ")

        result = "\n".join(formatted_results)
        
        if formatted_results: # Проверяем, что список не пуст
            # Логируем только первые 200 символов, чтобы не забить лог
            display_result = (result[:200] + '...') if len(result) > 200 else result
            system_logger.debug(f"Найденные записи в {collection.name}: {display_result}")
            return result
        else:
            system_logger.debug(f"[Vector DB] В коллекции {collection.name} ничего не найдено.")
            return f"[Vector DB] В коллекции {collection.name} ничего не найдено."
    
    except Exception as e:
        system_logger.error(f"[Vector DB] Ошибка при поиске записей (коллекция: {collection.name}): {e}")
        return f"[Vector DB] Ошибка при поиске записей (коллекция: {collection.name}): {e}"

@watchdog_decorator(vector_db_module)
def get_all_entries_in_vector_db(collection_name) -> str:
    """Возвращает все существующие записи в коллекции базы данных. Формат: список словарей с id, текстом и метаданными."""
    try:
        collection = _get_col(collection_name)
        results = collection.get()  # Метод get() без параметров возвращает всё
        
        all_entries = []

        for i in range(len(results['ids'])):
            id = results['ids'][i]
            text = results['documents'][i]
            metadata = results['metadatas'][i]

            all_entries.append(f"ID: {id} | [{metadata}]: {text}")

        result = "\n".join(all_entries)
        system_logger.debug(f"[Vector DB] Все записи (коллекция: {collection.name}): \n{result}")
        return result
    except Exception as e:
        system_logger.error(f"[Vector DB] Ошибка при получении всех записей (коллекция: {collection.name}): {e}")
        return f"[Vector DB] Ошибка при получении всех записей (коллекция: {collection.name}): {e}"

@watchdog_decorator(vector_db_module)
def update_entry_in_vector_db(collection_name: str, entry_id: str, new_text: str) -> str:
    """Обновляет содержимое существующей записи по её ID"""
    try:
        collection = _get_col(collection_name)
        
        # Проверяем, существует ли запись
        existing = collection.get(ids=[entry_id])
        if not existing['ids']:
            return f"[Vector DB] Запись с ID '{entry_id}' не найдена в коллекции '{collection_name}'."
        
        # Оставляем старые метаданные, но добавляем пометку об обновлении
        metadata = existing['metadatas'][0]
        metadata["updated_date"] = datetime.now().strftime("%d.%m.%Y %H:%M")
        
        collection.update(
            ids=[entry_id],
            documents=[new_text],
            metadatas=[metadata]
        )
        
        msg = f"[Vector DB] Запись '{entry_id}' успешно обновлена. Новое содержание: '{new_text}'"
        system_logger.debug(msg)
        return msg
    except Exception as e:
        error_msg = f"[Vector DB] Ошибка при обновлении записи '{entry_id}': {e}"
        system_logger.error(error_msg)
        return error_msg

@watchdog_decorator(vector_db_module)
def delete_entries_in_vector_db(collection_name, ids_list: list) -> str:
    """Принимает список ID, извлекает их данные для отчета и удаляет из коллекции базы данных."""
    if not ids_list:
        return "Список ID пуст, ничего не удалено."
    
    try:
        collection = _get_col(collection_name)
        records_to_delete = collection.get(ids=ids_list) # Получаем данные записей перед удалением
        
        if not records_to_delete['ids']:
            return f"[Vector DB] Записи с указанными ID не найдены (коллекция: {collection.name})."

        # Формируем список строк с описанием каждой записи
        deleted_details = []
        for i in range(len(records_to_delete['ids'])):
            record_id = records_to_delete['ids'][i]
            text = records_to_delete['documents'][i]
            date = records_to_delete['metadatas'][i].get('creation_date', 'Дата неизвестна')
            
            deleted_details.append(f"ID: {record_id} | [{date}]: {text}")

        collection.delete(ids=ids_list)

        report = f"[Vector DB] Успешно удаленные записи (коллекция: {collection.name}):\n" + "\n".join(deleted_details)
        system_logger.debug(report)
        return report
    
    except Exception as e:
        system_logger.error(f"[Vector DB] Ошибка при удалении записей (коллекция: {collection.name}): {e}")
        return f"[Vector DB] Ошибка при удалении записей (коллекция: {collection.name}): {e}"

# @watchdog_decorator(vector_db_module)
def delete_all_entries_in_vector_db(collection_name: str) -> str:
    """Полностью удаляет все записи из указанной коллекции"""
    try:
        collection = _get_col(collection_name)
        
        # Получаем все ID записей в коллекции
        results = collection.get()
        ids_to_delete = results['ids']

        if not ids_to_delete:
            message = f"[Vector DB] Коллекция '{collection_name}' уже пуста."
            system_logger.debug(message)
            return message

        # Удаляем записи по списку ID
        collection.delete(ids=ids_to_delete)
        
        count = len(ids_to_delete)
        report = f"[Vector DB] Успешно удалены все записи ({count} шт.) из коллекции '{collection_name}'."
        
        # Используем warning, так как это массовое удаление данных
        system_logger.warning(f"{report}") 
        return report
    
    except Exception as e:
        error_msg = f"[Vector DB] Ошибка при полной очистке коллекции '{collection_name}': {e}"
        system_logger.error(error_msg)
        return error_msg
    
@watchdog_decorator(vector_db_module)
def raw_find_entries_in_vector_db(collection_name: str, query: str, n_results: int = 5) -> list:
    """Служебная функция для MemoryManager. Возвращает сырые словари результатов для глобальной сортировки."""
    try:
        collection = _get_col(collection_name)
        if collection.count() == 0:
            return []
        
        results = collection.query(
            query_texts=[query], 
            n_results=n_results
        )
        
        output = []
        for i in range(len(results['documents'][0])):
            distance = results['distances'][0][i]
            
            if distance <= SIMILARITY_THRESHOLD:
                output.append({
                    "id": results['ids'][0][i],
                    "text": results['documents'][0][i],
                    "distance": distance,
                    "date": results['metadatas'][0][i].get('creation_date', 'Неизвестно'),
                    "collection": collection_name
                })
        return output
    except Exception as e:
        system_logger.error(f"[Vector DB] Ошибка сырого поиска (коллекция: {collection_name}): {e}")
        return []
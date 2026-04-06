import httpx
from src.l00_utils.managers.logger import system_logger
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.l03_interfaces.type.geo.client import GeoClient
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class GeoGeocoding(BaseInstrument):
    """Сервис для преобразования адресов в координаты и обратно."""

    def __init__(self, client: 'GeoClient'):
        super().__init__()  # BaseInstrument пробежится по методам ниже и закинет все @skill в ToolRegistry
        self.api = client

    @skill()
    async def text_to_coordinates(self, query: str) -> ToolResult:
        """
        Преобразует текстовый адрес (например, "Москва, Арбат" или "Эйфелева башня") в GPS координаты (широта, долгота).
        Рекомендуется всегда использовать эту функцию первой, если другие инструменты требуют координаты.
        """
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": query,
            "format": "json",
            "limit": 1,  # Берем только самый релевантный результат
            "addressdetails": 1,  # Просим разбить адрес на компоненты
        }

        try:
            response = await self.api.request("GET", url, params=params)

            if response.status_code == 200:
                data = response.json()

                if not data:
                    return ToolResult.fail(msg=f"По запросу '{query}' ничего не найдено.")

                # Берем первый (самый точный) результат
                place = data[0]
                lat = float(place.get("lat", 0.0))
                lon = float(place.get("lon", 0.0))
                display_name = place.get("display_name", "Неизвестный адрес")
                place_type = place.get("type", "unknown")

                msg = (
                    f"Результат поиска для '{query}':\n"
                    f"Широта (Lat): {lat}\n"
                    f"Долгота (Lon): {lon}\n"
                    f"Полный адрес: {display_name} (Тип: {place_type})"
                )

                system_logger.debug(f"[Geo] Геокодинг: '{query}' -> [{lat}, {lon}]")
                return ToolResult.ok(
                    msg=msg, data={"lat": lat, "lon": lon, "address": display_name}
                )

            return ToolResult.fail(
                msg=f"Ошибка геокодинга. HTTP Status: {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[Geo] Ошибка сети при геокодинге '{query}': {e}")
            return ToolResult.fail(msg=f"Ошибка сети: {e}", error=str(e))
        except Exception as e:
            return ToolResult.fail(msg=f"Критическая ошибка: {e}", error=str(e))

    @skill()
    async def coordinates_to_address(self, lat: float, lon: float) -> ToolResult:
        """
        Обратный геокодинг. Преобразует GPS координаты в понятный текстовый адрес.
        Например, переводит [55.7558, 37.6173] в "Москва, Красная площадь".
        """
        url = "https://nominatim.openstreetmap.org/reverse"
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json",
            "zoom": 18,  # Уровень детализации (18 = до здания)
            "addressdetails": 1,
        }

        try:
            response = await self.api.request("GET", url, params=params)

            if response.status_code == 200:
                data = response.json()

                if "error" in data:
                    return ToolResult.fail(
                        msg=f"Координаты [{lat}, {lon}] указывают на неизвестное место (возможно, океан)."
                    )

                display_name = data.get("display_name", "Неизвестный адрес")
                address_dict = data.get("address", {})

                # Достаем самое важное для короткой сводки
                city = (
                    address_dict.get("city")
                    or address_dict.get("town")
                    or address_dict.get("village")
                    or "Неизвестный город"
                )
                country = address_dict.get("country", "Неизвестная страна")

                msg = (
                    f"Координаты [{lat}, {lon}] находятся по адресу:\n"
                    f"{display_name}\n"
                    f"(Город: {city}, Страна: {country})"
                )

                system_logger.debug(f"[Geo] Обратный геокодинг: [{lat}, {lon}] -> {city}")
                return ToolResult.ok(msg=msg, data=data)

            return ToolResult.fail(
                msg=f"Ошибка обратного геокодинга. HTTP Status: {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[Geo] Ошибка сети при обратном геокодинге [{lat}, {lon}]: {e}")
            return ToolResult.fail(msg=f"Ошибка сети: {e}", error=str(e))
        except Exception as e:
            return ToolResult.fail(msg=f"Критическая ошибка: {e}", error=str(e))

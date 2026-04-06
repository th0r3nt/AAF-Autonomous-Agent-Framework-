import math
import httpx
from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.geo.client import GeoClient
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class GeoPlaces(BaseInstrument):
    """Сервис для поиска заведений, больниц, магазинов по координатам."""

    def __init__(self, client: GeoClient):
        super().__init__()
        self.api = client
        self.base_url = "https://overpass-api.de/api/interpreter"

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> int:
        """Вычисляет дистанцию между двумя точками на Земле в метрах."""
        R = 6371000  # Радиус Земли в метрах
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return int(R * c)

    def _get_osm_tag(self, category: str) -> str:
        """Переводит человеческие категории в теги OpenStreetMap."""
        cat = category.lower()
        mapping = {
            "аптека": '["amenity"="pharmacy"]',
            "pharmacy": '["amenity"="pharmacy"]',
            "кафе": '["amenity"="cafe"]',
            "cafe": '["amenity"="cafe"]',
            "ресторан": '["amenity"="restaurant"]',
            "restaurant": '["amenity"="restaurant"]',
            "магазин": '["shop"="supermarket"]',
            "супермаркет": '["shop"="supermarket"]',
            "supermarket": '["shop"="supermarket"]',
            "банкомат": '["amenity"="atm"]',
            "atm": '["amenity"="atm"]',
            "больница": '["amenity"="hospital"]',
            "hospital": '["amenity"="hospital"]',
            "заправка": '["amenity"="fuel"]',
            "парк": '["leisure"="park"]',
        }
        # Если юзер ввел что-то странное, пробуем искать просто по имени заведения
        return mapping.get(cat, f'["name"~"{category}",i]')

    @skill()
    async def find_nearest_places(
        self,
        lat: float,
        lon: float,
        category: str,
        radius_meters: int = 1000,
        limit: int = 5,
    ) -> ToolResult:
        """
        Ищет заведения (POIs) вокруг указанных координат.
        :param category: Что искать ('аптека', 'кафе', 'супермаркет', 'банкомат', 'больница' и т.д.).
        :param radius_meters: Радиус поиска в метрах (по умолчанию 1000 м = 1 км).
        """
        osm_tag = self._get_osm_tag(category)

        # Строим Overpass QL запрос (Язык запросов к базе OSM)
        # Ищем узлы (nodes), линии (ways) и отношения (relations) в заданном радиусе
        query = f"""
        [out:json][timeout:15];
        nwr(around:{radius_meters},{lat},{lon}){osm_tag};
        out center {limit * 3}; 
        """
        # Берем больше лимита, чтобы потом отсортировать и обрезать в Питоне

        try:
            response = await self.api.request("POST", self.base_url, data=query)

            if response.status_code == 200:
                data = response.json()
                elements = data.get("elements", [])

                if not elements:
                    return ToolResult.fail(
                        msg=f"В радиусе {radius_meters} м. ничего похожего на '{category}' не найдено."
                    )

                places = []
                for el in elements:
                    # Overpass для way/relation отдает центр в 'center', а для node - в 'lat'/'lon'
                    p_lat = el.get("lat") or el.get("center", {}).get("lat")
                    p_lon = el.get("lon") or el.get("center", {}).get("lon")

                    if not p_lat or not p_lon:
                        continue

                    tags = el.get("tags", {})
                    name = tags.get("name", "Без названия")
                    opening_hours = tags.get("opening_hours", "Неизвестно")

                    # Вычисляем точную дистанцию от точки пользователя до заведения
                    distance = self._haversine_distance(lat, lon, p_lat, p_lon)

                    places.append(
                        {
                            "name": name,
                            "distance": distance,
                            "hours": opening_hours,
                            "lat": p_lat,
                            "lon": p_lon,
                        }
                    )

                # Сортируем по удаленности и берем нужное количество
                places.sort(key=lambda x: x["distance"])
                places = places[:limit]

                result_lines = [f"Найденные '{category}' (Радиус {radius_meters}м):"]
                for p in places:
                    result_lines.append(
                        f"- {p['name']} | Дистанция: {p['distance']} м. | Часы работы: {p['hours']}"
                    )

                msg = "\n".join(result_lines)
                system_logger.debug(
                    f"[Geo] Найдено {len(places)} мест категории '{category}' вокруг [{lat}, {lon}]."
                )
                return ToolResult.ok(msg=msg, data=places)

            elif response.status_code == 429:
                return ToolResult.fail(
                    msg="Overpass API перегружен (Rate Limit). Попробуйте позже."
                )

            return ToolResult.fail(
                msg=f"Ошибка Overpass API. HTTP {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[Geo] Ошибка сети при поиске мест: {e}")
            return ToolResult.fail(msg=f"Ошибка сети: {e}", error=str(e))
        except Exception as e:
            return ToolResult.fail(msg=f"Критическая ошибка: {e}", error=str(e))

import httpx
from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.geo.client import GeoClient
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class GeoRouting(BaseInstrument):
    """Сервис для построения маршрутов и расчета времени в пути."""

    def __init__(self, client: GeoClient):
        super().__init__()
        self.api = client
        # Бесплатный публичный сервер OSRM
        self.base_url = "http://router.project-osrm.org/route/v1"

    @skill()
    async def calculate_route(
        self, lat_a: float, lon_a: float, lat_b: float, lon_b: float, mode: str = "foot"
    ) -> ToolResult:
        """
        Рассчитывает дистанцию и примерное время в пути между двумя координатами. :param mode: Режим передвижения: 'foot' (пешком), 'car' (на машине), 'bike' (на велосипеде).
        """
        # OSRM поддерживает только 3 профиля на публичном сервере
        mode_map = {
            "car": "driving",
            "foot": "foot",
            "bike": "bike",
            "driving": "driving",
            "walking": "foot",
            "cycling": "bike",
        }
        profile = mode_map.get(mode.lower(), "foot")

        # ВНИМАНИЕ: OSRM ожидает координаты в формате "долгота,широта" (lon,lat)!
        coordinates = f"{lon_a},{lat_a};{lon_b},{lat_b}"
        url = f"{self.base_url}/{profile}/{coordinates}"

        params = {
            "overview": "false",  # Отключаем генерацию геометрии маршрута (экономим 90% токенов)
            "alternatives": "false",
        }

        try:
            response = await self.api.request("GET", url, params=params)

            if response.status_code == 200:
                data = response.json()

                if data.get("code") != "Ok" or not data.get("routes"):
                    return ToolResult.fail(
                        msg="Маршрут между этими точками не найден (возможно, между ними океан или нет дорог)."
                    )

                route = data["routes"][0]
                distance_meters = route.get("distance", 0)
                duration_seconds = route.get("duration", 0)

                # Форматируем в человеческий вид
                distance_km = round(distance_meters / 1000, 2)

                minutes = int(duration_seconds // 60)
                hours = minutes // 60
                rem_minutes = minutes % 60

                if hours > 0:
                    time_str = f"{hours} ч. {rem_minutes} мин."
                else:
                    time_str = f"{minutes} мин."

                mode_ru = (
                    "Пешком"
                    if profile == "foot"
                    else "На машине" if profile == "driving" else "На велосипеде"
                )

                msg = (
                    f"Маршрут ({mode_ru}):\n"
                    f"Дистанция: {distance_km} км ({distance_meters} метров)\n"
                    f"Примерное время в пути: {time_str}"
                )

                system_logger.debug(
                    f"[Geo] Построен маршрут ({profile}): {distance_km} км, {time_str}"
                )
                return ToolResult.ok(
                    msg=msg,
                    data={
                        "distance_m": distance_meters,
                        "duration_s": duration_seconds,
                        "profile": profile,
                    },
                )

            return ToolResult.fail(
                msg=f"Ошибка сервиса маршрутов. HTTP Status: {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[Geo] Ошибка сети при построении маршрута: {e}")
            return ToolResult.fail(msg=f"Ошибка сети: {e}", error=str(e))
        except Exception as e:
            return ToolResult.fail(msg=f"Критическая ошибка: {e}", error=str(e))

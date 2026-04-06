import httpx
from src.l00_utils.managers.logger import system_logger
from src.l03_interfaces.type.geo.client import GeoClient
from src.l03_interfaces.models import ToolResult
from src.l03_interfaces.type.base import BaseInstrument

from src.l04_agency.skills.registry import skill


class GeoWeather(BaseInstrument):
    """Сервис для получения текущей погоды и прогнозов по координатам."""

    def __init__(self, client: GeoClient):
        super().__init__()  # Автоматическая регистрация навыков для LLM, у которых есть декоратор @skill
        self.api = client
        self.base_url = "https://api.open-meteo.com/v1/forecast"

    def _decode_wmo(self, code: int) -> str:
        """Вспомогательный метод. Расшифровывает коды погоды (WMO) в понятный текст для LLM."""
        weather_codes = {
            0: "☀️ Ясно",
            1: "🌤 В основном ясно",
            2: "⛅️ Переменная облачность",
            3: "☁️ Пасмурно",
            45: "🌫 Туман",
            48: "🌫 Изморозь (оседающий туман)",
            51: "🌧 Легкая морось",
            53: "🌧 Умеренная морось",
            55: "🌧 Сильная морось",
            56: "🌧 Легкий ледяной дождь",
            57: "🌧 Сильный ледяной дождь",
            61: "🌧 Легкий дождь",
            63: "🌧 Умеренный дождь",
            65: "🌧 Сильный дождь",
            66: "🌧 Легкий ледяной дождь",
            67: "🌧 Сильный ледяной дождь",
            71: "🌨 Легкий снег",
            73: "🌨 Умеренный снег",
            75: "🌨 Сильный снегопад",
            77: "🌨 Снежные зерна",
            80: "🌧 Легкие ливни",
            81: "🌧 Умеренные ливни",
            82: "🌧 Сильные ливни",
            85: "🌨 Слабый снежный ливень",
            86: "🌨 Сильный снежный ливень",
            95: "⛈ Гроза",
            96: "⛈ Гроза с легким градом",
            99: "⛈ Гроза с сильным градом",
        }
        return weather_codes.get(code, f"❓ Неизвестный код погоды ({code})")

    @skill()
    async def get_current_weather(self, lat: float, lon: float) -> ToolResult:
        """
        Узнает текущую погоду по координатам (Широта, Долгота).
        Возвращает температуру, ощущаемую температуру, ветер и осадки.
        """
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
            "wind_speed_unit": "ms",  # Метры в секунду (привычнее для RU сегмента)
            "timezone": "auto",
        }

        try:
            response = await self.api.request("GET", self.base_url, params=params)

            if response.status_code == 200:
                data = response.json()
                current = data.get("current", {})

                temp = current.get("temperature_2m", 0.0)
                feels_like = current.get("apparent_temperature", 0.0)
                wind = current.get("wind_speed_10m", 0.0)
                precip = current.get("precipitation", 0.0)
                wmo_code = current.get("weather_code", -1)

                condition = self._decode_wmo(wmo_code)

                # Знаки '+' для плюсовой температуры
                t_str = f"+{temp}" if temp > 0 else str(temp)
                fl_str = f"+{feels_like}" if feels_like > 0 else str(feels_like)

                msg = (
                    f"Текущая погода по координатам [{lat}, {lon}]:\n"
                    f"Состояние: {condition}\n"
                    f"Температура: {t_str}°C (Ощущается как: {fl_str}°C)\n"
                    f"Ветер: {wind} м/с\n"
                    f"Осадки: {precip} мм"
                )

                system_logger.debug(f"[Geo] Запрос текущей погоды для [{lat}, {lon}] -> {t_str}°C")
                return ToolResult.ok(msg=msg, data=data)

            return ToolResult.fail(
                msg=f"Ошибка погодного сервиса. HTTP Status: {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[Geo] Ошибка сети при запросе погоды: {e}")
            return ToolResult.fail(msg=f"Ошибка сети: {e}", error=str(e))
        except Exception as e:
            return ToolResult.fail(msg=f"Критическая ошибка: {e}", error=str(e))

    @skill()
    async def get_weather_forecast(self, lat: float, lon: float, days: int = 3) -> ToolResult:
        """
        Получает прогноз погоды на несколько дней вперед (от 1 до 14).
        """
        if not (1 <= days <= 14):
            return ToolResult.fail(
                msg=f"Ошибка: параметр days должен быть от 1 до 14. Передано: {days}."
            )

        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
            "timezone": "auto",
            "forecast_days": days,
        }

        try:
            response = await self.api.request("GET", self.base_url, params=params)

            if response.status_code == 200:
                data = response.json()
                daily = data.get("daily", {})

                dates = daily.get("time", [])
                max_temps = daily.get("temperature_2m_max", [])
                min_temps = daily.get("temperature_2m_min", [])
                precip_probs = daily.get("precipitation_probability_max", [])
                wmo_codes = daily.get("weather_code", [])

                if not dates:
                    return ToolResult.fail(msg="Не удалось получить данные прогноза.")

                result_lines = [f"Прогноз погоды на {days} дней (Координаты: [{lat}, {lon}]):"]

                for i in range(len(dates)):
                    date = dates[i]
                    t_max = max_temps[i]
                    t_min = min_temps[i]
                    prob = precip_probs[i]
                    condition = self._decode_wmo(wmo_codes[i])

                    t_max_str = f"+{t_max}" if t_max > 0 else str(t_max)
                    t_min_str = f"+{t_min}" if t_min > 0 else str(t_min)

                    result_lines.append(
                        f"- {date}: {condition} | Днем: {t_max_str}°C, Ночью: {t_min_str}°C | Вероятность осадков: {prob}%"
                    )

                msg = "\n".join(result_lines)
                system_logger.debug(
                    f"[Geo] Прогноз погоды на {days} дн. для [{lat}, {lon}] успешно получен."
                )
                return ToolResult.ok(msg=msg, data=data)

            return ToolResult.fail(
                msg=f"Ошибка погодного сервиса. HTTP Status: {response.status_code}",
                error=response.text,
            )

        except httpx.RequestError as e:
            system_logger.error(f"[Geo] Ошибка сети при запросе прогноза погоды: {e}")
            return ToolResult.fail(msg=f"Ошибка сети: {e}", error=str(e))
        except Exception as e:
            return ToolResult.fail(msg=f"Критическая ошибка: {e}", error=str(e))

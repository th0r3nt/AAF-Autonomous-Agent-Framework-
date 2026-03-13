import asyncio
from src.layer02_sensors.telegram.agent_account.client import agent_client

async def main():
    # Введите номер телефона агента через +7
    await agent_client.start()
    print("\nАккаунт агента успешно авторизован!\n")


if __name__ == "__main__":
    asyncio.run(main())
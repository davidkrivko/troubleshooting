import logging
import os
import aiohttp

from config import TELEGRAM_BOT, CHAT_ID


async def send_telegram_message(message: str):
    telegram_url = f"https://api.telegram.org/{TELEGRAM_BOT}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}

    async with aiohttp.ClientSession() as session:
        async with session.post(telegram_url, data=data) as response:
            if response.status != 200:
                t = await response.text()
                logging.error("Telegram error: %s, message: %s", t, message)


async def create_notification_async(payload: dict):
    """Асинхронная замена старому create_notification (на aiohttp)"""
    payload["api_key"] = os.environ.get("NOTIFICATION_API_KEY")
    _url = os.environ.get("BACKEND_URL")

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                    f"{_url}api/support/notifications/create/",
                    json=payload,
                    headers={"Content-Type": "application/json"}
            ) as response:
                t = await response.text()
                logging.info(f"Notification response: {t}")
        except Exception as e:
            logging.error(f"Failed to create notification: {e}")


async def save_learning_data_async(serial_num: str, time_taken: int, start_temp: int, end_temp: int):
    """Новая функция: отправка данных об обучении на бэкенд"""
    _url = os.environ.get("BACKEND_URL")
    api_key = os.environ.get("NOTIFICATION_API_KEY")

    payload = {
        "api_key": api_key,
        "serial_num": serial_num,
        "time_to_heat": time_taken,
        "start_temp": start_temp,
        "end_temp": end_temp,
    }

    # Пример запроса к вашему API. URL нужно будет адаптировать под ваш бэкенд
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                    f"{_url}api/devices/controller/heating-delta/",  # Замените на реальный эндпоинт
                    json=payload
            ):
                logging.info(f"Learning data saved for {serial_num}. Took {time_taken}s")
        except Exception as e:
            logging.error(f"Failed to save learning data: {e}")

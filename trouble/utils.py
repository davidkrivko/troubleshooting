import datetime
import json
import logging

import aiohttp
import pandas as pd
import pytz

from db.utils import create_notification, list_of_controller
from config import TROUBLE_SHOOTING_DATA, TELEGRAM_BOT, CHAT_ID
from models.state import BoilerState
from redis_dir.daos import redis_dao


def check_amplitude(ctr_data: pd.Series):
    current_temp = int(ctr_data.temperature)

    heat_data = json.loads(ctr_data.data)
    min_temp = heat_data["heat_amplitude"][0]
    max_temp = heat_data["heat_amplitude"][1]
    if min_temp <= current_temp <= max_temp:
        return True
    elif current_temp < min_temp:
        return False
    else:
        return None


def heating_process(ctr_data: pd.Series, historical_data: pd.DataFrame):
    cool_data = historical_data[historical_data["serial_num"] == ctr_data["serial_num"]]
    cool_data = cool_data.iloc[0]

    delta = ctr_data["timestamp"] - cool_data["timestamp"]

    heat_data = json.loads(ctr_data["data"])
    if delta.seconds > heat_data["heating_time"]:
        return True
    else:
        return False


async def parse_redis_data(controllers_keys: list):
    """Возвращает чистый словарь из Redis вместо тяжелого Pandas DataFrame"""
    raw_data = await redis_dao.get_all_paired_relay_data(controllers_keys)

    parsed = {}
    for data in raw_data:
        if not data or "sn1" not in data:
            continue

        serial_num = data["sn1"]
        try:
            temp = int(data.get("t1", "0"))
        except (ValueError, TypeError):
            temp = 0

        relay_val = int(data.get("relay", "0"))
        out_heat_val = int(data.get("out_heat", "0"))
        relay_status = 1 if (relay_val == 1 or out_heat_val == 1) else 0

        timestamp_str = data.get("timestamp", "")
        try:
            timestamp = datetime.datetime.fromisoformat(timestamp_str).replace(tzinfo=datetime.timezone.utc)
        except ValueError:
            timestamp = datetime.datetime.now(tz=datetime.timezone.utc)

        parsed[serial_num] = {
            "relay": relay_status,
            "temperature": temp,
            "timestamp": timestamp
        }
    return parsed


async def fetch_db_controllers():
    """Получает список бойлеров из БД"""
    controllers_raw = await list_of_controller()

    boilers = {}
    for row in controllers_raw:
        serial_num = row[0]
        boilers[serial_num] = BoilerState(
            serial_num=serial_num,
            owner_first_name=row[1],
            boiler_id=row[2],
            boiler_name=row[3],
            is_statistic=row[4],
            is_learning=row[5] if row[5] is not None else False,
            heating_delta=row[6]
        )
    return boilers


def update_redis_data(main_data, new_data):
    updated_data = main_data.merge(
        new_data, on="serial_num", how="left", suffixes=("", "_new")
    )

    updated_data["temperature"] = updated_data["temperature_new"].combine_first(
        updated_data["temperature"]
    )
    updated_data["relay"] = updated_data["relay_new"].combine_first(
        updated_data["relay"]
    )
    updated_data["timestamp"] = updated_data["timestamp_new"].combine_first(
        updated_data["timestamp"]
    )

    updated_data = updated_data.drop(
        columns=["temperature_new", "relay_new", "timestamp_new"]
    )
    return updated_data


async def send_telegram_message(message):
    telegram_url = f"https://api.telegram.org/{TELEGRAM_BOT}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}

    async with aiohttp.ClientSession() as session:
        async with session.post(telegram_url, data=data) as response:
            t = await response.text()
            if response.status != 200:
                logging.error("text: %s, message: %s", t, message)
            return t


async def create_heating_notification(data: pd.Series, heat_started: datetime.datetime):
    payload = {
        "text": f"Boiler {data['boiler_name']}!",
        "type": 6,
        "boiler": data["boiler_id"],
        "additional_data": {
            "last_seen": data["timestamp"],
            "device_name": data["serial_num"],
            "name": data["owner_first_name"],
        },
    }

    ny_timezone = pytz.timezone("America/New_York")
    heat_started_ny = heat_started.astimezone(ny_timezone)
    formatted_date = heat_started_ny.strftime("%Y-%m-%d %H:%M:%S")

    await send_telegram_message(f"Heating problem: {data['serial_num']}\nRelay turned on at: {formatted_date}")
    # await create_notification(payload)
    return pd.DataFrame([{"timestamp": data["timestamp"], "serial_num": data["serial_num"], "heat_started": heat_started}])


async def create_heating_notification_2(data: pd.Series, heat_started: datetime.datetime):
    ny_timezone = pytz.timezone("America/New_York")
    now = datetime.datetime.now().astimezone(ny_timezone)

    heat_started_ny = data['timestamp'].astimezone(ny_timezone)
    formatted_date = heat_started_ny.strftime("%Y-%m-%d %H:%M:%S")

    await send_telegram_message(
        f"Heat working: {data['serial_num']}\n"
        f"Heating started at: {formatted_date}\n"
        f"Heating takes: {(now - heat_started).seconds} sec"
    )
    return pd.DataFrame([{"timestamp": datetime.datetime.now(tz=datetime.UTC), "serial_num": data["serial_num"], "heat_started": heat_started}])

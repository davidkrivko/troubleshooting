import datetime
import json

import aiohttp
import pandas as pd
import pytz

from db.utils import create_notification, list_of_controller
from config import TROUBLE_SHOOTING_DATA, TELEGRAM_BOT, CHAT_ID
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


async def get_redis_data(controllers: list):
    controllers = await redis_dao.get_all_paired_relay_data(controllers)
    data = pd.DataFrame(controllers)
    data.rename(columns={"sn1": "serial_num", "t1": "temperature"}, inplace=True)
    data = data[
        (data["serial_num"].notnull()) &
        (data["temperature"].notnull()) &
        (data["relay"].notnull())
        ]

    data["relay"] = data["relay"].astype(int)

    data["timestamp"] = pd.to_datetime(data["timestamp"])
    return data[["serial_num", "relay", "temperature", "timestamp"]]


async def init_dataframe():
    controllers = await list_of_controller()
    controllers = pd.DataFrame(
        controllers,
        columns=["serial_num", "owner_first_name", "boiler_id", "boiler_name"],
    )

    controllers["temperature"] = 0
    controllers["relay"] = 0
    controllers["data"] = json.dumps(TROUBLE_SHOOTING_DATA)
    controllers["timestamp"] = datetime.datetime.now(tz=datetime.UTC)

    return controllers


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
            print("text: ", t)
            return t


async def create_heating_notification(data: pd.Series, heat_started: datetime.datetime):
    now = datetime.datetime.now()

    payload = {
        "text": f"Boiler {data['boiler_name']}!",
        "message_type": "E",
        "type_id": 6,
        "boiler_id": data["boiler_id"],
        "created_at": now,
        "updated_at": now,
        "message_template": "device_offline",
        "is_sent": False,
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
    return pd.DataFrame([{"timestamp": data["timestamp"], "serial_num": data["serial_num"]}])


async def create_heating_notification_2(data: pd.Series, heat_started: datetime.datetime):
    ny_timezone = pytz.timezone("America/New_York")
    heat_started_ny = data['timestamp'].astimezone(ny_timezone)
    formatted_date = heat_started_ny.strftime("%Y-%m-%d %H:%M:%S")

    await send_telegram_message(
        f"Heat working: {data['serial_num']}\n"
        f"Heating started at: {formatted_date}\n"
        f"Heating takes: {(data['timestamp'] - heat_started).seconds} sec"
    )
    return pd.DataFrame([{"timestamp": data["timestamp"], "serial_num": data["serial_num"]}])

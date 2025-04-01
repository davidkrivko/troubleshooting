from dotenv import load_dotenv
load_dotenv()

import asyncio
import datetime
import logging
import pytz

import pandas as pd
import warnings

from config import TROUBLE_SHOOTING_DATA

warnings.simplefilter(action="ignore", category=pd.errors.SettingWithCopyWarning)


from trouble.utils import (
    init_dataframe,
    get_redis_data,
    update_redis_data,
    check_amplitude,
    heating_process,
    create_heating_notification,
    create_heating_notification_2, send_telegram_message,
)


# e19_ctr_001, wv_ctr_001, heat_ctr_prd1, heat_ctr_prd2
async def main():
    controllers = await init_dataframe()
    all_data = controllers.copy()
    cool_data = all_data.copy()

    messages = pd.DataFrame(columns=["serial_num", "heat_started", "type"])
    main_message = "Owner: {}\n\nstart time: {}\ntaken time: {}\nstart temperature: {}\nend temperature: {}\nserial number: {}"

    i = 0
    start_time = datetime.datetime.now(tz=datetime.UTC)
    while True:

        redis_data = await get_redis_data(list(controllers.serial_num.str.upper()))
        now = datetime.datetime.now(tz=datetime.UTC)

        cool_redis_data = redis_data[redis_data["relay"] == 0]
        cool_data = update_redis_data(cool_data, cool_redis_data)
        all_data = update_redis_data(all_data, redis_data)

        heat_data = all_data[
            (all_data["relay"] == 1) & ((now - all_data["timestamp"]).dt.seconds < 120)
        ]

        cool_data_copy = cool_data.copy()
        cool_data_copy.rename(columns={"timestamp": "start_heating_time", "temperature": "start_temp"}, inplace=True)
        heat_data = pd.merge(
            heat_data,
            cool_data_copy[["serial_num", "start_heating_time", "start_temp"]],
            how="inner",
        )

        for _, row in heat_data.iterrows():
            serial_num = row['serial_num']
            start_time = row['start_heating_time']
            current_temp = int(row['temperature'])

            if ((messages["serial_num"] == serial_num) & (messages["heat_started"] == start_time)).any():
                continue

            elapsed_time = round((now - start_time).total_seconds())
            mess = main_message.format(row['owner_first_name'], start_time.strftime("%Y-%m-%d %H:%M:%S"), elapsed_time, row["start_temp"],
                                       row["temperature"], row["serial_num"])
            if current_temp > TROUBLE_SHOOTING_DATA['heat_amplitude']:
                if elapsed_time <= TROUBLE_SHOOTING_DATA['heating_time']:
                    await send_telegram_message(f"{row['boiler_name']} heated up quickly. 🟢\n" + mess)
                    messages = pd.concat(
                        [messages, pd.DataFrame([{"serial_num": serial_num, "heat_started": start_time, "type": "green"}])],
                        ignore_index=True)
                elif TROUBLE_SHOOTING_DATA['heating_time'] < elapsed_time <= TROUBLE_SHOOTING_DATA[
                    'heating_time_2']:
                    await send_telegram_message(f"Boiler {row['boiler_name']} heated up slowly.🟡\n" + mess)
                    messages = pd.concat(
                        [messages, pd.DataFrame([{"serial_num": serial_num, "heat_started": start_time, "type": "yellow"}])],
                        ignore_index=True)

                    last_three = messages[messages["serial_num"] == serial_num].sort_values(
                        by="heat_started", ascending=False
                    ).head(3)

                    if len(last_three) == 3 and all(last_three["type"] == "yellow"):
                        await send_telegram_message(f"Boiler {row['boiler_name']} is heating slowly consistently. ⚠️")

            else:
                if elapsed_time > TROUBLE_SHOOTING_DATA['heating_time_2']:
                    today = now.date()
                    red_messages_today = messages[
                        (messages["serial_num"] == serial_num) &
                        (messages["type"] == "red") &
                        (messages["heat_started"].dt.date == today)
                        ]

                    # Определяем текст сообщения
                    if red_messages_today.empty:
                        message_text = f"Boiler {row['boiler_name']} didn't heat up in time.🔴\n"
                    else:
                        message_text = f"Boiler {row['boiler_name']} didn't heat up in time.🔴\n **JUST FOR LOGGING**\n"

                    await send_telegram_message(message_text + mess)
                    messages = pd.concat(
                        [messages, pd.DataFrame([{"serial_num": serial_num, "heat_started": start_time, "type": "red"}])],
                        ignore_index=True)

        i += 1
        if i == 1000:
            end_time = datetime.datetime.now(tz=datetime.UTC)

            controllers = await init_dataframe()
            logging.error(f"ales good: {end_time - start_time}")
            start_time = end_time
            i = 0


if __name__ == "__main__":
    asyncio.run(main())

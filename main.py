import asyncio
import datetime
import logging

from dotenv import load_dotenv

load_dotenv()

from models.state import BoilerState
from trouble.http_req import save_learning_data_async, create_notification_async
from trouble.utils import fetch_db_controllers, parse_redis_data, send_telegram_message

from config import TROUBLE_SHOOTING_DATA


def format_seconds(seconds):
    return f"{seconds // 60}min {seconds % 60}sec"


async def send_boiler_alert(boiler, serial_num, elapsed_time, expected_time, alert_type, main_msg, alert_key):
    """
    alert_type: 7 (Learning Success), 6 (Yellow/Slow), 26 (Red/No Heat), 'green' (Just Telegram)
    """
    elapsed_str = format_seconds(elapsed_time)
    expected_str = format_seconds(expected_time) if expected_time else ""

    emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴", "learn": "🧠"}.get(alert_key, "")

    notify_type = None  # Для зеленого не создаем нотификацию в БД по вашему коду
    if alert_key == "learn":
        text = f"Boiler **{boiler.boiler_name}**. \nLearning data updated, Delta T: *{elapsed_str}*!"
        tg_prefix = f"🧠 Boiler {boiler.boiler_name} learned! Reached 110°C in {elapsed_str}."
        notify_type = 7
    elif alert_key == "green":
        text = f"Boiler {boiler.boiler_name} heated up quickly. {emoji}"
        tg_prefix = text
    elif alert_key == "yellow":
        text = f"Boiler **{boiler.boiler_name}** took *{elapsed_str}* to heat up. \nExpected time: {expected_str}"
        tg_prefix = f"Boiler heated up slowly. {emoji}"
        notify_type = 6
    elif alert_key == "red":
        text = f"Boiler **{boiler.boiler_name}**. Never heated up.\nExpected time: {expected_str}"
        tg_prefix = f"Boiler didn't heat up in time. {emoji}"
        notify_type = 26
    else:
        return

    await send_telegram_message(f"{tg_prefix}\n\n{main_msg}")

    if notify_type:
        payload = {
            "text": text,
            "type": notify_type,
            "boiler": boiler.boiler_id,
            "additional_data": {
                "last_seen": boiler.last_seen.isoformat(),
                "device_name": serial_num,
                "name": boiler.owner_first_name,
            }
        }
        await create_notification_async(payload)

    boiler.alerts_sent.add(alert_key)


async def main():
    logging.info("Starting IONIQ Monitoring Service...")
    boilers: dict[str, BoilerState] = await fetch_db_controllers()
    last_db_sync = datetime.datetime.now(tz=datetime.timezone.utc)

    main_message_tpl = (
        "Owner: {owner}\n"
        "Start: {start_time}\n"
        "Taken: {taken}s\n"
        "Temp: {start_temp}°C -> {end_temp}°C\n"
        "SN: {serial}"
    )

    while True:
        try:
            now = datetime.datetime.now(tz=datetime.timezone.utc)

            if (now - last_db_sync).total_seconds() > 3600:
                new_boilers = await fetch_db_controllers()
                for sn, b in new_boilers.items():
                    if sn in boilers:
                        boilers[sn].is_statistic = b.is_statistic
                        boilers[sn].is_learning = b.is_learning
                        boilers[sn].heating_delta = b.heating_delta
                    else:
                        boilers[sn] = b
                last_db_sync = now
                logging.info("Synced controllers from DB.")

            redis_data = await parse_redis_data(list(boilers.keys()))

            for serial_num, current_data in redis_data.items():
                boiler = boilers.get(serial_num)
                if not boiler: continue

                prev_relay = boiler.relay
                boiler.relay = current_data["relay"]
                boiler.current_temp = current_data["temperature"]
                boiler.last_seen = current_data["timestamp"]

                if (now - boiler.last_seen).total_seconds() > 120:
                    continue

                if boiler.relay == 1 and prev_relay == 0:
                    boiler.heat_start_time = now
                    boiler.heat_start_temp = boiler.current_temp
                    boiler.alerts_sent.clear()
                    if boiler.is_learning and boiler.current_temp <= TROUBLE_SHOOTING_DATA['learning_start_temp']:
                        boiler.learning_active = True
                        logging.info(f"[{serial_num}] Learning mode active.")

                elif boiler.relay == 0 and prev_relay == 1:
                    boiler.learning_active = False

                if boiler.relay == 1 and boiler.heat_start_time:
                    if boiler.alerts_sent:
                        continue

                    elapsed_time = round((now - boiler.heat_start_time).total_seconds())
                    mess = main_message_tpl.format(
                        owner=boiler.owner_first_name,
                        start_time=boiler.heat_start_time.strftime("%H:%M:%S"),
                        taken=elapsed_time,
                        start_temp=boiler.heat_start_temp,
                        end_temp=boiler.current_temp,
                        serial=serial_num
                    )

                    if boiler.learning_active:
                        if boiler.current_temp >= TROUBLE_SHOOTING_DATA['learning_target_temp']:
                            await save_learning_data_async(
                                serial_num=serial_num,
                                time_taken=elapsed_time,
                                start_temp=boiler.heat_start_temp,
                                end_temp=boiler.current_temp
                            )
                            await send_boiler_alert(boiler, serial_num, elapsed_time, None, 7, mess, "learn")
                            boiler.learning_active = False
                        continue

                    target_temp = TROUBLE_SHOOTING_DATA['heat_amplitude']

                    if boiler.heating_delta is not None:
                        t1 = boiler.heating_delta
                        t2 = boiler.heating_delta + 120
                    else:
                        continue

                    if boiler.current_temp >= target_temp:
                        if elapsed_time <= t1:
                            await send_boiler_alert(boiler, serial_num, elapsed_time, t1, None, mess, "green")
                        elif t1 < elapsed_time <= t2:
                            await send_boiler_alert(boiler, serial_num, elapsed_time, t1, 6, mess, "yellow")
                    else:
                        if elapsed_time > t2:
                            await send_boiler_alert(boiler, serial_num, elapsed_time, t1, 26, mess, "red")

        except Exception as e:
            logging.error(f"Error in main loop: {e}", exc_info=True)

        await asyncio.sleep(2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

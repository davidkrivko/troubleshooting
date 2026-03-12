import asyncio
import datetime
import logging

from dotenv import load_dotenv
load_dotenv()

from models.state import BoilerState
from trouble.http_req import save_learning_data_async, create_notification_async
from trouble.utils import fetch_db_controllers, parse_redis_data, send_telegram_message

from config import TROUBLE_SHOOTING_DATA


async def main():
    logging.info("Starting IONIQ Monitoring Service...")

    boilers: dict[str, BoilerState] = await fetch_db_controllers()

    last_db_sync = datetime.datetime.now(tz=datetime.timezone.utc)

    main_message_tpl = (
        "Owner: {owner}\n\nstart time: {start_time}\n"
        "taken time: {taken}s\nstart temperature: {start_temp}\n"
        "end temperature: {end_temp}\nserial number: {serial}"
    )

    while True:
        try:
            now = datetime.datetime.now(tz=datetime.timezone.utc)

            if (now - last_db_sync).total_seconds() > 3600:
                new_boilers = await fetch_db_controllers()
                for sn, boiler in new_boilers.items():
                    if sn not in boilers:
                        boilers[sn] = boiler
                    else:
                        boilers[sn].is_statistic = boiler.is_statistic
                        boilers[sn].is_learning = boiler.is_learning
                        boilers[sn].heating_delta = boiler.heating_delta
                last_db_sync = now
                logging.info("Synced controllers from DB.")

            redis_data = await parse_redis_data(list(boilers.keys()))

            for serial_num, current_data in redis_data.items():
                boiler = boilers.get(serial_num)
                if not boiler:
                    continue

                prev_relay = boiler.relay
                boiler.relay = current_data["relay"]
                boiler.current_temp = current_data["temperature"]
                boiler.last_seen = current_data["timestamp"]

                # Проверка, что контроллер "живой" (данные свежие, < 120 сек назад)
                if (now - boiler.last_seen).total_seconds() > 120:
                    continue  # Контроллер отвалился от сети, пропускаем расчеты

                # СОБЫТИЕ: Реле только что включилось (Старт нагрева)
                if boiler.relay == 1 and prev_relay == 0:
                    boiler.heat_start_time = now
                    boiler.heat_start_temp = boiler.current_temp
                    boiler.alerts_sent.clear()  # Очищаем историю алертов для нового цикла

                    # ПРОВЕРКА РЕЖИМА ОБУЧЕНИЯ:
                    if boiler.is_learning and boiler.current_temp <= TROUBLE_SHOOTING_DATA['learning_start_temp']:
                        boiler.learning_active = True
                        logging.info(f"[{serial_num}] Started learning mode cycle.")

                # СОБЫТИЕ: Реле выключилось (Конец нагрева)
                elif boiler.relay == 0 and prev_relay == 1:
                    boiler.learning_active = False  # Сбрасываем флаг обучения

                # ЛОГИКА АКТИВНОГО НАГРЕВА (Реле включено)
                if boiler.relay == 1 and boiler.heat_start_time:
                    elapsed_time = round((now - boiler.heat_start_time).total_seconds())

                    mess = main_message_tpl.format(
                        owner=boiler.owner_first_name,
                        start_time=boiler.heat_start_time.strftime("%Y-%m-%d %H:%M:%S"),
                        taken=elapsed_time,
                        start_temp=boiler.heat_start_temp,
                        end_temp=boiler.current_temp,
                        serial=serial_num
                    )

                    # --- 1. ЛОГИКА ОБУЧЕНИЯ (LEARNING MODE) ---
                    if boiler.learning_active and boiler.current_temp >= TROUBLE_SHOOTING_DATA['learning_target_temp']:
                        # Бойлер достиг 110 градусов!
                        await save_learning_data_async(
                            serial_num=serial_num,
                            time_taken=elapsed_time,
                            start_temp=boiler.heat_start_temp,
                            end_temp=boiler.current_temp
                        )
                        boiler.learning_active = False  # Обучение для этого цикла завершено
                        await send_telegram_message(
                            f"🧠 Boiler {boiler.boiler_name} learned! Reached 110°C in {elapsed_time}s.\n" + mess)

                    # --- 2. ЛОГИКА ТРАБЛШУТИНГА (АЛЕРТЫ) ---
                    target_temp = TROUBLE_SHOOTING_DATA['heat_amplitude']
                    if boiler.heating_delta is not None:
                        t1 = boiler.heating_delta
                        t2 = boiler.heating_delta + 120  # +2 минуты (120 сек) сверху для красного
                    else:
                        # Стандартные (дефолтные) значения, если delta не задана
                        t1 = TROUBLE_SHOOTING_DATA['heating_time']  # 120
                        t2 = TROUBLE_SHOOTING_DATA['heating_time_2']  # 240

                    if boiler.current_temp > target_temp:
                        # Нагрелся быстро (до 120 сек)
                        if elapsed_time <= t1 and "green" not in boiler.alerts_sent:
                            await send_telegram_message(f"Boiler {boiler.boiler_name} heated up quickly. 🟢\n" + mess)
                            boiler.alerts_sent.add("green")

                        # Нагрелся медленно (от 120 до 240 сек)
                        elif t1 < elapsed_time <= t2 and "yellow" not in boiler.alerts_sent:
                            payload = {
                                "text": f"Boiler {boiler.boiler_name} didn't heat up in time!",
                                "type": 6,
                                "boiler": boiler.boiler_id,
                                "additional_data": {
                                    "last_seen": boiler.last_seen.isoformat(),
                                    "device_name": serial_num,
                                    "name": boiler.owner_first_name,
                                }
                            }
                            await create_notification_async(payload)
                            await send_telegram_message(f"Boiler {boiler.boiler_name} heated up slowly. 🟡\n" + mess)
                            boiler.alerts_sent.add("yellow")

                            # Здесь можно добавить логику подсчета "3 раза подряд желтый = ⚠️",
                            # но для этого нужно хранить историю ПРЕДЫДУЩИХ циклов (вне boiler.alerts_sent)

                    else:
                        # Температура всё еще ниже нормы, а прошло уже больше 240 сек (Авария)
                        if elapsed_time > t2 and "red" not in boiler.alerts_sent:
                            payload = {
                                "text": f"Boiler {boiler.boiler_name} didn't heat up!",
                                "type": 26,
                                "boiler": boiler.boiler_id,
                                "additional_data": {
                                    "last_seen": boiler.last_seen.isoformat(),
                                    "device_name": serial_num,
                                    "name": boiler.owner_first_name,
                                }
                            }
                            await create_notification_async(payload)
                            await send_telegram_message(
                                f"Boiler {boiler.boiler_name} didn't heat up in time. 🔴\n" + mess)
                            boiler.alerts_sent.add("red")

        except Exception as e:
            logging.error(f"Error in main loop: {e}", exc_info=True)

        await asyncio.sleep(2)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

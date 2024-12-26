import asyncio
import datetime
import logging
import pytz

import pandas as pd
import warnings

from dotenv import load_dotenv

from config import TROUBLE_SHOOTING_DATA

load_dotenv()
warnings.simplefilter(action="ignore", category=pd.errors.SettingWithCopyWarning)


from trouble.utils import (
    init_dataframe,
    get_redis_data,
    update_redis_data,
    check_amplitude,
    heating_process,
    create_heating_notification,
    create_heating_notification_2,
)


# e19_ctr_001, wv_ctr_001, heat_ctr_prd1, heat_ctr_prd2
async def main():
    controllers = await init_dataframe()
    all_data = controllers.copy()
    cool_data = all_data.copy()

    errors = pd.DataFrame(columns=["serial_num", "timestamp"])
    heat_work_errors_history = pd.DataFrame(columns=["serial_num", "timestamp"])

    i = 0
    start_time = datetime.datetime.now()
    while True:

        redis_data = await get_redis_data(list(controllers.serial_num.str.upper()))
        now = datetime.datetime.now(tz=datetime.UTC)

        cool_redis_data = redis_data[redis_data["relay"] == 0]
        cool_data = update_redis_data(cool_data, cool_redis_data)
        all_data = update_redis_data(all_data, redis_data)

        heat_data = all_data[
            (all_data["relay"] == 1) & ((now - all_data["timestamp"]).dt.seconds < 120)
        ]
        errors = errors[errors["serial_num"].isin(heat_data["serial_num"])]

        if len(heat_data) > 0:
            heat_data["heat_work"] = heat_data.apply(check_amplitude, axis=1)

            heat_work = heat_data[heat_data["heat_work"] != False]
            check_data = heat_data[heat_data["heat_work"] == False]

            if len(check_data) > 0:
                check_data["error"] = check_data.apply(
                    lambda x: heating_process(x, cool_data), axis=1
                )

                error_data = check_data[check_data["error"] == True]

                if len(error_data) > 0:
                    for _, data in error_data.iterrows():
                        last_error = errors.loc[
                            errors["serial_num"] == data["serial_num"], "timestamp"
                        ]
                        heat_started = cool_data.loc[
                            cool_data["serial_num"] == data["serial_num"], "timestamp"
                        ]
                        if not any(last_error) or datetime.datetime.now(
                            tz=datetime.UTC
                        ) - data["timestamp"] > datetime.timedelta(hours=1):
                            error = await create_heating_notification(
                                data,
                                (
                                    heat_started.iloc[0]
                                    if len(heat_started) > 0
                                    else data["timestamp"]
                                ),
                            )

                            if (
                                error["serial_num"].values[0]
                                in errors["serial_num"].values
                            ):
                                errors.loc[
                                    errors["serial_num"] == error["serial_num"],
                                    "timestamp",
                                ] = error["timestamp"]
                            else:
                                errors = pd.concat([errors, error], ignore_index=True)

            heat_work_errors = errors[
                errors["serial_num"].isin(heat_work["serial_num"])
            ]
            if len(heat_work_errors) > 0:
                for _, heat_work_error in heat_work_errors.iterrows():
                    last_error = heat_work_errors_history.loc[
                        heat_work_errors_history["serial_num"] == heat_work_error["serial_num"],
                        "timestamp",
                    ]

                    curr_temp = heat_data.loc[
                        heat_data["serial_num"] == heat_work_error["serial_num"], "t1"
                    ]
                    if TROUBLE_SHOOTING_DATA["heat_amplitude"][0] <= curr_temp:
                        one_hour = datetime.datetime.now(tz=datetime.UTC) - heat_work_error["timestamp"].replace(tzinfo=pytz.utc) > datetime.timedelta(hours=1)
                        _is_more = datetime.datetime.now(tz=datetime.UTC) > heat_work_error["timestamp"].replace(tzinfo=pytz.utc)
                        if not any(last_error) or (one_hour and _is_more):
                            heat_started = cool_data.loc[
                                cool_data["serial_num"] == heat_work_error["serial_num"], "timestamp"
                            ]

                            heat_work_error = await create_heating_notification_2(
                                heat_work_error,
                                (
                                    heat_started.iloc[0]
                                    if len(heat_started) > 0
                                    else heat_work_error["timestamp"]
                                ),
                            )

                            if (
                                heat_work_error["serial_num"].values[0]
                                in heat_work_errors_history["serial_num"].values
                            ):
                                heat_work_errors_history.loc[
                                    heat_work_errors_history["serial_num"]
                                    == heat_work_error["serial_num"].iloc[0],
                                    "timestamp",
                                ] = heat_work_error["timestamp"]
                            else:
                                heat_work_errors_history = pd.concat(
                                    [heat_work_errors_history, heat_work_error],
                                    ignore_index=True,
                                )

        i += 1
        if i == 10:
            end_time = datetime.datetime.now()

            controllers = await init_dataframe()
            logging.error(f"ales good: {end_time - start_time}")
            start_time = end_time
            i = 0


if __name__ == "__main__":
    asyncio.run(main())

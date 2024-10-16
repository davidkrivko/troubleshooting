import datetime

import pytz

from redis_dir.daos import redis_dao


DEVICE_ONLINE_STATUS_DELTA_SEC = 15
dao = redis_dao

utc_tz = pytz.timezone('UTC')


def fetch_online_status(timestamp, now) -> dict:
    """
    Searches serial number in redis_dir stream of devices online status
    and returns bool response in a context object

    Returns:
        object: [data] (bool) True if online, else False
    """

    ctx = {
        'detail': None,
        'data': None, 
    }
    timestamp_str = timestamp
    timestamp = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f%z")
    delta = now - timestamp.replace(tzinfo=None)

    if delta.days != -1:
        if delta.seconds <= DEVICE_ONLINE_STATUS_DELTA_SEC:
            ctx['data'] = True
            ctx['detail'] = f"Timedelta (last seen online) [{delta.seconds} s]"
        else:
            ctx['data'] = False
            ctx['detail'] = f"Timedelta (last seen online) [{delta.seconds} s] " \
                            f"status exceeds limit [{DEVICE_ONLINE_STATUS_DELTA_SEC} s]"
    else:
        ctx["data"] = True

    return ctx

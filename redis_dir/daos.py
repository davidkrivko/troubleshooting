import asyncio
import os
import redis.asyncio as redis


REDIS_URL = os.environ.get("REDIS_CONNECTION")

connect = redis.from_url(REDIS_URL)


class RedisDao:
    @staticmethod
    async def get_all_paired_relay_data(controllers: list):
        all_data = await asyncio.gather(*[connect.hgetall("ION:PAIR:REL:" + key.upper()) for key in controllers])
        return all_data


redis_dao = RedisDao()

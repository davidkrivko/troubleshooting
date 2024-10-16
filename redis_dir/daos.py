import asyncio
import os
import redis.asyncio as redis

from redis_dir.schemas import StreamsKeySchema


streams_key_schema = StreamsKeySchema()

REDIS_URL = os.environ.get("REDIS_CONNECTION")

connect = redis.from_url(REDIS_URL)


class RedisDao:
    """
    Instantiates Data Access object which uses
    redis_dir to store iot data in its data types (streams, ts etc.)
    """

    async def get_paired_relay_controller_data(self, sn: str):
        key = streams_key_schema.paired_relay_key(sn)
        raw_data = await connect.hgetall(key)
        return raw_data

    async def get_paired_thermostat_data(self, sn: str):
        key = streams_key_schema.paired_thermostat_key(sn)
        raw_data = await connect.hgetall(key)
        return raw_data

    async def get_receiver_data(self, sn: str):
        key = streams_key_schema.receiver_key(sn)
        raw_data = await connect.hgetall(key)
        return raw_data

    async def get_boiler_data(self, sn: str):
        key = streams_key_schema.boiler_data_key(sn)
        raw_data = await connect.hgetall(key)
        return raw_data

    async def get_all_paired_relay_data(self, controllers: list):
        all_data = await asyncio.gather(*[connect.hgetall("ION:PAIR:REL:" + key) for key in controllers])
        return all_data


redis_dao = RedisDao()

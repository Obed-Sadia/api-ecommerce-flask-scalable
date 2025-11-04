import redis
import json
import os

redis_client = redis.Redis.from_url(os.getenv('REDIS_URL'))

def cache_order(order_id, order_data):
    redis_client.set(f"order:{order_id}", json.dumps(order_data))

def get_cached_order(order_id):
    cached = redis_client.get(f"order:{order_id}")
    return json.loads(cached) if cached else None
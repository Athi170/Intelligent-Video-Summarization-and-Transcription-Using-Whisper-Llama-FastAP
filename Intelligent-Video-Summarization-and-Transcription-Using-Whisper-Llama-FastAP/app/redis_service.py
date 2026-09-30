import redis
import os
from datetime import datetime
from dotenv import load_dotenv


# Load variables from .env
load_dotenv()


# Get Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))


# Create Redis connection
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    decode_responses=True
)


def save_result(key, value):
    redis_client.set(key, value)


def get_result(key):
    return redis_client.get(key)


def check_redis():
    return redis_client.ping()

def set_status(video_id, status):
    redis_client.set(
        f"video:{video_id}:status",
        status
    )


def get_status(video_id):
    return redis_client.get(
        f"video:{video_id}:status"
    )

def save_history(video_id, status):

    redis_client.hset(
        f"video:{video_id}:history",
        mapping={
            "video_id": video_id,
            "status": status,
            "timestamp": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        }
    )

    redis_client.sadd(
        "video_history",
        video_id
    )

def get_history(video_id):
    return redis_client.hgetall(
        f"video:{video_id}:history"
    )    

def get_all_video_ids():
    return list(
        redis_client.smembers("video_history")
    )

def delete_video(video_id):

    redis_client.delete(
        f"video:{video_id}:transcript"
    )

    redis_client.delete(
        f"video:{video_id}:summary"
    )

    redis_client.delete(
        f"video:{video_id}:language"
    )

    redis_client.delete(
        f"video:{video_id}:status"
    )

    redis_client.delete(
        f"video:{video_id}:history"
    )

    redis_client.srem(
        "video_history",
        video_id
    )

def delete_all_history_records():

    video_ids = get_all_video_ids()

    for video_id in video_ids:

        delete_video(video_id)

    return len(video_ids) 
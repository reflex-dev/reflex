import redis
import psycopg2
from reflex.config import get_config

def check_redis_connection():
    try:
        config = get_config()
        redis_client = redis.Redis.from_url(config.redis_url)
        redis_client.ping()
        return True
    except redis.ConnectionError:
        return False

def check_postgres_connection():
    try:
        config = get_config()
        conn = psycopg2.connect(config.db_url)
        conn.close()
        return True
    except psycopg2.OperationalError:
        return False

def health_check():
    redis_status = check_redis_connection()
    postgres_status = check_postgres_connection()
    
    status = "healthy" if redis_status and postgres_status else "unhealthy"
    return {
        "status": status,
        "redis": "connected" if redis_status else "disconnected",
        "postgres": "connected" if postgres_status else "disconnected"
    }
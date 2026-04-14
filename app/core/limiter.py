"""
全局 API 限流配置
使用 slowapi 实现内存限流，无需 Redis 依赖。
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, storage_uri="memory://")

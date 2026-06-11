import time
from typing import Any, Dict, Optional, Tuple

class InMemoryCache:
    """
    A simple in-memory cache with TTL (Time To Live) support.
    """
    def __init__(self, default_ttl: int = 300) -> None:
        self.default_ttl = default_ttl
        # Store values as (value, expire_time)
        self._cache: Dict[str, Tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieves a value from the cache. Returns None if the key does not exist or has expired.
        """
        if key not in self._cache:
            return None
        
        val, expire_time = self._cache[key]
        if time.time() > expire_time:
            del self._cache[key]
            return None
            
        return val

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Stores a value in the cache with a specified TTL or the default TTL.
        """
        duration = ttl if ttl is not None else self.default_ttl
        expire_time = time.time() + duration
        self._cache[key] = (value, expire_time)

    def delete(self, key: str) -> None:
        """
        Removes a key from the cache.
        """
        if key in self._cache:
            del self._cache[key]

    def clear(self) -> None:
        """
        Clears all keys from the cache.
        """
        self._cache.clear()

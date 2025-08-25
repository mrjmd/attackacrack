"""
CacheService - Simple in-memory caching service
This is a basic implementation for testing purposes
In production, this would use Redis or another caching solution
"""

from typing import Any, Optional, Dict
import time
import threading
import logging

logger = logging.getLogger(__name__)


class CacheEntry:
    """Represents a cached value with expiration."""
    
    def __init__(self, value: Any, ttl: int = None):
        """
        Initialize cache entry.
        
        Args:
            value: Value to cache
            ttl: Time to live in seconds (None for no expiration)
        """
        self.value = value
        self.created_at = time.time()
        self.ttl = ttl
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl


class CacheService:
    """
    Simple in-memory cache service with TTL support.
    Thread-safe implementation for concurrent access.
    """
    
    def __init__(self):
        """Initialize the cache service."""
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if not entry.is_expired():
                    self._hits += 1
                    logger.debug(f"Cache hit for key: {key}")
                    return entry.value
                else:
                    # Remove expired entry
                    del self._cache[key]
                    logger.debug(f"Cache expired for key: {key}")
            
            self._misses += 1
            logger.debug(f"Cache miss for key: {key}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None for no expiration)
            
        Returns:
            True if successful
        """
        try:
            with self._lock:
                self._cache[key] = CacheEntry(value, ttl)
                logger.debug(f"Cached value for key: {key} with TTL: {ttl}")
                return True
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            True if key existed and was deleted
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Deleted cache key: {key}")
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cached values."""
        with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")
    
    def exists(self, key: str) -> bool:
        """
        Check if key exists in cache (and is not expired).
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists and is not expired
        """
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if not entry.is_expired():
                    return True
                else:
                    # Remove expired entry
                    del self._cache[key]
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0.0
            
            return {
                'total_keys': len(self._cache),
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': hit_rate,
                'total_requests': total_requests
            }
    
    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from cache.
        
        Returns:
            Number of entries removed
        """
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
            
            return len(expired_keys)
    
    def get_or_set(self, key: str, factory_func, ttl: int = None) -> Any:
        """
        Get value from cache or compute and cache it.
        
        Args:
            key: Cache key
            factory_func: Function to compute value if not cached
            ttl: Time to live in seconds
            
        Returns:
            Cached or computed value
        """
        value = self.get(key)
        if value is None:
            value = factory_func()
            self.set(key, value, ttl)
        return value
"""
Repository Layer - Data Access Abstraction
Implements the Repository Pattern for database isolation
"""

from .base_repository import (
    BaseRepository,
    PaginationParams,
    PaginatedResult,
    SortOrder
)

__all__ = [
    'BaseRepository',
    'PaginationParams',
    'PaginatedResult',
    'SortOrder'
]
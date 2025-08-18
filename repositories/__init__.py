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
from .contact_flag_repository import ContactFlagRepository

__all__ = [
    'BaseRepository',
    'PaginationParams',
    'PaginatedResult',
    'SortOrder',
    'ContactFlagRepository'
]
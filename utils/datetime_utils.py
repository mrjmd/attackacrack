"""
Timezone-aware datetime utilities for Attack-a-Crack CRM.

This module provides timezone-aware datetime operations to replace deprecated
datetime.utcnow() usage throughout the codebase. All functions return timezone-aware
datetime objects in UTC.

Phase 2 Test Cleanup: Eliminates datetime.utcnow() deprecation warnings.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Union
import pytz


def utc_now() -> datetime:
    """
    Get the current UTC time as a timezone-aware datetime object.
    
    This replaces datetime.utcnow() which is deprecated in Python 3.12+.
    
    Returns:
        datetime: Current UTC time with timezone information
        
    Example:
        >>> now = utc_now()
        >>> print(now.tzinfo)  # UTC
    """
    return datetime.now(timezone.utc)


def utc_from_timestamp(timestamp: Union[int, float]) -> datetime:
    """
    Convert a Unix timestamp to a timezone-aware UTC datetime.
    
    Args:
        timestamp: Unix timestamp (seconds since epoch)
        
    Returns:
        datetime: Timezone-aware datetime in UTC
        
    Example:
        >>> dt = utc_from_timestamp(1234567890)
        >>> print(dt.tzinfo)  # UTC
    """
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """
    Ensure a datetime object is timezone-aware and in UTC.
    
    If the datetime is naive (no timezone), it assumes UTC.
    If the datetime has a different timezone, it converts to UTC.
    
    Args:
        dt: Datetime object (may be naive or timezone-aware)
        
    Returns:
        datetime: Timezone-aware datetime in UTC
        
    Example:
        >>> naive_dt = datetime(2025, 1, 1, 12, 0, 0)
        >>> utc_dt = ensure_utc(naive_dt)
        >>> print(utc_dt.tzinfo)  # UTC
    """
    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        return dt.replace(tzinfo=timezone.utc)
    elif dt.tzinfo != timezone.utc:
        # Different timezone - convert to UTC
        return dt.astimezone(timezone.utc)
    else:
        # Already UTC
        return dt


def utc_to_local(dt: datetime, local_tz: str = 'America/New_York') -> datetime:
    """
    Convert a UTC datetime to a local timezone.
    
    Args:
        dt: UTC datetime (should be timezone-aware)
        local_tz: Target timezone name (default: America/New_York)
        
    Returns:
        datetime: Datetime in the specified local timezone
        
    Example:
        >>> utc_dt = utc_now()
        >>> local_dt = utc_to_local(utc_dt, 'America/Los_Angeles')
    """
    utc_dt = ensure_utc(dt)
    local_timezone = pytz.timezone(local_tz)
    return utc_dt.astimezone(local_timezone)


def local_to_utc(dt: datetime, local_tz: str = 'America/New_York') -> datetime:
    """
    Convert a local datetime to UTC.
    
    Args:
        dt: Local datetime (may be naive or timezone-aware)
        local_tz: Source timezone name if dt is naive (default: America/New_York)
        
    Returns:
        datetime: Timezone-aware datetime in UTC
        
    Example:
        >>> local_dt = datetime(2025, 1, 1, 12, 0, 0)
        >>> utc_dt = local_to_utc(local_dt, 'America/Los_Angeles')
    """
    if dt.tzinfo is None:
        # Naive datetime - assume it's in the specified local timezone
        local_timezone = pytz.timezone(local_tz)
        local_dt = local_timezone.localize(dt)
        return local_dt.astimezone(timezone.utc)
    else:
        # Already has timezone - just convert to UTC
        return dt.astimezone(timezone.utc)


def utc_days_ago(days: int) -> datetime:
    """
    Get a UTC datetime for a specific number of days ago.
    
    Args:
        days: Number of days in the past
        
    Returns:
        datetime: Timezone-aware datetime in UTC for the specified days ago
        
    Example:
        >>> week_ago = utc_days_ago(7)
        >>> month_ago = utc_days_ago(30)
    """
    return utc_now() - timedelta(days=days)


def utc_hours_ago(hours: int) -> datetime:
    """
    Get a UTC datetime for a specific number of hours ago.
    
    Args:
        hours: Number of hours in the past
        
    Returns:
        datetime: Timezone-aware datetime in UTC for the specified hours ago
        
    Example:
        >>> hour_ago = utc_hours_ago(1)
        >>> day_ago = utc_hours_ago(24)
    """
    return utc_now() - timedelta(hours=hours)


def utc_date_range(start_date: datetime, end_date: Optional[datetime] = None) -> tuple[datetime, datetime]:
    """
    Create a UTC date range with timezone-aware datetimes.
    
    Args:
        start_date: Start of the range (will be converted to UTC)
        end_date: End of the range (defaults to now if not provided)
        
    Returns:
        tuple: (start_datetime, end_datetime) both in UTC
        
    Example:
        >>> start = datetime(2025, 1, 1)
        >>> start_utc, end_utc = utc_date_range(start)
    """
    start_utc = ensure_utc(start_date)
    end_utc = ensure_utc(end_date) if end_date else utc_now()
    return start_utc, end_utc


def format_utc_iso(dt: Optional[datetime] = None) -> str:
    """
    Format a datetime as an ISO 8601 string in UTC.
    
    Args:
        dt: Datetime to format (defaults to current UTC time)
        
    Returns:
        str: ISO 8601 formatted string with UTC timezone
        
    Example:
        >>> iso_str = format_utc_iso()
        >>> print(iso_str)  # 2025-01-01T12:00:00+00:00
    """
    utc_dt = ensure_utc(dt) if dt else utc_now()
    return utc_dt.isoformat()


def parse_utc_iso(iso_string: str) -> datetime:
    """
    Parse an ISO 8601 string to a timezone-aware UTC datetime.
    
    Args:
        iso_string: ISO 8601 formatted datetime string
        
    Returns:
        datetime: Timezone-aware datetime in UTC
        
    Example:
        >>> dt = parse_utc_iso('2025-01-01T12:00:00Z')
        >>> print(dt.tzinfo)  # UTC
    """
    # Handle various ISO formats
    if iso_string.endswith('Z'):
        iso_string = iso_string[:-1] + '+00:00'
    
    dt = datetime.fromisoformat(iso_string)
    return ensure_utc(dt)


# Backward compatibility aliases (for gradual migration)
# These will be removed in a future update
def get_utc_now() -> datetime:
    """Deprecated: Use utc_now() instead."""
    return utc_now()


def get_current_utc_datetime() -> datetime:
    """Deprecated: Use utc_now() instead."""
    return utc_now()
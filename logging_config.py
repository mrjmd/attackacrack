# logging_config.py

import logging
import structlog
import sys
from typing import Any, Dict
from flask import has_request_context, request, g
import json


def add_request_context(logger: logging.Logger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add Flask request context to log entries"""
    if has_request_context():
        event_dict["request_id"] = getattr(g, 'request_id', None)
        event_dict["user_id"] = getattr(g, 'user_id', None)
        event_dict["remote_addr"] = request.remote_addr
        event_dict["method"] = request.method
        event_dict["path"] = request.path
        event_dict["user_agent"] = request.headers.get('User-Agent', '')[:100]  # Truncate
    return event_dict


def setup_logging(app_name: str = "attackacrack-crm", log_level: str = "INFO") -> None:
    """
    Configure structured logging for production use
    
    Args:
        app_name: Application name for log identification
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            add_request_context,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, log_level.upper())),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper()),
    )
    
    # Set application logger
    logging.getLogger(app_name).setLevel(getattr(logging, log_level.upper()))
    
    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


def get_logger(name: str = None) -> structlog.BoundLogger:
    """
    Get a structured logger instance
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured structlog instance
    """
    return structlog.get_logger(name or __name__)


class SecurityLogger:
    """Dedicated security event logger"""
    
    def __init__(self):
        self.logger = get_logger("security")
    
    def log_authentication_attempt(self, username: str, success: bool, ip_address: str):
        """Log authentication attempts"""
        self.logger.info(
            "Authentication attempt",
            username=username,
            success=success,
            ip_address=ip_address,
            event_type="auth_attempt"
        )
    
    def log_api_key_usage(self, service: str, success: bool, ip_address: str = None):
        """Log API key usage"""
        self.logger.info(
            "API key usage",
            service=service,
            success=success,
            ip_address=ip_address,
            event_type="api_key_usage"
        )
    
    def log_ssl_error(self, service: str, error: str):
        """Log SSL-related errors"""
        self.logger.error(
            "SSL verification error",
            service=service,
            error=error,
            event_type="ssl_error"
        )


class PerformanceLogger:
    """Performance and monitoring logger"""
    
    def __init__(self):
        self.logger = get_logger("performance")
    
    def log_api_call(self, service: str, endpoint: str, duration_ms: float, status_code: int):
        """Log external API call performance"""
        self.logger.info(
            "External API call",
            service=service,
            endpoint=endpoint,
            duration_ms=duration_ms,
            status_code=status_code,
            event_type="api_call"
        )
    
    def log_database_query(self, query_type: str, duration_ms: float, record_count: int = None):
        """Log database query performance"""
        self.logger.info(
            "Database query",
            query_type=query_type,
            duration_ms=duration_ms,
            record_count=record_count,
            event_type="db_query"
        )


# Global logger instances
security_logger = SecurityLogger()
performance_logger = PerformanceLogger()
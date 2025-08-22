"""
Result Pattern Implementation
Provides a standardized way for services to return results with success/failure status
"""

from typing import TypeVar, Generic, Optional, Any, Dict
from dataclasses import dataclass

T = TypeVar('T')


@dataclass
class Result(Generic[T]):
    """
    A generic Result class for service method returns.
    
    Encapsulates either a successful result with data or a failure with error information.
    This pattern provides a consistent interface for error handling across all services.
    
    Examples:
        # Success case
        result = Result.success(user_data)
        if result.is_success:
            print(result.data)
        
        # Failure case
        result = Result.failure("User not found", code="USER_NOT_FOUND")
        if result.is_failure:
            print(result.error)
    """
    
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @classmethod
    def success(cls, data: T, metadata: Optional[Dict[str, Any]] = None) -> 'Result[T]':
        """
        Create a successful result.
        
        Args:
            data: The successful result data
            metadata: Optional metadata about the operation
            
        Returns:
            A Result instance representing success
        """
        return cls(
            success=True,
            data=data,
            error=None,
            error_code=None,
            metadata=metadata
        )
    
    @classmethod
    def failure(cls, 
                error: str, 
                code: Optional[str] = None,
                metadata: Optional[Dict[str, Any]] = None) -> 'Result[T]':
        """
        Create a failure result.
        
        Args:
            error: Error message describing the failure
            code: Optional error code for programmatic handling
            metadata: Optional metadata about the failure
            
        Returns:
            A Result instance representing failure
        """
        return cls(
            success=False,
            data=None,
            error=error,
            error_code=code,
            metadata=metadata
        )
    
    @property
    def is_success(self) -> bool:
        """Check if the result represents a success."""
        return self.success
    
    @property
    def is_failure(self) -> bool:
        """Check if the result represents a failure."""
        return not self.success
    
    @property
    def value(self) -> Optional[T]:
        """Alias for data property for backward compatibility."""
        return self.data
    
    @property
    def code(self) -> Optional[str]:
        """Alias for error_code property for backward compatibility."""
        return self.error_code
    
    def unwrap(self) -> T:
        """
        Get the data from a successful result.
        
        Returns:
            The data if successful
            
        Raises:
            ValueError: If called on a failure result
        """
        if self.is_failure:
            raise ValueError(f"Cannot unwrap a failure result: {self.error}")
        return self.data
    
    def unwrap_or(self, default: T) -> T:
        """
        Get the data from a successful result or return a default value.
        
        Args:
            default: Value to return if result is a failure
            
        Returns:
            The data if successful, otherwise the default value
        """
        return self.data if self.is_success else default
    
    def map(self, func) -> 'Result':
        """
        Transform the data if successful.
        
        Args:
            func: Function to apply to the data
            
        Returns:
            A new Result with transformed data if successful, 
            otherwise the original failure
        """
        if self.is_success:
            return Result.success(func(self.data), self.metadata)
        return self
    
    def __bool__(self) -> bool:
        """Allow Result to be used in boolean context."""
        return self.is_success
    
    def __repr__(self) -> str:
        """String representation of the Result."""
        if self.is_success:
            return f"Result.success(data={self.data!r})"
        return f"Result.failure(error={self.error!r}, code={self.error_code!r})"


@dataclass
class PagedResult(Generic[T], Result[T]):
    """
    Extended Result for paginated data.
    
    Includes pagination metadata along with the result data.
    """
    
    total: Optional[int] = None
    page: Optional[int] = None
    per_page: Optional[int] = None
    total_pages: Optional[int] = None
    
    @classmethod
    def paginated(cls,
                  data: T,
                  total: int,
                  page: int,
                  per_page: int,
                  metadata: Optional[Dict[str, Any]] = None) -> 'PagedResult[T]':
        """
        Create a paginated successful result.
        
        Args:
            data: The page of data
            total: Total number of items
            page: Current page number
            per_page: Items per page
            metadata: Optional additional metadata
            
        Returns:
            A PagedResult instance
        """
        total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        
        return cls(
            success=True,
            data=data,
            error=None,
            error_code=None,
            metadata=metadata,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
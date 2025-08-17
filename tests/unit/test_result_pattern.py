"""
Tests for Result Pattern Implementation
"""

import pytest
from services.common.result import Result, PagedResult


class TestResultPattern:
    """Test suite for Result pattern"""
    
    def test_success_result(self):
        """Test creating a successful result"""
        data = {"id": 1, "name": "Test"}
        result = Result.success(data)
        
        assert result.is_success == True
        assert result.is_failure == False
        assert result.data == data
        assert result.error is None
        assert result.error_code is None
        assert bool(result) == True
    
    def test_failure_result(self):
        """Test creating a failure result"""
        error_msg = "Not found"
        error_code = "NOT_FOUND"
        result = Result.failure(error_msg, code=error_code)
        
        assert result.is_success == False
        assert result.is_failure == True
        assert result.data is None
        assert result.error == error_msg
        assert result.error_code == error_code
        assert bool(result) == False
    
    def test_success_with_metadata(self):
        """Test successful result with metadata"""
        data = "test_data"
        metadata = {"timestamp": "2025-01-01", "version": "1.0"}
        result = Result.success(data, metadata=metadata)
        
        assert result.data == data
        assert result.metadata == metadata
    
    def test_failure_with_metadata(self):
        """Test failure result with metadata"""
        error = "Validation failed"
        metadata = {"field": "email", "value": "invalid"}
        result = Result.failure(error, metadata=metadata)
        
        assert result.error == error
        assert result.metadata == metadata
    
    def test_unwrap_success(self):
        """Test unwrapping successful result"""
        data = [1, 2, 3]
        result = Result.success(data)
        
        assert result.unwrap() == data
    
    def test_unwrap_failure_raises(self):
        """Test unwrapping failure result raises error"""
        result = Result.failure("Error occurred")
        
        with pytest.raises(ValueError) as excinfo:
            result.unwrap()
        assert "Cannot unwrap a failure result" in str(excinfo.value)
    
    def test_unwrap_or_success(self):
        """Test unwrap_or with successful result"""
        data = "success_data"
        default = "default_data"
        result = Result.success(data)
        
        assert result.unwrap_or(default) == data
    
    def test_unwrap_or_failure(self):
        """Test unwrap_or with failure result"""
        default = "default_data"
        result = Result.failure("Error")
        
        assert result.unwrap_or(default) == default
    
    def test_map_success(self):
        """Test mapping function over successful result"""
        result = Result.success(5)
        mapped = result.map(lambda x: x * 2)
        
        assert mapped.is_success == True
        assert mapped.data == 10
    
    def test_map_failure(self):
        """Test mapping function over failure result"""
        result = Result.failure("Error", code="ERR")
        mapped = result.map(lambda x: x * 2)
        
        assert mapped.is_failure == True
        assert mapped.error == "Error"
        assert mapped.error_code == "ERR"
    
    def test_repr_success(self):
        """Test string representation of success"""
        result = Result.success("data")
        repr_str = repr(result)
        
        assert "Result.success" in repr_str
        assert "data='data'" in repr_str
    
    def test_repr_failure(self):
        """Test string representation of failure"""
        result = Result.failure("error", code="CODE")
        repr_str = repr(result)
        
        assert "Result.failure" in repr_str
        assert "error='error'" in repr_str
        assert "code='CODE'" in repr_str


class TestPagedResult:
    """Test suite for PagedResult pattern"""
    
    def test_paginated_result(self):
        """Test creating a paginated result"""
        data = [1, 2, 3, 4, 5]
        result = PagedResult.paginated(
            data=data,
            total=100,
            page=1,
            per_page=5
        )
        
        assert result.is_success == True
        assert result.data == data
        assert result.total == 100
        assert result.page == 1
        assert result.per_page == 5
        assert result.total_pages == 20
    
    def test_paginated_with_metadata(self):
        """Test paginated result with metadata"""
        data = ["item1", "item2"]
        metadata = {"query": "search_term"}
        result = PagedResult.paginated(
            data=data,
            total=50,
            page=2,
            per_page=2,
            metadata=metadata
        )
        
        assert result.data == data
        assert result.metadata == metadata
        assert result.total_pages == 25
    
    def test_paginated_single_page(self):
        """Test paginated result with single page"""
        data = [1, 2, 3]
        result = PagedResult.paginated(
            data=data,
            total=3,
            page=1,
            per_page=10
        )
        
        assert result.total_pages == 1
    
    def test_paginated_empty_result(self):
        """Test paginated result with no data"""
        result = PagedResult.paginated(
            data=[],
            total=0,
            page=1,
            per_page=10
        )
        
        assert result.data == []
        assert result.total == 0
        assert result.total_pages == 0
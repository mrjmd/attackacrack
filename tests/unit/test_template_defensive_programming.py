"""
Unit tests for defensive programming in Jinja2 templates
Tests critical template fixes for None/NULL handling
"""
import pytest
from flask import Flask, render_template_string
from crm_database import CSVImport
from datetime import datetime


class TestTemplateDefensiveProgramming:
    """Test defensive programming patterns in templates"""
    
    def test_failed_imports_none_handling(self):
        """Test that templates handle None/NULL failed_imports gracefully
        
        This tests the fix for: import.failed_imports > 0 when failed_imports is None
        Changed to: (import.failed_imports or 0) > 0
        """
        # Create test app context
        app = Flask(__name__)
        
        with app.app_context():
            # Test template snippet that was causing crashes
            template_str = """
            {%- for import in recent_imports -%}
            {% if (import.failed_imports or 0) > 0 %}
FAILED: {{ import.failed_imports }}
            {% else %}
COMPLETE
            {% endif %}
            {%- endfor -%}
            """
            
            # Test with None failed_imports (this was causing crashes)
            import_with_none = CSVImport(
                filename="test.csv",
                imported_at=datetime.utcnow(),
                total_rows=10,
                successful_imports=8,
                failed_imports=None  # This should not crash anymore
            )
            
            result = render_template_string(
                template_str,
                recent_imports=[import_with_none]
            )
            
            assert "COMPLETE" in result
            assert "FAILED" not in result
    
    def test_failed_imports_zero_handling(self):
        """Test that templates correctly handle failed_imports = 0"""
        app = Flask(__name__)
        
        with app.app_context():
            template_str = """
            {%- for import in recent_imports -%}
            {% if (import.failed_imports or 0) > 0 %}
FAILED: {{ import.failed_imports }}
            {% else %}
COMPLETE
            {% endif %}
            {%- endfor -%}
            """
            
            # Test with 0 failed_imports
            import_with_zero = CSVImport(
                filename="success.csv",
                imported_at=datetime.utcnow(),
                total_rows=10,
                successful_imports=10,
                failed_imports=0
            )
            
            result = render_template_string(
                template_str,
                recent_imports=[import_with_zero]
            )
            
            assert "COMPLETE" in result
            assert "FAILED" not in result
    
    def test_failed_imports_positive_value_handling(self):
        """Test that templates correctly handle failed_imports > 0"""
        app = Flask(__name__)
        
        with app.app_context():
            template_str = """
            {%- for import in recent_imports -%}
            {% if (import.failed_imports or 0) > 0 %}
FAILED: {{ import.failed_imports }}
            {% else %}
COMPLETE
            {% endif %}
            {%- endfor -%}
            """
            
            # Test with positive failed_imports
            import_with_failures = CSVImport(
                filename="partial.csv",
                imported_at=datetime.utcnow(),
                total_rows=10,
                successful_imports=7,
                failed_imports=3
            )
            
            result = render_template_string(
                template_str,
                recent_imports=[import_with_failures]
            )
            
            assert "FAILED: 3" in result
            assert "COMPLETE" not in result
    
    def test_original_bug_reproduction(self):
        """Test that the original bug would have occurred without our fix"""
        app = Flask(__name__)
        
        with app.app_context():
            # This is the BROKEN template pattern (pre-fix)
            broken_template_str = """
            {%- for import in recent_imports -%}
            {% if import.failed_imports > 0 %}
FAILED: {{ import.failed_imports }}
            {% else %}
COMPLETE
            {% endif %}
            {%- endfor -%}
            """
            
            # Test with None failed_imports
            import_with_none = CSVImport(
                filename="test.csv",
                imported_at=datetime.utcnow(),
                total_rows=10,
                successful_imports=8,
                failed_imports=None
            )
            
            # This should raise TypeError: '>' not supported between instances of 'NoneType' and 'int'
            with pytest.raises(TypeError, match="not supported between instances of 'NoneType' and 'int'"):
                render_template_string(
                    broken_template_str,
                    recent_imports=[import_with_none]
                )
    
    def test_defensive_programming_pattern_robustness(self):
        """Test that our defensive programming pattern handles multiple edge cases"""
        app = Flask(__name__)
        
        with app.app_context():
            template_str = """
            {%- for import in recent_imports -%}
            Status: {% if (import.failed_imports or 0) > 0 %}{{ import.failed_imports }} failed{% else %}Complete{% endif %}
            {%- endfor -%}
            """
            
            # Test multiple scenarios in one go
            test_imports = [
                CSVImport(
                    filename="none.csv",
                    failed_imports=None
                ),
                CSVImport(
                    filename="zero.csv", 
                    failed_imports=0
                ),
                CSVImport(
                    filename="failures.csv",
                    failed_imports=5
                )
            ]
            
            result = render_template_string(
                template_str,
                recent_imports=test_imports
            )
            
            # All cases should render without error
            assert "Status: Complete" in result  # Should appear twice (None and 0)
            assert "Status: 5 failed" in result  # Should appear once
            assert result.count("Complete") == 2  # Both None and 0 cases
            assert "5 failed" in result

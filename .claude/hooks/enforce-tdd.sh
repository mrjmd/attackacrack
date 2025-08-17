#!/bin/bash
# TDD Enforcement Hook - Prevents implementation without tests
# Place in .claude/hooks/ and configure in settings.json

# Check if this is a Write or Edit operation on implementation files
if [[ "$1" == "Write" || "$1" == "Edit" || "$1" == "MultiEdit" ]]; then
    FILE_PATH="$2"
    
    # Check if editing service, route, or other implementation files
    if [[ "$FILE_PATH" == *"/services/"* ]] || 
       [[ "$FILE_PATH" == *"/routes/"* ]] || 
       [[ "$FILE_PATH" == *"/repositories/"* ]] ||
       [[ "$FILE_PATH" == *"/tasks/"* ]]; then
        
        # Extract the module name
        MODULE_NAME=$(basename "$FILE_PATH" .py)
        
        # Determine expected test file
        if [[ "$FILE_PATH" == *"/services/"* ]]; then
            TEST_FILE="tests/test_services/test_${MODULE_NAME}.py"
        elif [[ "$FILE_PATH" == *"/routes/"* ]]; then
            TEST_FILE="tests/test_routes/test_${MODULE_NAME}.py"
        elif [[ "$FILE_PATH" == *"/repositories/"* ]]; then
            TEST_FILE="tests/test_repositories/test_${MODULE_NAME}.py"
        else
            TEST_FILE="tests/test_${MODULE_NAME}.py"
        fi
        
        # Check if test file exists
        if [[ ! -f "$TEST_FILE" ]]; then
            echo "❌ TDD VIOLATION: No test file found at $TEST_FILE"
            echo "You must write tests BEFORE implementation!"
            echo "Create the test file first with failing tests."
            exit 1
        fi
        
        # Check if tests were modified recently (within last hour)
        TEST_MOD_TIME=$(stat -f %m "$TEST_FILE" 2>/dev/null || stat -c %Y "$TEST_FILE" 2>/dev/null)
        CURRENT_TIME=$(date +%s)
        TIME_DIFF=$((CURRENT_TIME - TEST_MOD_TIME))
        
        # If test file is older than 1 hour, likely not following TDD
        if [[ $TIME_DIFF -gt 3600 ]]; then
            echo "⚠️  WARNING: Test file hasn't been modified recently"
            echo "Following TDD? Tests should be written first!"
            echo "Test file: $TEST_FILE"
            echo "Last modified: $((TIME_DIFF / 60)) minutes ago"
        fi
    fi
fi

# Check if running tests before committing
if [[ "$1" == "git" && "$2" == "commit" ]]; then
    echo "📋 Running tests before commit..."
    
    # Run tests
    docker-compose exec -T web pytest --tb=short -q
    TEST_RESULT=$?
    
    if [[ $TEST_RESULT -ne 0 ]]; then
        echo "❌ Tests are failing! Fix them before committing."
        exit 1
    fi
    
    echo "✅ All tests passing!"
fi

exit 0
#!/bin/bash

# Large Scale OpenPhone Import Runner
# Handles Docker execution with proper timeout settings and auto-resume

echo "🚀 Large Scale OpenPhone Import Runner"
echo "========================================"

# Set Docker timeout to 6 hours (21600 seconds) 
export DOCKER_CLIENT_TIMEOUT=21600
export COMPOSE_HTTP_TIMEOUT=21600

# Parse arguments
RESUME_FLAG=""
RESET_FLAG=""
if [[ "$1" == "--resume" ]]; then
    RESUME_FLAG="--resume"
    echo "🔄 Resuming from previous progress"
elif [[ "$1" == "--reset" ]]; then
    RESET_FLAG="--reset"
    echo "🗑️  Resetting and starting fresh"
else
    RESUME_FLAG="--auto-resume"
    echo "🤖 Auto-resume mode (will resume if recent progress exists)"
fi

echo "📦 Starting import in Docker container..."
echo "⏱️  Import will run for up to 6 hours with automatic checkpoints"
echo "📋 Monitor progress: docker-compose logs -f web"
echo "🛑 Stop gracefully: docker-compose exec web pkill -SIGINT python"
echo ""

# Run the import with timeout handling
timeout 21600 docker-compose exec -T web python large_scale_import.py $RESUME_FLAG $RESET_FLAG

# Check the exit code
EXIT_CODE=$?

echo ""
echo "========================================"

if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ IMPORT COMPLETED SUCCESSFULLY!"
    echo "🎯 All 7000+ conversations have been imported"
    echo "🌐 View your data: http://localhost:5000/contacts/conversations"
    echo "📊 Check database: docker-compose exec web python import_manager.py status"
elif [ $EXIT_CODE -eq 1 ]; then
    echo "⚠️  IMPORT WAS INTERRUPTED OR TIMED OUT"
    echo "💾 Progress has been automatically saved"
    echo "🔄 Resume with: ./run_large_import.sh --resume"
    echo "📊 Check progress: docker-compose exec web python import_manager.py status"
elif [ $EXIT_CODE -eq 2 ]; then
    echo "🚨 CRITICAL ERRORS DETECTED - IMPORT ABORTED"
    echo "🛠️  Code issues need to be fixed before continuing"
    echo "🔄 After fixing, restart with: ./run_large_import.sh --reset"
    echo "📋 Check logs for error details: docker-compose logs web"
elif [ $EXIT_CODE -eq 124 ]; then
    echo "⏰ IMPORT TIMED OUT (6+ hours)"
    echo "💾 Progress should be saved automatically"
    echo "🔄 Resume with: ./run_large_import.sh --resume"
else
    echo "❌ UNEXPECTED ERROR (Exit Code: $EXIT_CODE)"
    echo "📋 Check logs: docker-compose logs web"
fi

echo "========================================"
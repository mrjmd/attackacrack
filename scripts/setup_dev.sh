#!/bin/bash
# Setup development environment

echo "Setting up development environment..."

# Install development dependencies
echo "Installing development dependencies..."
pip install flake8 bandit pytest pytest-cov

# Make scripts executable
echo "Making scripts executable..."
chmod +x scripts/*.py scripts/*.sh

# Setup git hooks
echo "Setting up git hooks..."
chmod +x .git/hooks/pre-commit 2>/dev/null || true

echo "✅ Development environment setup complete!"
echo ""
echo "You can now use:"
echo "  make lint       - Run linting checks"
echo "  make security   - Run security scan"
echo "  make test       - Run tests in Docker"
echo "  make check-all  - Run all checks"
echo ""
echo "Or use the Python script directly:"
echo "  python scripts/lint_check.py"
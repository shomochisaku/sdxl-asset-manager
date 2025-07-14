#!/bin/bash
# Local CI simulation script for SDXL Asset Manager
# This script runs the same checks as CI to catch issues early

set -e  # Exit on any error

echo "🔍 Running local CI simulation..."
echo "=================================="

# Check if we're in the project root
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: Please run this script from the project root directory"
    exit 1
fi

echo "📋 Step 1: Type checking with mypy..."
python3 -m mypy src/ || {
    echo "❌ Type checking failed"
    exit 1
}
echo "✅ Type checking passed"

echo ""
echo "🔍 Step 2: Linting with ruff..."
python3 -m ruff check src/ --statistics || {
    echo "❌ Linting failed"
    exit 1
}
echo "✅ Linting passed"

echo ""
echo "🧪 Step 3: Running tests..."
python3 -m pytest tests/ --tb=short || {
    echo "❌ Tests failed"
    exit 1
}
echo "✅ Tests passed"

echo ""
echo "🎉 All checks passed! Your code is ready for CI."
echo "💡 To run this automatically before commits, install pre-commit:"
echo "   pip install pre-commit && pre-commit install"
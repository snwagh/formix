#!/bin/bash
# Run Formix performance experiments

echo "Formix Network Performance Experiments"
echo "======================================"

# Install dependencies if needed
echo "Checking dependencies..."
uv pip install matplotlib numpy

# Run experiments
echo ""
echo "Choose experiment suite:"
echo "1. Quick latency test (1 minute)"
echo "2. Full experiment suite (10-15 minutes)"
echo "3. Custom experiment"

read -p "Enter choice (1-3): " choice

case $choice in
    1)
        echo "Running quick latency test..."
        echo "Q" | uv run python experiments.py
        ;;
    2)
        echo "Running full experiment suite..."
        echo "A" | uv run python experiments.py
        ;;
    3)
        echo "Starting custom experiment environment..."
        uv run python experiments.py
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "Experiment complete! Check experiment_results/ for graphs and data."
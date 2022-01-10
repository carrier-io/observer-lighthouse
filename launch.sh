#!/bin/bash

python3 minio_tests_reader.py
echo "Scripts downloaded"
echo "Start test"
lhci autorun
echo "Test is done. Results processing..."
python3 results_processing.py
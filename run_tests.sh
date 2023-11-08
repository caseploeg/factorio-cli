#!/bin/bash

# Directories
TESTCASE_DIR="./testcases"
EXPECTED_DIR="./expected"

# Check if testrunner.sh is executable
if [ ! -x "./testrunner.sh" ]; then
    echo "Error: testrunner.sh is not executable or not found."
    exit 1
fi

# Check if testcase and expected directories exist
if [ ! -d "$TESTCASE_DIR" ] || [ ! -d "$EXPECTED_DIR" ]; then
    echo "Error: The required directories do not exist."
    exit 1
fi

# Loop through files in testcase directory
for testcase in "$TESTCASE_DIR"/*; do
    # Extract the filename without the path
    filename=$(basename "$testcase")
    
    # Corresponding file in expected directory
    expected="$EXPECTED_DIR/$filename"
    
    # Check if the corresponding expected file exists
    if [ -f "$expected" ]; then
        # Run testrunner.sh with testcase and expected files
        if ! ./testrunner.sh "$testcase" "$expected"; then
            echo "Test failed: $filename"
        fi
    else
        echo "Expected file for '$filename' not found."
    fi
done

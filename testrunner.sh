#!/bin/bash

# Check if at least two arguments are given (# - number of arguments)
if [ "$#" -lt 2 ]; then
    echo "Usage: $0 <file_to_modify> <file_to_compare>"
    exit 1
fi

# Assign the arguments to variables
FILE_TO_MODIFY=$1
FILE_TO_COMPARE=$2

# Create a temporary file
TEMP_FILE=$(mktemp)
TEMP_SAVE_FILE=$(mktemp)

# Ensure temporary file gets deleted on script exit or interruption
trap "rm -f $TEMP_FILE" EXIT INT TERM HUP
trap "rm -f $TEMP_SAVE_FILE" EXIT INT TERM HUP

# Add the line to the temporary file
echo "clear" > "$TEMP_FILE"
cat "$FILE_TO_MODIFY" >> "$TEMP_FILE"
echo "save $TEMP_SAVE_FILE" >> "$TEMP_FILE"

# Run the command with the temporary file as stdin and capture the output
COMMAND_OUTPUT=$(python3 ./main.py < "$TEMP_FILE")

# Run diff against the output and the second file
# If diff returns anything, echo "Test fail"
if diff "$TEMP_SAVE_FILE" "$FILE_TO_COMPARE" > /dev/null; then
    echo "Test pass"
else
    echo "Test fail"
    exit 1
fi

# The script will automatically clean up the temporary files
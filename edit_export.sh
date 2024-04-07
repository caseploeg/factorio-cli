#!/bin/bash

# Check if a file name is provided
if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <filename>"
    exit 1
fi

# File to process
FILENAME=$1

# Check if the file exists
if [ ! -f "$FILENAME" ]; then
    echo "File does not exist: $FILENAME"
    exit 1
fi

# Process the file: Remove lines that exactly match "prod"
sed '/^prod$/d' "$FILENAME" > "${FILENAME}_edited"

# Optional: Rename the edited file to original, to directly modify the original file uncomment the next line
# mv "${FILENAME}_edited" "$FILENAME"

echo "Processed file is ${FILENAME}_edited"


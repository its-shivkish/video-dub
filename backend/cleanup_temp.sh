#!/bin/bash

# Cleanup script for video-dub temporary files

echo "Cleaning up video-dub temporary files..."

if [ -d "/tmp/video-dub" ]; then
    echo "Found temp directory: /tmp/video-dub"
    ls -la /tmp/video-dub/
    echo ""
    read -p "Delete all temp files? (y/N): " confirm
    
    if [[ $confirm == [yY] ]]; then
        rm -rf /tmp/video-dub
        echo "✅ All temp files deleted"
    else
        echo "ℹ️  Temp files preserved"
    fi
else
    echo "No temp files found"
fi 

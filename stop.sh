#!/bin/bash

set -e

echo "Stopping existing processes..."

if [ -f app.pid ]; then
    PID=$(cat app.pid)
    if ps -p $PID > /dev/null; then
        echo "Stopping Backend process $PID"
        kill $PID
    fi
    rm -f app.pid
else
    echo "No Backend PID file found"
fi

if [ -f ui.pid ]; then
    PID=$(cat ui.pid)
    if ps -p $PID > /dev/null; then
        echo "Stopping Frontend process $PID"
        kill $PID
    fi
    rm -f ui.pid
else
    echo "No Frontend PID file found"
fi

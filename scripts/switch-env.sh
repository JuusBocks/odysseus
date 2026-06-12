#!/bin/bash
# Quickly switch between environments (branches) for testing locally.

ENV=$1
if [ -z "$ENV" ]; then
    echo "Usage: ./scripts/switch-env.sh [dev|nonprod|prod]"
    exit 1
fi

if [ "$ENV" = "dev" ]; then
    BRANCH="leounib-dev"
elif [ "$ENV" = "nonprod" ]; then
    BRANCH="leounib-nonprod"
elif [ "$ENV" = "prod" ]; then
    BRANCH="leounib-main"
else
    echo "Unknown environment: $ENV"
    echo "Available environments: dev, nonprod, prod"
    exit 1
fi

echo "Switching to $BRANCH..."
git fetch origin
git switch $BRANCH
git pull origin $BRANCH

echo "Setting environment to $ENV..."
export ODYSSEUS_ENVIRONMENT=$ENV
export ODYSSEUS_REF=$BRANCH

echo "Starting Odysseus..."
# Use the macOS launcher to start the app natively
./start-macos.sh

#!/bin/bash

# # Rerun instance, Register ssh keys to ssh-agent, Then build the container, and Run the instance
# This script automates the process of updating and redeploying the megamind application.
# It performs the following steps:
# 1. Starts the ssh-agent and adds the necessary SSH keys.
# 2. Navigates to the megamind project directory.
# 3. Pulls the latest changes from the main branch.
# 4. Builds the Docker containers with the new changes.
# 5. Restarts the Docker services, forcing a recreation of the containers.

echo "### Starting ssh-agent and adding SSH keys... ###"
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/frappe_mcp_server
ssh-add ~/.ssh/megamind
echo "### SSH keys added successfully. ###"

echo ""
echo "### Changing directory to megamind... ###"
# Assuming 'megamind' directory is in the user's home directory.
# If not, you may need to provide the full path e.g., cd /path/to/your/megamind
cd ~/megamind || { echo "Error: Could not change directory to megamind. Aborting."; exit 1; }
echo "### Successfully changed directory. ###"

echo ""
echo "### Pulling latest changes from git... ###"
git pull origin main
echo "### Git pull completed. ###"

echo ""
echo "### Building new changes with Docker Compose... ###"
sudo -E docker compose build
echo "### Docker Compose build finished. ###"

echo ""
echo "### Recreating and running the Docker Compose instance... ###"
docker compose up -d --force-recreate
echo "### Instance is up and running. ###"

echo ""
echo "### Deployment script finished successfully. ###"
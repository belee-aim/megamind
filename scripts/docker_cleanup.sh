#!/bin/bash

# This script cleans up unused Docker resources, including:
# - All stopped containers
# - All dangling images (images not tagged or used by any container)
# - All unused networks
# - All build cache

echo "### Starting Docker cleanup... ###"

# Prune stopped containers
echo ""
echo "### Removing all stopped containers... ###"
docker container prune -f

# Prune unused networks
echo ""
echo "### Removing all unused networks... ###"
docker network prune -f

# Prune dangling and unused images
# The 'docker image prune -a' command removes all images that are not
# associated with at least one container. The '-f' flag forces the removal
# without prompting for confirmation.
echo ""
echo "### Removing all unused images (those not associated with any container)... ###"
docker image prune -a -f

# Prune build cache
echo ""
echo "### Cleaning up Docker build cache... ###"
docker builder prune -f

echo ""
echo "### Docker cleanup process has been successfully completed. ###"
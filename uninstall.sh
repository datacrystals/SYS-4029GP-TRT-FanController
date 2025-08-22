#!/bin/bash
# Fan Controller Uninstallation Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}SuperMicro Fan Controller Uninstallation${NC}"
echo "=============================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root using sudo${NC}"
    exit 1
fi

# Stop and disable service
echo -e "${YELLOW}Stopping and disabling service...${NC}"
systemctl stop fan-controller.service 2>/dev/null || true
systemctl disable fan-controller.service 2>/dev/null || true

# Remove service file
echo -e "${YELLOW}Removing service file...${NC}"
rm -f /etc/systemd/system/fan-controller.service

# Remove installation directory
echo -e "${YELLOW}Removing installation files...${NC}"
INSTALL_DIR="/opt/FanController"
if [ -d "$INSTALL_DIR" ]; then
    rm -rf "$INSTALL_DIR"
    echo -e "${GREEN}✓ Removed $INSTALL_DIR${NC}"
else
    echo -e "${YELLOW}Installation directory not found${NC}"
fi

# Reload systemd
systemctl daemon-reload

echo -e "${GREEN}Uninstallation complete!${NC}"
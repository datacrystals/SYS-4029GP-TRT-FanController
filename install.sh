#!/bin/bash
# Fan Controller Installation Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}SuperMicro Fan Controller Installation${NC}"
echo "=========================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root using sudo${NC}"
    exit 1
fi

# Check for required tools
echo -e "${YELLOW}Checking for required tools...${NC}"
for tool in ipmitool rocm-smi; do
    if ! command -v $tool &> /dev/null; then
        echo -e "${RED}Error: $tool is not installed${NC}"
        echo "Please install it with: sudo apt install $tool"
        exit 1
    fi
    echo -e "${GREEN}✓ $tool found${NC}"
done

# Create installation directory
echo -e "${YELLOW}Creating installation directory...${NC}"
INSTALL_DIR="/opt/FanController"
mkdir -p $INSTALL_DIR
chmod 755 $INSTALL_DIR

# Copy the fan controller script
echo -e "${YELLOW}Installing fan controller script...${NC}"
SCRIPT_NAME="fan_controller.py"
if [ -f "$SCRIPT_NAME" ]; then
    cp "$SCRIPT_NAME" "$INSTALL_DIR/"
    chmod 755 "$INSTALL_DIR/$SCRIPT_NAME"
    echo -e "${GREEN}✓ Script copied to $INSTALL_DIR/${NC}"
else
    echo -e "${RED}Error: fan_controller.py not found in current directory${NC}"
    exit 1
fi

# Install systemd service file
echo -e "${YELLOW}Installing systemd service...${NC}"
SERVICE_FILE="fan-controller.service"
if [ -f "$SERVICE_FILE" ]; then
    cp "$SERVICE_FILE" /etc/systemd/system/
    chmod 644 /etc/systemd/system/fan-controller.service
    echo -e "${GREEN}✓ Service file installed${NC}"
else
    echo -e "${RED}Error: fan-controller.service not found${NC}"
    exit 1
fi

# Reload systemd and enable service
echo -e "${YELLOW}Setting up systemd service...${NC}"
systemctl daemon-reload
systemctl enable fan-controller.service

echo -e "${GREEN}✓ Service enabled to start on boot${NC}"

# Start the service
echo -e "${YELLOW}Starting fan controller service...${NC}"
if systemctl start fan-controller.service; then
    echo -e "${GREEN}✓ Service started successfully${NC}"
else
    echo -e "${RED}Warning: Could not start service automatically${NC}"
    echo "You may need to start it manually: sudo systemctl start fan-controller.service"
fi

# Show service status
echo -e "${YELLOW}Service status:${NC}"
systemctl status fan-controller.service --no-pager -l

echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo ""
echo -e "${YELLOW}Useful commands:${NC}"
echo "  Check status:    sudo systemctl status fan-controller.service"
echo "  View logs:       sudo journalctl -u fan-controller.service -f"
echo "  Restart service: sudo systemctl restart fan-controller.service"
echo "  Stop service:    sudo systemctl stop fan-controller.service"
echo ""
echo -e "${GREEN}The fan controller will now start automatically on boot.${NC}"
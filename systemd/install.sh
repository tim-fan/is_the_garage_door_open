#!/bin/bash
# Install systemd services for garage door monitor

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_DIR="/etc/systemd/system"

echo "Installing systemd service files..."

# Copy service files
sudo cp "$SCRIPT_DIR/presence-monitor.service" "$SERVICE_DIR/"
sudo cp "$SCRIPT_DIR/garage-monitor.service" "$SERVICE_DIR/"

echo "Service files installed."
echo ""
echo "Next steps:"
echo "1. Create environment file for API key:"
echo "   mkdir -p ~/.config/garage-monitor"
echo "   cp $SCRIPT_DIR/env.example ~/.config/garage-monitor/env"
echo "   vim ~/.config/garage-monitor/env  # Edit and add your GEMINI_API_KEY"
echo "   chmod 600 ~/.config/garage-monitor/env"
echo ""
echo "2. Update the User and WorkingDirectory paths in the service files if needed:"
echo "   sudo vim /etc/systemd/system/presence-monitor.service"
echo "   sudo vim /etc/systemd/system/garage-monitor.service"
echo ""
echo "3. Reload systemd and enable services:"
echo "   sudo systemctl daemon-reload"
echo "   sudo systemctl enable presence-monitor"
echo "   sudo systemctl enable garage-monitor"
echo ""
echo "4. Start services:"
echo "   sudo systemctl start presence-monitor"
echo "   sudo systemctl start garage-monitor"
echo ""
echo "5. Check status:"
echo "   sudo systemctl status presence-monitor"
echo "   sudo systemctl status garage-monitor"
echo ""
echo "6. View logs:"
echo "   sudo journalctl -u presence-monitor -f"
echo "   sudo journalctl -u garage-monitor -f"

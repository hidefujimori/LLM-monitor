#!/bin/bash
# Run this script on the LLM machine to install and enable the service
set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_NAME="llm-monitor"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "=== LLM Monitor service installer ==="
echo "Repo: ${REPO_DIR}"

# Stop existing service if running
if systemctl is-active --quiet "${SERVICE_NAME}"; then
    echo "Stopping existing service..."
    sudo systemctl stop "${SERVICE_NAME}"
fi

# Install service file
echo "Installing ${SERVICE_FILE}..."
sudo cp "${REPO_DIR}/systemd/${SERVICE_NAME}.service" "${SERVICE_FILE}"
sudo systemctl daemon-reload

# Enable and start
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl start "${SERVICE_NAME}"

echo ""
echo "=== Done ==="
systemctl status "${SERVICE_NAME}" --no-pager
echo ""
echo "Useful commands:"
echo "  journalctl -u ${SERVICE_NAME} -f      # Follow logs"
echo "  systemctl status ${SERVICE_NAME}       # Check status"
echo "  systemctl restart ${SERVICE_NAME}      # Restart"
echo "  systemctl stop ${SERVICE_NAME}         # Stop"

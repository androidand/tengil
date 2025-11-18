#!/bin/bash
set -e

SERVER="root@192.168.1.42"
CONTAINER="hass-mcp"

# Load environment if available
if [ -f "../.env" ]; then
    source ../.env
    SERVER="root@${PROXMOX_SERVER:-192.168.1.42}"
fi

case "$1" in
    "list")
        echo "📋 Environment variables (values hidden):"
        ssh "$SERVER" "tg env list $CONTAINER"
        ;;
    "show")
        echo "📋 Environment variables with values:"
        ssh "$SERVER" "tg env list $CONTAINER --show-values"
        ;;
    "set")
        if [ -z "$2" ] || [ -z "$3" ]; then
            echo "❌ Usage: $0 set VARIABLE_NAME value"
            exit 1
        fi
        echo "🔧 Setting $2=$3..."
        ssh "$SERVER" "tg env set $CONTAINER '$2' '$3' --restart hass-mcp"
        ;;
    "edit")
        echo "🔧 Opening environment editor in container..."
        ssh "$SERVER" "pct exec $CONTAINER -- nano /app/.env"
        echo "🔄 Restarting service to pick up changes..."
        ssh "$SERVER" "pct exec $CONTAINER -- systemctl restart hass-mcp"
        ;;
    "sync")
        if [ ! -f "../.env" ]; then
            echo "❌ No .env file found in parent directory"
            exit 1
        fi
        echo "🔄 Syncing local .env to container..."
        scp ../.env "$SERVER:/tmp/app.env"
        ssh "$SERVER" "tg env sync $CONTAINER /tmp/app.env --restart hass-mcp"
        ssh "$SERVER" "rm -f /tmp/app.env"
        echo "✅ Environment synced and service restarted"
        ;;
    "restart")
        echo "🔄 Restarting service..."
        ssh "$SERVER" "pct exec $CONTAINER -- systemctl restart hass-mcp"
        echo "✅ Service restarted"
        ;;
    "logs")
        echo "📜 Service logs (press Ctrl+C to exit):"
        ssh "$SERVER" "pct exec $CONTAINER -- journalctl -u hass-mcp -f"
        ;;
    "status")
        echo "📊 Service status:"
        ssh "$SERVER" "pct exec $CONTAINER -- systemctl status hass-mcp --no-pager"
        ;;
    *)
        echo "🔧 Environment Management for Home Assistant MCP Server"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  list     - List environment variable names"
        echo "  show     - Show environment variables with values"
        echo "  set      - Set a single environment variable"
        echo "  edit     - Edit environment variables in container"
        echo "  sync     - Sync local .env file to container"
        echo "  restart  - Restart the service"
        echo "  logs     - View service logs"
        echo "  status   - Show service status"
        echo ""
        echo "Examples:"
        echo "  $0 list                    # List all env vars"
        echo "  $0 set HASS_MOCK false     # Set single variable"
        echo "  $0 sync                    # Push local .env to container"
        echo "  $0 logs                    # Watch logs in real-time"
        ;;
esac
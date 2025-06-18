#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo -e "${BLUE}🚀 ZulipChat MCP Server Installer${NC}"
    echo "=================================================="
}

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        OS="windows"
    else
        OS="unknown"
    fi
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is required but not installed."
        print_info "Please install Docker from https://docs.docker.com/get-docker/"
        
        if [[ "$OS" == "linux" ]]; then
            print_info "On Linux, you can install Docker with:"
            echo "  curl -fsSL https://get.docker.com -o get-docker.sh"
            echo "  sudo sh get-docker.sh"
        elif [[ "$OS" == "macos" ]]; then
            print_info "On macOS, you can install Docker with:"
            echo "  brew install --cask docker"
        fi
        
        exit 1
    fi
    
    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        print_error "Docker is installed but not running."
        print_info "Please start Docker and try again."
        exit 1
    fi
    
    print_success "Docker is installed and running"
}

# Pull Docker image
pull_image() {
    print_info "Pulling ZulipChat MCP Docker image..."
    
    if docker pull ghcr.io/akougkas/zulipchat-mcp:latest; then
        print_success "Docker image pulled successfully"
    else
        print_error "Failed to pull Docker image"
        print_info "Trying to build from source..."
        build_from_source
    fi
}

# Build from source if image pull fails
build_from_source() {
    print_info "Cloning repository..."
    
    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR"
    
    if git clone https://github.com/akougkas/zulipchat-mcp.git; then
        cd zulipchat-mcp
        print_info "Building Docker image from source..."
        
        if docker build -t ghcr.io/akougkas/zulipchat-mcp:latest .; then
            print_success "Docker image built successfully"
        else
            print_error "Failed to build Docker image"
            exit 1
        fi
    else
        print_error "Failed to clone repository"
        exit 1
    fi
    
    # Clean up
    cd /
    rm -rf "$TEMP_DIR"
}

# Create configuration directory
create_config_dir() {
    CONFIG_DIR="$HOME/.config/zulipchat-mcp"
    
    if [[ ! -d "$CONFIG_DIR" ]]; then
        mkdir -p "$CONFIG_DIR"
        print_success "Created configuration directory: $CONFIG_DIR"
    else
        print_info "Configuration directory already exists: $CONFIG_DIR"
    fi
}

# Create example configuration
create_example_config() {
    CONFIG_DIR="$HOME/.config/zulipchat-mcp"
    EXAMPLE_CONFIG="$CONFIG_DIR/config.json.example"
    
    cat > "$EXAMPLE_CONFIG" << 'EOF'
{
  "email": "your-bot@zulip.com",
  "api_key": "your-api-key-here",
  "site": "https://your-org.zulipchat.com"
}
EOF
    
    print_success "Created example configuration: $EXAMPLE_CONFIG"
}

# Test installation
test_installation() {
    print_info "Testing installation..."
    
    if docker run --rm ghcr.io/akougkas/zulipchat-mcp:latest python -c "from src.zulipchat_mcp import __version__; print('Version:', __version__)"; then
        print_success "Installation test passed"
    else
        print_warning "Installation test failed, but the image seems to be available"
    fi
}

# Create helper scripts
create_helper_scripts() {
    SCRIPTS_DIR="$HOME/.local/bin"
    
    # Create scripts directory if it doesn't exist
    if [[ ! -d "$SCRIPTS_DIR" ]]; then
        mkdir -p "$SCRIPTS_DIR"
    fi
    
    # Create run script
    cat > "$SCRIPTS_DIR/zulipchat-mcp" << 'EOF'
#!/bin/bash
# ZulipChat MCP Server Runner

set -euo pipefail

CONTAINER_NAME="zulipchat-mcp"
IMAGE="ghcr.io/akougkas/zulipchat-mcp:latest"

case "${1:-}" in
    start)
        echo "Starting ZulipChat MCP server..."
        docker run -d \
            --name "$CONTAINER_NAME" \
            --restart unless-stopped \
            -p 3000:3000 \
            -e ZULIP_EMAIL="${ZULIP_EMAIL:-}" \
            -e ZULIP_API_KEY="${ZULIP_API_KEY:-}" \
            -e ZULIP_SITE="${ZULIP_SITE:-}" \
            -v "$HOME/.config/zulipchat-mcp:/app/.config/zulipchat-mcp:ro" \
            "$IMAGE"
        echo "✅ Server started successfully"
        ;;
    stop)
        echo "Stopping ZulipChat MCP server..."
        docker stop "$CONTAINER_NAME" || true
        docker rm "$CONTAINER_NAME" || true
        echo "✅ Server stopped"
        ;;
    restart)
        $0 stop
        sleep 2
        $0 start
        ;;
    logs)
        docker logs -f "$CONTAINER_NAME"
        ;;
    status)
        if docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}" | grep -q "$CONTAINER_NAME"; then
            echo "✅ Server is running"
            docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        else
            echo "❌ Server is not running"
        fi
        ;;
    update)
        echo "Updating ZulipChat MCP server..."
        docker pull "$IMAGE"
        $0 restart
        echo "✅ Server updated"
        ;;
    configure)
        echo "Opening configuration file..."
        ${EDITOR:-nano} "$HOME/.config/zulipchat-mcp/config.json"
        ;;
    test)
        echo "Testing configuration..."
        docker run --rm \
            -e ZULIP_EMAIL="${ZULIP_EMAIL:-}" \
            -e ZULIP_API_KEY="${ZULIP_API_KEY:-}" \
            -e ZULIP_SITE="${ZULIP_SITE:-}" \
            -v "$HOME/.config/zulipchat-mcp:/app/.config/zulipchat-mcp:ro" \
            "$IMAGE" \
            python -c "from src.zulipchat_mcp.config import ConfigManager; print('✅ Configuration valid' if ConfigManager().validate_config() else '❌ Configuration invalid')"
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|logs|status|update|configure|test}"
        echo ""
        echo "Commands:"
        echo "  start      - Start the MCP server"
        echo "  stop       - Stop the MCP server"
        echo "  restart    - Restart the MCP server"
        echo "  logs       - View server logs"
        echo "  status     - Check server status"
        echo "  update     - Update to latest version"
        echo "  configure  - Edit configuration file"
        echo "  test       - Test configuration"
        echo ""
        echo "Environment variables:"
        echo "  ZULIP_EMAIL    - Your Zulip email address"
        echo "  ZULIP_API_KEY  - Your Zulip API key"
        echo "  ZULIP_SITE     - Your Zulip site URL"
        exit 1
        ;;
esac
EOF
    
    chmod +x "$SCRIPTS_DIR/zulipchat-mcp"
    print_success "Created helper script: $SCRIPTS_DIR/zulipchat-mcp"
    
    # Add to PATH if not already there
    if [[ ":$PATH:" != *":$SCRIPTS_DIR:"* ]]; then
        print_info "Add $SCRIPTS_DIR to your PATH to use the zulipchat-mcp command globally:"
        echo "  echo 'export PATH=\"\$PATH:$SCRIPTS_DIR\"' >> ~/.bashrc"
        echo "  source ~/.bashrc"
    fi
}

# Print usage instructions
print_usage() {
    echo ""
    print_info "Installation completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Get your Zulip API credentials:"
    echo "   - Visit https://your-org.zulipchat.com"
    echo "   - Go to Settings → Account & privacy → API key"
    echo "   - Generate and copy your API key"
    echo ""
    echo "2. Configure the server:"
    echo "   export ZULIP_EMAIL='your-bot@zulip.com'"
    echo "   export ZULIP_API_KEY='your-api-key'"
    echo "   export ZULIP_SITE='https://your-org.zulipchat.com'"
    echo ""
    echo "3. Start the server:"
    echo "   zulipchat-mcp start"
    echo ""
    echo "4. Configure your MCP client (Claude Desktop, etc.):"
    echo "   See README.md for detailed instructions"
    echo ""
    echo "Helpful commands:"
    echo "  zulipchat-mcp status    - Check if server is running"
    echo "  zulipchat-mcp logs      - View server logs"
    echo "  zulipchat-mcp test      - Test your configuration"
    echo "  zulipchat-mcp configure - Edit configuration file"
    echo ""
}

# Main installation function
main() {
    print_header
    
    detect_os
    print_info "Detected OS: $OS"
    
    if [[ "$OS" == "windows" ]]; then
        print_warning "Windows detected. Please use Docker Desktop or WSL2."
        print_info "Visit: https://github.com/akougkas/zulipchat-mcp#windows-setup"
        exit 1
    fi
    
    check_docker
    pull_image
    create_config_dir
    create_example_config
    test_installation
    create_helper_scripts
    print_usage
}

# Run main function
main "$@"
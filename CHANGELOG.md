# Changelog

## [1.4.0] - 2025-09-05

### Added - Agent Communication System
- **Multi-Instance Bot Identity System**
  - Automatic project detection from git, package.json, pyproject.toml
  - Machine and session awareness (hostname, user, platform)
  - Branch tracking for distinct notification contexts
  - Persistent instance identity across restarts
- **Smart Stream Organization**
  - Personal streams per agent type (claude-code-username)
  - Project-specific topics within personal streams
  - Clean separation without stream proliferation
- **AFK (Away From Keyboard) Mode**
  - Simple toggle for notification control
  - Only sends notifications when user is away
  - Auto-return after specified hours
  - Command: `/zulipchat:afk [on|off] [reason] [hours]`
- **Agent Registration & Management**
  - `register_agent` tool with instance detection
  - `list_instances` to view all active instances
  - `cleanup_old_instances` for maintenance
- **Agent Communication Tools**
  - `agent_message` - Send project-aware notifications
  - `request_user_input` - Request input with context
  - `send_agent_status` - Real-time status updates
  - `wait_for_response` - Async response handling
- **Task Lifecycle Management**
  - `start_task` - Begin tasks with subtask tracking
  - `update_task_progress` - Progress updates with blockers
  - `complete_task` - Detailed completion summaries
  - SQLite database for persistent task storage
- **Stream Management Tools**
  - `create_stream` - Programmatic stream creation
  - `rename_stream` - Stream renaming
  - `archive_stream` - Archive with farewell messages
  - Topic management and organization
- **Dual Identity Support**
  - Bot credentials configuration (ZULIP_BOT_EMAIL, ZULIP_BOT_API_KEY)
  - Automatic bot identity for agent operations
  - Clear distinction between human and AI messages

### Changed
- Enhanced `ZulipClientWrapper` with `use_bot_identity` parameter
- Updated `ConfigManager` with bot credential support
- Modified agent tools to use instance-aware routing
- Improved notification formatting with instance prefixes

### Technical Details
- Added SQLite database (`database.py`) for persistent storage
- Created Pydantic models for agents and tasks
- Implemented `afk_state.py` for simple state management
- Added `instance_identity.py` for project/session detection
- Created modular tool architecture in `tools/` directory
- Enhanced `agent_adapters/setup_agents.py` with AFK command

## [1.3.0] - 2025-09-05

### Added
- Complete UV package manager migration as primary build system
- 100% test pass rate (257/257 tests passing)
- Comprehensive test coverage reaching 75%
- Full MCP tools implementation with proper validation
- MCP resources implementation (streams, users, messages)
- MCP prompts (daily_summary, morning_briefing, catch_up)
- Proper TextContent objects for all prompt returns
- Enhanced error handling with specific exception types

### Changed
- Migrated from hatchling to uv_build backend
- Standardized user data handling with 'full_name' field
- Enhanced catch_up_prompt with topic and participant tracking
- Unified message/user/stream object conversion logic
- Improved validation timing for all input parameters
- Applied comprehensive code formatting with ruff
- Fixed all 254 linting issues

### Removed
- Deprecated batch_ops module (consolidated into server)
- Deprecated workflows module (consolidated into commands)
- Legacy agent adapter implementations

### Fixed
- All test failures resolved (from 48 failing to 0)
- User data field consistency issues
- Prompt validation timing issues
- Message object conversion inconsistencies
- Import resolution problems
- Type annotation errors throughout codebase

## [1.2.0] - 2025-09-05

### Added
- Command chain system for workflow automation
- Smart notification system with priority routing
- Message scheduler with Zulip native API
- Batch operations for bulk processing
- Simplified intelligent assistant tools
- Comprehensive test suite with 85%+ coverage
- Standardized error handling across all tools

### Changed
- Simplified assistant features for maintainability
- Improved error handling consistency
- Enhanced type safety throughout codebase
- Updated dependencies and build configuration

### Removed
- WebSocket support (over-engineered for initial release)
- Complex ML-based features from assistants
- Advanced conversation analysis
- Over-engineered notification features
- Complex workflow state machines

### Fixed
- Import resolution issues
- Type annotation errors
- Circular dependency problems
- Test coverage gaps

### Technical Improvements
- Added absolute imports throughout codebase
- Implemented standardized error response format
- Enhanced configuration management
- Improved logging and monitoring capabilities
- Added comprehensive documentation

## [1.1.0] - 2025-06-28

### Added
- Initial MCP server implementation
- Basic Zulip API integration
- Docker containerization
- Environment variable configuration

### Changed
- Migrated from direct API calls to MCP protocol
- Improved error handling and validation

## [1.0.0] - 2025-06-16

### Added
- Initial release
- Basic message sending and retrieval
- Stream and user management
- Simple search functionality

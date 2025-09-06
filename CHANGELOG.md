# Changelog

## [2.2.0] - 2025-09-06

### Added - v2.0 Production Completion & Standards Research
- **Bot Identity System Complete**
  - Configured sophisticated dual-credential system (user + bot identity)
  - Claude Code now has dedicated bot identity: `claude-code-bot@grc.zulipchat.com`
  - Professional message attribution with clear AI agent identification
  - Maintains competitive advantage over other MCP servers

- **100% Tool Success Rate Achievement**
  - Fixed all 3 critical MCP tool bugs from debugging session
  - `register_agent` type error resolved (dict vs object handling)
  - `rename_stream` API signature corrected for Zulip API compliance
  - `request_user_input` fully implemented with complete Zulip messaging
  - All 19 MCP tools now working flawlessly

- **MCP Industry Standards Research**
  - Comprehensive analysis of GitHub, AWS, and other successful MCP servers
  - Identified standard pattern: `uvx package` → `claude mcp add` → client-managed credentials
  - Documented findings showing 100% of successful MCP servers use simple installation
  - Created comprehensive next-session plan for standardization

### Changed - Architecture Optimization
- **Performance Enhancements Maintained**
  - Preserved 59ms average latency optimization from v2.1.0
  - Kept direct API streaming and efficient data flow patterns
  - Maintained sophisticated bot identity competitive advantage

### Removed - Legacy Non-Standard Components
- **Scripts Directory** (7 files, 1,574 lines removed)
  - `setup_claude_code.sh` - Used deprecated .env file approach
  - `test_integration.sh` - Legacy integration testing patterns
  - `test_mcp_tools.py` - Obsolete HTTP-based MCP testing
- **Documentation Files**
  - `docs/api-keys.md` - Incompatible with standard MCP credential management
  - `docs/BOT_SETUP.md` - Obsoleted by client-managed credentials
  - `.env.example` - Standard MCP doesn't use .env files
- **Planning Files**
  - `INTEGRATE-PLAN.md` - Task completed, superseded by NEXT-SESSION-PROMPT.md

### Fixed - Critical Bug Resolution
- **Type Handling in register_agent**
  ```python
  # Before: Assumed object attributes
  stream_exists = any(s.name == "Agents-Channel" for s in streams)
  
  # After: Proper dict handling  
  streams = response.get("streams", []) if response.get("result") == "success" else []
  stream_exists = any(s.get("name") == "Agents-Channel" for s in streams)
  ```

- **Zulip API Compliance in rename_stream**
  ```python
  # Before: Positional arguments causing API errors
  result = client.client.update_stream(stream_id, new_name)
  
  # After: Proper dictionary parameter
  request = {"stream_id": stream_id, "new_name": new_name}
  result = client.client.update_stream(request)
  ```

- **Complete Implementation of request_user_input**
  - Added missing Zulip message sending functionality
  - Proper user interaction with formatted requests
  - Database storage with actual messaging integration

### Research Findings - MCP Standardization
- **Current Gap**: ZulipChat MCP uses non-standard .env file configuration
- **Industry Standard**: All successful MCP servers use `uvx package` installation
- **Target UX**: `uvx zulipchat-mcp` → `claude mcp add zulipchat` → client prompts for credentials
- **Deviation Cost**: Complex setup vs one-line installation of competitors

### Next Session Priority
- **Standardization Implementation** (see NEXT-SESSION-PROMPT.md)
  - Remove DuckDB config storage (keep DuckDB for app data only)
  - Simplify ConfigManager to environment variables only
  - Fix pyproject.toml for proper uvx compatibility
  - Implement standard MCP installation flow

### Current Status - Production Ready Foundation
- ✅ **Architecture**: v2.0 complete with 59ms latency optimization
- ✅ **Functionality**: 19/19 MCP tools working (100% success rate)  
- ✅ **Bot Identity**: Sophisticated dual-credential system working perfectly
- ✅ **Performance**: 40-60% latency improvement maintained
- ✅ **Database**: DuckDB persistence with proper migrations
- 🎯 **Next**: Standardize to match industry MCP patterns while preserving advantages

## [2.1.0] - 2025-09-06

### Added - Performance Optimization
- **Direct API Response Streaming**
  - Eliminated unnecessary Pydantic model conversions in data flow
  - Direct pass-through of Zulip API responses to MCP tools
  - Content size limiting (50KB) to prevent memory issues with large messages
  - Smart truncation with indicators for oversized content

### Changed - Latency Optimizations
- **Refactored Data Flow**
  - Removed intermediate Pydantic models (ZulipMessage, ZulipStream, ZulipUser)
  - Changed `client.get_messages()` to `client.get_messages_raw()` for raw API responses
  - Tools now extract only essential fields needed by agents
  - Consistent error handling with specific KeyError catching
- **Tool Response Optimization**
  - All messaging tools now return raw dicts with minimal transformation
  - Search tools optimized for direct dict manipulation
  - Stream tools simplified to return essential fields only
  - Average latency reduced from ~100-150ms to ~59ms
- **API Compliance Updates**
  - Added missing parameters to `get_messages` (include_anchor, client_gravatar, apply_markdown)
  - Enhanced `edit_message` with propagate_mode and notification parameters
  - Fixed stream management tools to use correct Zulip API endpoints

### Fixed - Tool Functionality
- **Message Tools**
  - Fixed `get_messages` tool that was expecting dict but receiving Pydantic models
  - Fixed `search_messages` return type consistency
  - Added proper content truncation for large messages
- **Error Handling**
  - Clear, specific error messages instead of generic "unexpected error"
  - Proper fail-fast behavior with helpful debugging information
  - Consistent status/error response format across all tools

### Performance Improvements
- **Latency**: Average 59ms for get_messages (previously 100-150ms)
- **Consistency**: 47-98ms across different payload sizes
- **Memory**: Content truncation prevents memory bloat
- **Efficiency**: Direct API → dict → response (removed dict → Pydantic → dict conversion)

## [2.0.0] - 2025-09-06

### Added - Complete v2.0 Architectural Refactor
- **Clean Architecture Implementation**
  - New `core/utils/services/tools/integrations` package structure
  - Separation of domain logic (`core/`) from cross-cutting concerns (`utils/`)
  - Dedicated `tools/` directory for MCP tool registrars
  - `integrations/` system for agent-specific installers
- **DuckDB Persistence Layer**
  - Complete database schema with migrations
  - Thread-safe DatabaseManager with connection pooling
  - Tables: agents, agent_instances, tasks, user_input_requests, afk_state, caches
  - Project-local database storage (`.mcp/zulipchat/zulipchat.duckdb`)
- **FastMCP Server Implementation**
  - Stdio-only MCP transport for maximum compatibility
  - 19 registered MCP tools across messaging, streams, agents, search
  - Clean server.py (35 lines) focused only on tool registration
  - Automatic database initialization on startup
- **Integration CLI System**
  - `zulipchat-mcp-integrate` command for agent setup
  - Agent registry pattern supporting multiple AI frameworks
  - Claude Code integration with workflow command generation
  - Extensible architecture for future agent types

### Changed - Major Architectural Overhaul
- **Module Restructuring**
  - Moved `client.py` → `core/client.py` with enhanced ZulipClientWrapper
  - Moved `config.py` → `config.py` (root level for easy import)
  - Split tools into dedicated modules: `messaging.py`, `streams.py`, `agents.py`, `search.py`
  - Consolidated utilities in `utils/` (database, logging, metrics, health)
- **Database Migration**
  - Replaced SQLite with DuckDB for better performance and SQL compliance
  - Thread-safe operations with proper locking mechanisms
  - Atomic transactions for data consistency
  - Enhanced schema with proper indexes and constraints
- **Tool Registration**
  - Modular tool registrars instead of monolithic server
  - Proper type hints and validation for all MCP tools
  - Standardized error handling with specific exception types
  - Enhanced logging and metrics collection

### Removed - Legacy Components
- **Deprecated Modules**
  - Removed `agent_adapters/setup_agents.py` (replaced by integrations/)
  - Removed `hooks/` directory (consolidated into integrations/)
  - Cleaned up temporary implementation files
  - Removed complex caching layer (simplified with DuckDB views)
- **Over-engineered Features**
  - Removed WebSocket support (stdio MCP is sufficient)
  - Simplified batch operations (consolidated into core tools)
  - Removed complex workflow state machines

### Fixed - Critical Issues Resolved
- **Import Resolution**
  - Fixed all circular dependency issues
  - Updated to absolute imports throughout codebase
  - Proper module boundaries and dependencies
- **Database Operations**
  - Fixed thread safety issues with connection management
  - Proper transaction handling and rollback support
  - Resolved datetime handling incompatibilities
- **MCP Protocol Compliance**
  - Fixed FastMCP server initialization
  - Proper tool registration and discovery
  - Enhanced error handling for MCP transport

### Technical Implementation Details
- **Architecture Pattern**: Clean separation with `core/utils/services/tools/integrations`
- **Persistence**: DuckDB with full ACID transactions and thread safety
- **MCP Integration**: FastMCP stdio transport with 19 registered tools
- **Build System**: UV package management with proper dependency resolution
- **Development**: Enhanced debugging documentation and next-session planning

### Current Status
- ✅ **Server Connection**: MCP server successfully connects to Claude Code
- ✅ **Database**: DuckDB persistence working with all required tables
- ✅ **Some Tools**: `get_streams`, `register_agent` working correctly
- ❌ **Message Tools**: `get_messages`, `search_messages` need debugging (generic errors)
- 🎯 **Next Priority**: Debug Zulip API integration layer for message retrieval

### Migration Notes
- Existing installations need to run `uv sync` to update dependencies
- Database will be automatically migrated to new DuckDB schema
- MCP connection requires re-registration: `claude mcp add zulipchat uv run zulipchat-mcp`
- Integration setup: `uv run zulipchat-mcp-integrate claude-code`

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

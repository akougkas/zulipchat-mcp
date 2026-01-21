# Changelog

All notable changes to ZulipChat MCP are documented in this file.

## [0.4.2] - 2025-01-20

### Added
- **Privacy Policy**: Added `PRIVACY.md` and privacy section in README (required for MCP directory listings)
- **MCP Registry Metadata**: Added `server.json` for Official MCP Registry submission
- **Registry Verification**: Added `mcp-name` metadata for PyPI package ownership verification

### Documentation
- Prepared for submission to Official MCP Registry, Smithery.ai, Glama.ai, and other directories
- Added comprehensive privacy policy documentation

---

## [0.4.1] - 2025-01-19

### Fixed
- Updated README with correct PyPI install instructions

---

## [0.4.0] - 2025-01-19

### Added
- **Setup Wizard**: Interactive `zulipchat-mcp-setup` command for guided configuration
- **zuliprc-first Authentication**: Credentials now loaded from zuliprc files (more secure than CLI args)
- **Anthropic Sampling Handler**: Fallback handler for LLM analytics when MCP sampling unavailable
- **249 New Tests**: Comprehensive test suite from Gemini QA audit (411 total tests)
- **Emoji Registry**: Approved emoji validation for agent reactions (`src/zulipchat_mcp/core/emoji_registry.py`)

### Changed
- **Version Reset**: Moved from 2.5.x to 0.4.x versioning scheme
- **MCP Spec Compliance**: Improved sampling, emoji registry, and error messages
- **Coverage Threshold**: Adjusted to 60% (realistic for full codebase testing)
- **Smart Stream Fallback**: Agent tools now fallback gracefully when streams unavailable
- **execute_chain Context**: Proper context initialization for workflow chains

### Fixed
- Resolved 5 bugs from Gemini QA audit
- Resolved 3 bugs from MCP stress testing
- Strict typing gaps and SDK mismatches
- Removed orphaned v25 modules and broken imports
- Removed MCP sampling dependency from AI analytics tools (now optional)

### Documentation
- Standardized version references to 0.4.x across all docs
- Fixed coverage gate documentation (60% across all files)
- Updated release documentation structure

---

## [0.3.0] - 2024-12-01

### Major Architecture Consolidation
- **24+ tools → 7 categories**: Complete consolidation with foundation layer
- **Foundation Components**: IdentityManager, ParameterValidator, ErrorHandler, MigrationManager
- **New Capabilities**: Event streaming, scheduled messaging, bulk operations, admin tools
- **Multi-Identity**: User/bot/admin authentication with capability boundaries
- **100% Backward Compatibility**: Migration layer preserves all legacy functionality

### Tool Categories
1. **Core Messaging** (`messaging.py`) - 4 consolidated tools with scheduling, narrow filters, bulk operations
2. **Stream & Topic Management** (`streams.py`) - 3 enhanced tools with topic-level control
3. **Event Streaming** (`events.py`) - 3 stateless tools for real-time capabilities
4. **User & Authentication** (`users.py`) - 3 identity-aware tools with multi-credential support
5. **Advanced Search & Analytics** (`search.py`) - 2 enhanced tools with aggregation capabilities
6. **File & Media Management** (`files.py`) - 2 enhanced tools with streaming support
7. **Administration & Settings** (`admin.py`) - 2 admin tools with permission boundaries

### Technical Improvements
- Sub-100ms response times for basic operations
- Stateless event architecture with ephemeral queues
- Standardized error responses across all tools
- Progressive disclosure interface (basic/advanced modes)

---

## [0.2.0] - 2024-11-01

### Initial Public Release
- Core messaging and search functionality
- Stream management tools
- User management tools
- Basic event handling
- DuckDB persistence layer
- FastMCP framework integration

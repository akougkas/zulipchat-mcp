# Comprehensive Zulip REST API Documentation for MCP Tool Design

## Overview
Zulip provides a robust REST API that enables complete programmatic interaction with Zulip's chat platform. This document serves as a comprehensive reference for designing MCP tools.

## Authentication

### API Key Authentication
- **Method**: HTTP Basic Auth with email and API key
- **Obtain API Key**: 
  - Through web interface
  - Via `/fetch_api_key` endpoint
- **Security**: Store API keys securely, rotate periodically

### Supported Authentication Flows
- Bot Authentication
- User Authentication
- Server-to-Server Integration

## Core API Endpoints

### 1. Messages API
#### Endpoints
- `GET /messages`: Retrieve messages
- `POST /messages`: Send new messages
- `PATCH /messages/{message_id}`: Edit messages
- `DELETE /messages/{message_id}`: Delete messages

#### Advanced Features
- Scheduled messages
- Emoji reactions
- Message flags
- Markdown rendering
- File attachments

### 2. Streams/Channels API
#### Endpoints
- `GET /streams`: List streams
- `POST /streams`: Create new stream
- `PATCH /streams/{stream_id}`: Update stream
- `DELETE /streams/{stream_id}`: Delete/archive stream

#### Advanced Management
- Subscription management
- Topic operations
- Stream permissions

### 3. Users API
#### Endpoints
- `GET /users`: List users
- `POST /users`: Create users
- `PATCH /users/me`: Update user profile
- `GET /users/me/presence`: User presence

#### User Management
- User groups
- Roles and permissions
- Status updates

### 4. Events & Real-time API
#### Core Concepts
- Long-polling event system
- Event queues
- Real-time updates

#### Key Endpoints
- `POST /register`: Create event queue
- `GET /events`: Fetch events
- `DELETE /events`: Delete event queue

### 5. Organization API
- Server settings
- Custom emoji
- Linkifiers
- Profile fields
- Data exports

## Advanced Integration Patterns

### Event Streaming
- Support for multiple event types
- Configurable event queues
- Heartbeat and connection management

### Bulk Operations
- Bulk message deletion
- Batch user management
- Optimized data retrieval

### Performance Considerations
- Avatar URL optimization
- Efficient event handling
- Connection pooling strategies

## Error Handling

### Error Response Structure
```json
{
  "result": "error",
  "msg": "Error message",
  "code": "ERROR_CODE"
}
```

### Common Error Codes
- `REQUEST_VARIABLE_MISSING`
- `RATE_LIMIT_EXCEEDED`
- `UNAUTHORIZED`
- `INVALID_STREAM`

## Best Practices for MCP Tools

1. Use official Python/JavaScript bindings
2. Implement robust error handling
3. Respect rate limits
4. Use event queues for real-time updates
5. Cache organizational data
6. Securely manage API keys

## Rate Limiting
- Per-endpoint rate limits
- Organization-wide limits
- Exponential backoff recommended

## Recommended Client Libraries
- Python: `zulip` package
- JavaScript: Official Zulip JS library
- Supports most programming languages via REST calls

## Security Recommendations
- Use environment variables for credentials
- Implement token rotation
- Validate and sanitize all inputs
- Use HTTPS for all API calls

## Versioning
- Check `/api/changelog` for updates
- Pin to specific library versions
- Test integrations thoroughly

## Monitoring & Logging
- Log all API interactions
- Track error rates
- Monitor event queue performance

## Resources
- Official API Docs: https://zulip.com/api/
- REST API Reference: https://zulip.com/api/rest
- Client Libraries: https://zulip.com/api/client-libraries

## MCP Tool Design Principles
1. Stateless design
2. Efficient event handling
3. Comprehensive error management
4. Secure authentication
5. Performance optimization
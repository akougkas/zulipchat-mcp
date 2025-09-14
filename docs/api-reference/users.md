# Users API Reference

The users category provides comprehensive user management and identity switching capabilities with multi-identity support.

## Tool Overview

| Function | Purpose | Identity Support |
|----------|---------|------------------|
| [`manage_users()`](#manage_users) | User operations with identity context | User, Bot, Admin |
| [`switch_identity()`](#switch_identity) | Switch identity context for operations | All |
| [`manage_user_groups()`](#manage_user_groups) | Manage user groups and permissions | Admin |

## Functions

### `manage_users()`

User operations with identity context, allowing operations as user, bot, or admin with appropriate capability boundaries.

#### Signature
```python
async def manage_users(
    operation: Literal["list", "get", "update", "presence", "groups", "avatar", "profile_fields"],
    
    # User identification (operation-dependent)
    user_id: Optional[int] = None,
    email: Optional[str] = None,
    
    # Identity context
    as_bot: bool = False,  # Use bot identity
    as_admin: bool = False,  # Requires admin credentials
    
    # User updates
    full_name: Optional[str] = None,
    status_text: Optional[str] = None,
    status_emoji: Optional[str] = None,
    
    # Presence
    status: Optional[Literal["active", "idle", "offline"]] = None,
    client: str = "MCP",
    
    # Advanced options
    include_custom_profile_fields: bool = False,
    client_gravatar: bool = True,
    
    # Avatar management
    avatar_file: Optional[bytes] = None,
    
    # Profile fields
    profile_field_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]
```

#### Parameters

##### Required Parameters
- **`operation`** (Literal): Type of operation to perform
  - `"list"`: Get all users in organization
  - `"get"`: Get specific user information
  - `"update"`: Update user profile
  - `"presence"`: Update/get presence status
  - `"groups"`: Get user group memberships
  - `"avatar"`: Update user avatar
  - `"profile_fields"`: Manage custom profile fields

##### User Identification (operation-dependent)
- **`user_id`** (int): Target user ID (for get/update operations)
- **`email`** (str): Target user email (alternative to user_id)

##### Identity Context
- **`as_bot`** (bool): Execute operation using bot identity
- **`as_admin`** (bool): Execute operation using admin identity (requires admin access)

##### Update Parameters
- **`full_name`** (str): New full name (for update operation)
- **`status_text`** (str): Status text to set
- **`status_emoji`** (str): Status emoji to set

##### Presence Parameters
- **`status`** (Literal): Presence status ("active", "idle", "offline")
- **`client`** (str): Client name for presence updates (default: "MCP")

##### Advanced Options
- **`include_custom_profile_fields`** (bool): Include custom profile data
- **`client_gravatar`** (bool): Include gravatar URLs (default: True)
- **`avatar_file`** (bytes): Avatar image data for avatar operation
- **`profile_field_data`** (Dict): Custom profile field data for profile_fields operation

#### Examples

**List all users (as current identity)**:
```python
result = await manage_users("list")
```

**Get user details with admin privileges**:
```python
result = await manage_users(
    operation="get",
    email="user@example.com",
    as_admin=True
)
```

**Update user status as bot**:
```python
result = await manage_users(
    operation="update",
    user_id=123,
    status_text="Working on project",
    as_bot=True
)
```

**Set presence status**:
```python
result = await manage_users(
    operation="presence",
    status="active",
    client="Mobile App"
)
```

**Update avatar**:
```python
result = await manage_users(
    operation="avatar",
    avatar_file=avatar_bytes
)
```

**Update custom profile fields**:
```python
result = await manage_users(
    operation="profile_fields",
    profile_field_data={"department": "Engineering"}
)
```

#### Response Formats by Operation

**List Operation**:
```python
{
    "status": "success",
    "operation": "list",
    "users": [...],  # Array of user objects from Zulip API
    "count": 25,
    "identity_used": "user"
}
```

**Get Operation**:
```python
{
    "status": "success",
    "operation": "get",
    "user": {
        # User object from Zulip API
    },
    "identity_used": "user"
}
```

**Update Operation**:
```python
{
    "status": "success",
    "operation": "update",
    "user_id": 123,
    "updated_fields": ["full_name", "status_text", "status_emoji"],
    "identity_used": "admin"
}
```

**Presence Operation**:
```python
{
    "status": "success",
    "operation": "presence",
    "new_status": "active",
    "client": "MCP",
    "identity_used": "user"
}
```

**Groups Operation**:
```python
{
    "status": "success",
    "operation": "groups",
    "user_groups": [...],  # Groups where user is a member
    "all_groups": [...],   # All organization groups
    "identity_used": "user"
}
```

**Avatar Operation**:
```python
{
    "status": "success",
    "operation": "avatar",
    "message": "Avatar updated successfully",
    "identity_used": "user"
}
```

**Profile Fields Operation**:
```python
{
    "status": "success",
    "operation": "profile_fields",
    "updated_fields": ["department"],  # If updating
    # OR
    "available_fields": [...],  # If getting available fields
    "identity_used": "user"
}
```

#### Operation-Specific Usage

**User Profile Management**:
```python
# Get current user profile
profile = await manage_users("get", user_id="me")

# Update own status
await manage_users(
    operation="update",
    user_id="me", 
    status_text="In a meeting",
    status_emoji="calendar"
)

# Update presence status
await manage_users(
    operation="presence",
    status="active"
)
```

**User Information Lookup**:
```python
# Find user by email
user = await manage_users(
    operation="get",
    email="alice@example.com",
    include_custom_profile_fields=True
)

# Get user's group memberships
groups = await manage_users(
    operation="groups",
    user_id=123
)
```

**Administrative Operations** (requires admin identity):
```python
# Update another user's profile (admin only)
await manage_users(
    operation="update",
    user_id=456,
    full_name="Updated Name",
    as_admin=True
)

# Get comprehensive user list with all fields
all_users = await manage_users(
    operation="list",
    include_custom_profile_fields=True,
    client_gravatar=True,
    as_admin=True
)
```

### `switch_identity()`

Switch identity context for operations with proper validation and capability management.

#### Signature
```python
async def switch_identity(
    identity: Literal["user", "bot", "admin"],
    persist: bool = False,  # Temporary switch by default
    validate: bool = True   # Check credentials
) -> Dict[str, Any]
```

#### Parameters

##### Required Parameters
- **`identity`** (Literal): Target identity type to switch to
  - `"user"`: Standard user identity
  - `"bot"`: Bot identity (if configured)
  - `"admin"`: Admin identity (if available)

##### Optional Parameters
- **`persist`** (bool): If True, make this the default identity for future operations (default: False)
- **`validate`** (bool): If True, validate the target identity credentials (default: True)

#### Examples

**Temporarily switch to bot identity**:
```python
result = await switch_identity("bot", persist=False)
```

**Permanently switch to admin identity with validation**:
```python
result = await switch_identity(
    identity="admin",
    persist=True,
    validate=True
)
```

**Quick switch without credential validation**:
```python
result = await switch_identity("user", validate=False)
```

#### Response Format

```python
{
    "status": "success",
    "switched_to": "bot",  # The identity that was switched to
    "previous_identity": "user",  # The identity before switching
    "persistent": False,  # Whether the switch is permanent
    "capabilities": [...],  # List of capabilities for new identity
    "email": "bot@example.com",  # Email associated with new identity
    "display_name": "Bot User",  # Display name for new identity
    "name": "bot",  # Identity name
    "available_identities": ["user", "bot", "admin"]  # All available identities
}
```

#### Identity Management Patterns

**Context Switching Pattern**:
```python
# Temporary identity switch
async def admin_operation():
    # Store current identity
    current = await switch_identity("user", operation="status")
    
    try:
        # Switch to admin for operation
        await switch_identity("admin", persistent=False)
        
        # Perform admin operation
        result = await manage_users("update", user_id=456, full_name="New Name")
        
        return result
        
    finally:
        # Restore previous identity
        await switch_identity(current["current_identity"])
```

**Capability Checking Pattern**:
```python
# Check capabilities before operation
async def safe_user_operation(operation: str, **kwargs):
    caps = await switch_identity("user", operation="capabilities")
    
    required_caps = get_required_capabilities(operation)
    if not all(cap in caps["capabilities"] for cap in required_caps):
        # Try admin identity
        if "admin" in await switch_identity("admin", operation="status")["available_identities"]:
            await switch_identity("admin")
        else:
            raise PermissionError(f"Insufficient capabilities for {operation}")
    
    # Proceed with operation
    return await manage_users(operation, **kwargs)
```

### `manage_user_groups()`

Manage user groups and permissions including creation, modification, deletion, and member management.

#### Signature
```python
async def manage_user_groups(
    action: Literal["create", "update", "delete", "add_members", "remove_members"],
    
    # Group identification (action-dependent)
    group_name: Optional[str] = None,
    group_id: Optional[int] = None,
    
    # Group parameters
    description: Optional[str] = None,
    members: Optional[List[int]] = None
) -> Dict[str, Any]
```

#### Parameters

##### Required Parameters
- **`action`** (Literal): Action to perform on user groups
  - `"create"`: Create new user group
  - `"update"`: Update group properties  
  - `"delete"`: Delete user group
  - `"add_members"`: Add users to group
  - `"remove_members"`: Remove users from group

##### Group Identification
- **`group_name`** (str): Name of the user group (required for create, optional for others)
- **`group_id`** (int): ID of the user group (alternative to group_name)

##### Group Parameters
- **`description`** (str): Description for the group (used in create/update)
- **`members`** (List[int]): List of user IDs for member operations

#### Examples

**Create new user group**:
```python
result = await manage_user_groups(
    action="create",
    group_name="developers",
    description="Development team",
    members=[1, 2, 3]
)
```

**Add members to existing group**:
```python
result = await manage_user_groups(
    action="add_members",
    group_id=5,
    members=[4, 5]
)
```

**Update group description**:
```python
result = await manage_user_groups(
    action="update",
    group_name="developers",
    description="Software development team"
)
```

**Remove members from group**:
```python
result = await manage_user_groups(
    action="remove_members",
    group_id=5,
    members=[3]
)
```

**Delete group**:
```python
result = await manage_user_groups(
    action="delete",
    group_id=5
)
```

#### Response Formats

**Create Action**:
```python
{
    "status": "success",
    "action": "create",
    "group_name": "developers",
    "group_id": 456,  # Newly created group ID
    "members_added": 3,
    "description": "Development team"
}
```

**Update Action**:
```python
{
    "status": "success",
    "action": "update",
    "group_id": 456,
    "updated_fields": ["description"]
}
```

**Delete Action**:
```python
{
    "status": "success",
    "action": "delete",
    "group_id": 456,
    "group_name": "developers"
}
```

**Add Members Action**:
```python
{
    "status": "success",
    "action": "add_members",
    "group_id": 456,
    "members_added": [4, 5],
    "count": 2
}
```

**Remove Members Action**:
```python
{
    "status": "success",
    "action": "remove_members",
    "group_id": 456,
    "members_removed": [3],
    "count": 1
}
```

## Identity & Permissions

### Required Capabilities by Function

| Function | User | Bot | Admin | Notes |
|----------|------|-----|-------|-------|
| `manage_users()` | ✅ Self/Read | ❌ | ✅ All | Users can manage own profile |
| `switch_identity()` | ✅ | ✅ | ✅ | All identities can switch context |
| `manage_user_groups()` | ❌ | ❌ | ✅ | Admin-only group management |

### Operation-Specific Permissions

#### User Management Operations
- **List users**: All identities
- **Get user info**: All identities (public info only)
- **Update profile**: Own profile only (users), any profile (admin)
- **Update presence**: Own presence only

#### Identity Switching
- **Switch to user**: Always available
- **Switch to bot**: Requires bot credentials configured
- **Switch to admin**: Requires admin privileges detected

#### User Group Management
- **All operations**: Admin identity required
- **View group membership**: Available via manage_users() for all identities

## Error Handling

### Common Error Scenarios

#### User Not Found
```python
{
    "status": "error",
    "error": "User not found: user@example.com",
    "error_type": "NotFoundError",
    "retryable": False
}
```

#### Permission Denied
```python
{
    "status": "error",
    "error": "Cannot update another user's profile",
    "error_type": "PermissionError", 
    "retryable": False,
    "required_identity": "admin"
}
```

#### Identity Switch Failed
```python
{
    "status": "error",
    "error": "Bot credentials not configured",
    "error_type": "ConfigurationError",
    "retryable": False,
    "missing_config": ["ZULIP_BOT_EMAIL", "ZULIP_BOT_API_KEY"]
}
```

#### Invalid Group Operation
```python
{
    "status": "error",
    "error": "Cannot delete system group 'everyone'",
    "error_type": "ValidationError",
    "retryable": False
}
```

## Best Practices

### Identity Management
1. **Check capabilities first** - Verify identity has required permissions
2. **Use temporary switches** - Switch back to original identity when done
3. **Validate credentials** - Always validate when switching identities
4. **Handle missing identities** - Gracefully handle unavailable bot/admin identities

### User Information
1. **Cache user data** - User info changes infrequently
2. **Use user IDs** - More stable than email addresses
3. **Include custom fields selectively** - Only when needed for performance
4. **Respect privacy** - Handle user information according to privacy policies

### Group Management
1. **Use descriptive names** - Make group purposes clear
2. **Document group membership** - Keep group descriptions updated
3. **Handle system groups carefully** - Cannot modify system groups
4. **Validate membership changes** - Check user existence before operations

## Integration Examples

### User Onboarding System
```python
async def onboard_new_user(user_id: int, team: str):
    # Switch to admin identity
    await switch_identity("admin", persist=True)
    
    # Get user details
    user = await manage_users("get", user_id=user_id)
    
    # Add user to team group
    team_group = f"{team}-team"
    await manage_user_groups(
        action="add_members",
        group_name=team_group,
        members=[user_id]
    )
    
    # Set welcome status
    await manage_users(
        operation="update",
        user_id=user_id,
        status_text=f"Welcome to {team}!",
        status_emoji="wave"
    )
```

### User Activity Monitor
```python
async def monitor_user_activity():
    # Get all active users
    users = await manage_users("list")
    
    activity_report = []
    
    for user in users["users"]:
        if user["is_active"]:
            # Get user presence
            presence = await manage_users(
                operation="presence", 
                user_id=user["user_id"]
            )
            
            # Get user groups
            groups = await manage_users(
                operation="groups",
                user_id=user["user_id"] 
            )
            
            activity_report.append({
                "user": user,
                "presence": presence,
                "groups": groups["user_groups"]
            })
    
    return activity_report
```

### Dynamic Permission System
```python
async def execute_with_best_identity(operation: str, **kwargs):
    """Execute operation with the most appropriate identity."""
    
    # Try as current user first
    try:
        return await manage_users(operation, **kwargs)
    except Exception as e:
        if "permission" not in str(e).lower():
            raise
    
    # Try admin identity if available
    try:
        await switch_identity("admin", validate=True)
        return await manage_users(operation, as_admin=True, **kwargs)
    except:
        pass
    
    # Try bot identity if available
    try:
        await switch_identity("bot", validate=True)
        return await manage_users(operation, as_bot=True, **kwargs)
    except:
        pass
    
    raise PermissionError(f"No identity has required permissions for {operation}")
```

---

**Related**: [Admin API](admin.md) | [Messaging API](messaging.md) | [Streams API](streams.md)
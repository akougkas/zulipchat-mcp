# Admin API Reference

The admin category provides organizational administration and customization capabilities. These functions require admin identity and work with the Zulip admin API.

## Tool Overview

| Function | Purpose | Identity Support |
|----------|---------|------------------|
| [`admin_operations()`](#admin_operations) | Realm settings, users, streams, data management | Admin only |
| [`customize_organization()`](#customize_organization) | Emoji, linkifiers, playgrounds, filters | Admin only |

## Functions

### `admin_operations()`

Server and realm administration operations including settings, user management, and data export/import.

#### Signature
```python
async def admin_operations(
    identity_manager: IdentityManager,  # Required: Identity manager instance
    operation: Literal["settings", "users", "streams", "export", "import", "branding", "profile_fields"],
    realm_id: Optional[int] = None,
    
    # Settings management
    settings: Optional[Dict[str, Any]] = None,
    
    # User administration
    deactivate_users: Optional[List[int]] = None,
    role_changes: Optional[Dict[int, str]] = None,
    
    # Export/Import
    export_type: Optional[Literal["public", "full", "subset"]] = None,
    export_params: Optional[Dict] = None,
    import_data: Optional[Dict] = None,
    
    # Organization branding
    logo_file: Optional[bytes] = None,
    icon_file: Optional[bytes] = None,
    
    # Custom profile fields management
    profile_field_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]
```

#### Parameters

##### Required Parameters
- **`identity_manager`** (IdentityManager): Identity manager instance for authentication
- **`operation`** (Literal): Administrative operation type
  - `"settings"`: Get or update realm settings
  - `"users"`: User administration (deactivation, role changes)
  - `"streams"`: Stream information and statistics
  - `"export"`: Start data export
  - `"import"`: Import data (placeholder)
  - `"branding"`: Upload logo/icon
  - `"profile_fields"`: Manage custom profile fields

##### Optional Parameters
- **`realm_id`** (int): Target realm ID (uses current realm if None)

##### Operation-specific Parameters

**For "settings" operation:**
- **`settings`** (Dict): Settings to update (if None, retrieves current settings)

**For "users" operation:**
- **`deactivate_users`** (List[int]): List of user IDs to deactivate
- **`role_changes`** (Dict[int, str]): Map of user_id -> new_role ("owner", "admin", "moderator", "member", "guest")

**For "export" operation:**
- **`export_type`** (Literal): Type of export ("public", "full", "subset")
- **`export_params`** (Dict): Additional export parameters

**For "import" operation:**
- **`import_data`** (Dict): Data to import (placeholder functionality)

**For "branding" operation:**
- **`logo_file`** (bytes): Organization logo image data
- **`icon_file`** (bytes): Organization icon image data

**For "profile_fields" operation:**
- **`profile_field_config`** (Dict): Configuration for custom profile field

#### Usage Examples

**Get realm settings:**
```python
# Retrieve current realm settings
result = await admin_operations(
    identity_manager=identity_manager,
    operation="settings"
)
```

**Update realm settings:**
```python
# Update specific realm settings
result = await admin_operations(
    identity_manager=identity_manager,
    operation="settings",
    settings={
        "name": "My Organization",
        "description": "Organization description",
        "allow_message_editing": True
    }
)
```

**User administration:**
```python
# Deactivate users
result = await admin_operations(
    identity_manager=identity_manager,
    operation="users",
    deactivate_users=[123, 456, 789]
)

# Change user roles
result = await admin_operations(
    identity_manager=identity_manager,
    operation="users",
    role_changes={
        123: "admin",
        456: "moderator",
        789: "member"
    }
)
```

**Organization branding:**
```python
# Upload organization logo
with open("logo.png", "rb") as f:
    result = await admin_operations(
        identity_manager=identity_manager,
        operation="branding",
        logo_file=f.read()
    )
```

**Custom profile fields:**
```python
# Create custom profile field
result = await admin_operations(
    identity_manager=identity_manager,
    operation="profile_fields",
    profile_field_config={
        "name": "Department",
        "type": "text",
        "hint": "Your department or team"
    }
)
```

#### Response Formats by Operation

**Settings Operation (Get)**:
```python
{
    "status": "success",
    "operation": "settings",
    "timestamp": "2024-01-15T10:30:00Z",
    "current_settings": {
        "name": "My Organization",
        "description": "Organization description",
        "allow_message_editing": True,
        // Other realm settings from Zulip API
    },
    "results": "Retrieved current realm settings"
}
```

**Settings Operation (Update)**:
```python
{
    "status": "success",
    "operation": "settings",
    "timestamp": "2024-01-15T10:30:00Z",
    "updated_settings": {
        "name": "My Organization",
        "description": "Updated description",
        "allow_message_editing": True
    },
    "results": "Realm settings updated successfully"
}
```

**Users Operation**:
```python
{
    "status": "success",
    "operation": "users",
    "timestamp": "2024-01-15T10:30:00Z",
    "user_changes": [
        "Deactivated user 123",
        "Deactivated user 456",
        "Changed user 789 role to admin",
        "Failed to change role for user 790: User not found"
    ],
    "results": "Processed user administration: 4 changes"
}
```

**Streams Operation**:
```python
{
    "status": "success",
    "operation": "streams",
    "timestamp": "2024-01-15T10:30:00Z",
    "stream_stats": {
        "total_streams": 25,
        "public_streams": 20,
        "private_streams": 5,
        "web_public_streams": 2
    },
    "streams": [
        // Array of stream objects from Zulip API
    ],
    "results": "Retrieved 25 streams with statistics"
}
```

**Export Operation**:
```python
{
    "status": "success",
    "operation": "export",
    "timestamp": "2024-01-15T10:30:00Z",
    "export_id": "abc123",
    "export_type": "public",
    "export_params": {},
    "results": "Started public export with ID abc123",
    "export_status": {
        // Export status from Zulip API if available
    }
}
```

**Branding Operation**:
```python
{
    "status": "success",
    "operation": "branding",
    "timestamp": "2024-01-15T10:30:00Z",
    "branding_updates": [
        "logo updated successfully",
        "icon updated successfully"
    ],
    "results": "Processed branding updates: 2 operations"
}
```

**Profile Fields Operation**:
```python
{
    "status": "success",
    "operation": "profile_fields",
    "timestamp": "2024-01-15T10:30:00Z",
    "profile_field_id": 123,
    "profile_field_config": {
        "name": "Department",
        "type": "text",
        "hint": "Your department or team"
    },
    "results": "Custom profile field created successfully"
}
```

### `customize_organization()`

Organization customization for emoji, linkifiers, code playgrounds, and filters.

#### Signature
```python
async def customize_organization(
    identity_manager: IdentityManager,  # Required: Identity manager instance
    operation: Literal["emoji", "linkifiers", "playgrounds", "filters"],
    
    # Custom emoji
    emoji_name: Optional[str] = None,
    emoji_file: Optional[bytes] = None,
    
    # Linkifiers
    pattern: Optional[str] = None,
    url_format: Optional[str] = None,
    
    # Code playgrounds
    playground_name: Optional[str] = None,
    url_prefix: Optional[str] = None,
    language: Optional[str] = None,
    
    # Filter operations
    filter_id: Optional[int] = None,
    filter_action: Optional[Literal["add", "remove", "update"]] = None,
    filter_pattern: Optional[str] = None,
) -> Dict[str, Any]
```

#### Parameters

##### Required Parameters
- **`identity_manager`** (IdentityManager): Identity manager instance for authentication
- **`operation`** (Literal): Customization operation type
  - `"emoji"`: Manage custom emoji
  - `"linkifiers"`: Manage URL linkifiers
  - `"playgrounds"`: Manage code playgrounds
  - `"filters"`: Manage message filters

##### Operation-specific Parameters

**For "emoji" operation:**
- **`emoji_name`** (str): Name for custom emoji
- **`emoji_file`** (bytes): Emoji image file data (base64 encoded internally)

**For "linkifiers" operation:**
- **`pattern`** (str): Regex pattern to match
- **`url_format`** (str): URL format string with placeholders

**For "playgrounds" operation:**
- **`playground_name`** (str): Name for the playground
- **`url_prefix`** (str): URL prefix for code execution
- **`language`** (str): Programming language (defaults to "text")

**For "filters" operation:**
- **`filter_id`** (int): Filter ID for operations
- **`filter_action`** (Literal): Action to perform ("add", "remove", "update")
- **`filter_pattern`** (str): Filter pattern

#### Usage Examples

**Custom Emoji Management:**
```python
# Upload custom emoji
with open("custom_emoji.png", "rb") as f:
    result = await customize_organization(
        identity_manager=identity_manager,
        operation="emoji",
        emoji_name="my_emoji",
        emoji_file=f.read()
    )

# List all custom emoji
result = await customize_organization(
    identity_manager=identity_manager,
    operation="emoji"
)
```

**Linkifier Management:**
```python
# Add a linkifier for issue numbers
result = await customize_organization(
    identity_manager=identity_manager,
    operation="linkifiers",
    pattern="#([0-9]+)",
    url_format="https://github.com/myorg/myrepo/issues/%s"
)

# List all linkifiers
result = await customize_organization(
    identity_manager=identity_manager,
    operation="linkifiers"
)
```

**Code Playground Management:**
```python
# Add a Python playground
result = await customize_organization(
    identity_manager=identity_manager,
    operation="playgrounds",
    playground_name="Python REPL",
    url_prefix="https://repl.it/languages/python3",
    language="python"
)

# List all code playgrounds
result = await customize_organization(
    identity_manager=identity_manager,
    operation="playgrounds"
)
```

#### Response Formats

**Emoji Operation (Upload):**
```python
{
    "status": "success",
    "operation": "emoji",
    "timestamp": "2024-01-15T10:30:00Z",
    "emoji_info": {
        "name": "my_emoji",
        "size": 12345,
        "upload_status": "success"
    },
    "results": "Successfully uploaded custom emoji 'my_emoji'"
}
```

**Emoji Operation (List):**
```python
{
    "status": "success",
    "operation": "emoji",
    "timestamp": "2024-01-15T10:30:00Z",
    "emoji_info": {
        "total_custom_emoji": 15,
        "emoji_list": [
            {
                "name": "custom1",
                "source_url": "https://example.com/emoji/custom1.png",
                "deactivated": false
            },
            // More emoji...
        ]
    },
    "results": "Retrieved 15 custom emoji"
}
```

**Linkifier Operation:**
```python
{
    "status": "success",
    "operation": "linkifiers",
    "timestamp": "2024-01-15T10:30:00Z",
    "linkifier_info": {
        "pattern": "#([0-9]+)",
        "url_format": "https://github.com/myorg/myrepo/issues/%s",
        "id": 456
    },
    "results": "Successfully added linkifier with pattern '#([0-9]+)'"
}
```

**Playground Operation:**
```python
{
    "status": "success",
    "operation": "playgrounds",
    "timestamp": "2024-01-15T10:30:00Z",
    "playground_info": {
        "name": "Python REPL",
        "url_prefix": "https://repl.it/languages/python3",
        "language": "python",
        "id": 789
    },
    "results": "Successfully added code playground 'Python REPL'"
}
```

**Filter Operation:**
```python
{
    "status": "success",
    "operation": "filters",
    "timestamp": "2024-01-15T10:30:00Z",
    "filter_info": {
        "action": "add",
        "pattern": "spam-pattern",
        "status": "queued"
    },
    "results": "Queued message filter pattern: spam-pattern"
}
```

## Identity & Permissions

### Admin-Only Functions
Both functions in the admin category require **admin identity**:
- Admin privileges checked via `identity_manager.check_capability()`
- Functions will fail if current identity lacks admin access
- Uses `IdentityType.ADMIN` for operations

## Error Handling

### Common Error Scenarios

#### Insufficient Privileges
```python
{
    "status": "error",
    "error": "Admin operations require admin privileges",
    "required_capability": "admin.admin_operations"
}
```

#### Failed Zulip API Call
```python
{
    "status": "error",
    "error": "Failed to update settings: Invalid parameter value"
}
```

#### Operation Not Supported
```python
{
    "status": "error",
    "error": "Unknown operation: invalid_op"
}
```

## Integration Examples

### Complete User Management
```python
async def manage_organization_users(identity_manager):
    """Comprehensive user management workflow."""
    
    # Get stream statistics first
    streams_info = await admin_operations(
        identity_manager=identity_manager,
        operation="streams"
    )
    
    # Deactivate specific users
    result = await admin_operations(
        identity_manager=identity_manager,
        operation="users",
        deactivate_users=[100, 101, 102]
    )
    
    # Update user roles
    role_result = await admin_operations(
        identity_manager=identity_manager,
        operation="users",
        role_changes={
            200: "admin",
            201: "moderator"
        }
    )
    
    return {
        "streams_count": streams_info["stream_stats"]["total_streams"],
        "users_deactivated": result["user_changes"],
        "roles_updated": role_result["user_changes"]
    }
```

### Organization Branding Setup
```python
async def setup_organization_branding(identity_manager):
    """Configure organization branding and customization."""
    
    # Upload logo and icon
    with open("logo.png", "rb") as logo, open("icon.png", "rb") as icon:
        branding_result = await admin_operations(
            identity_manager=identity_manager,
            operation="branding",
            logo_file=logo.read(),
            icon_file=icon.read()
        )
    
    # Add custom emoji
    with open("team_emoji.png", "rb") as emoji:
        emoji_result = await customize_organization(
            identity_manager=identity_manager,
            operation="emoji",
            emoji_name="teamwork",
            emoji_file=emoji.read()
        )
    
    # Set up code playgrounds
    playground_result = await customize_organization(
        identity_manager=identity_manager,
        operation="playgrounds",
        playground_name="Python",
        url_prefix="https://repl.it/languages/python3",
        language="python"
    )
    
    return {
        "branding": branding_result["branding_updates"],
        "emoji": emoji_result["emoji_info"],
        "playground": playground_result["playground_info"]
    }
```

---

**Related**: [Users API](users.md) | [Streams API](streams.md) | [Configuration Guide](../user-guide/configuration.md)
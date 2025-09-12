# Files API Reference

The files category provides file upload and management capabilities with automatic stream sharing and basic validation support.

## Tool Overview

| Function | Purpose | Identity Support |
|----------|---------|------------------|
| [`upload_file()`](#upload_file) | File upload with auto-sharing | User, Bot |
| [`manage_files()`](#manage_files) | File operations (limited by Zulip API) | User, Bot |

## Functions

### `upload_file()`

Upload files to Zulip with optional automatic sharing to streams.

#### Signature
```python
async def upload_file(
    file_path: str | None = None,      # Path to local file
    file_content: bytes | None = None, # File content as bytes (alternative to file_path)
    filename: str = "",                # Name for the uploaded file
    
    # Auto-sharing options
    stream: str | None = None,         # Stream name to auto-share to
    topic: str | None = None,          # Topic for stream sharing
    message: str | None = None,        # Optional message to accompany the file
    
    # Advanced options
    chunk_size: int = 1024*1024,       # Chunk size for streaming uploads (default: 1MB)
    mime_type: str | None = None,      # MIME type override (auto-detected if not provided)
) -> FileResponse
```

#### Parameters

##### Input Options (provide one)
- **`file_path`** (str): Path to local file to upload
- **`file_content`** (bytes): Raw file content as bytes (alternative to file_path)
- **`filename`** (str): Name for the uploaded file (required when using file_content, auto-detected from file_path)

##### Auto-sharing Parameters
- **`stream`** (str): Stream name to automatically share the file to
- **`topic`** (str): Topic for stream sharing (defaults to "File Uploads")
- **`message`** (str): Optional message to accompany the shared file

##### Advanced Parameters
- **`chunk_size`** (int): Size of chunks for upload simulation (default: 1048576 bytes = 1MB)
- **`mime_type`** (str): Override MIME type detection (auto-detected from filename/content if not provided)

#### Usage Examples

**Basic file upload from path:**
```python
# Upload a local file
result = await upload_file(
    file_path="/path/to/document.pdf",
    filename="report.pdf"
)
```

**Upload from memory:**
```python
# Upload file content from bytes
with open("document.pdf", "rb") as file:
    result = await upload_file(
        file_content=file.read(),
        filename="monthly-report.pdf"
    )
```

**Upload with auto-sharing to stream:**
```python
# Upload and automatically share to a stream
result = await upload_file(
    file_path="/path/to/screenshot.png",
    filename="ui-mockup.png",
    stream="design",
    topic="UI Mockups",
    message="Latest design iteration for the dashboard"
)
```

#### Response Format
```python
{
    "status": "success",
    "filename": "monthly-report.pdf",
    "file_url": "https://your-domain.zulipchat.com/user_uploads/abc123/monthly-report.pdf",
    "file_size": 2457600,  # Size in bytes
    "mime_type": "application/pdf",
    "file_hash": "sha256:abc123def456...",  # SHA256 hash of file content
    "upload_time": "2024-01-15T10:30:00Z",
    "warnings": [],  # Any validation warnings
    
    # Only present if stream parameter was provided
    "shared_to_stream": {
        "stream": "general",
        "topic": "File Uploads",
        "message_id": 123456,
        "status": "success"
    }
}
```

#### File Validation

The upload function performs basic validation:

**Validation Checks**:
- **File size limit**: Maximum 25MB (hardcoded in MAX_FILE_SIZE)
- **Extension checking**: Warns if extension not in allowed list
- **Filename safety**: Checks for dangerous characters (../, /, \, etc.)
- **Empty file detection**: Prevents upload of 0-byte files

**Allowed Extensions** (warnings generated for others):
```python
ALLOWED_EXTENSIONS = {
    '.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp',
    '.mp4', '.avi', '.mov', '.webm',
    '.zip', '.tar', '.gz', '.rar',
    '.json', '.xml', '.csv', '.yaml', '.yml',
    '.py', '.js', '.html', '.css', '.md'
}
```

**MIME Type Detection**:
- Basic detection from filename extension
- Magic number detection for common formats (PNG, JPEG, GIF, PDF, ZIP)
- Defaults to 'application/octet-stream' if unknown

### `manage_files()`

Manage uploaded files and attachments (limited functionality due to Zulip API constraints).

#### Signature
```python
async def manage_files(
    operation: Literal["list", "get", "delete", "share", "download", "generate_thumbnail", "get_permissions"],
    file_id: str | None = None,
    filters: FileFilters | None = None,
    # Download options
    download_path: str | None = None,
    # Sharing options
    share_in_stream: str | None = None,
    share_in_topic: str | None = None,
) -> FileListResponse
```

#### Parameters

##### Required Parameters
- **`operation`** (Literal): File operation type
  - `"list"`: List files (limited - returns partial_success)
  - `"get"`: Get file information (limited - returns partial_success)
  - `"delete"`: Delete file (not supported - returns partial_success)
  - `"share"`: Share file to stream
  - `"download"`: Download file (limited - requires full URL)
  - `"generate_thumbnail"`: Generate thumbnail (not supported)
  - `"get_permissions"`: Get file permissions info

##### Operation-specific Parameters
- **`file_id`** (str): File identifier (required for get, delete, share, download operations)
- **`filters`** (FileFilters): Filtering options for list operation (not fully implemented)
- **`download_path`** (str): Local path for download operation
- **`share_in_stream`** (str): Stream name for share operation
- **`share_in_topic`** (str): Topic for share operation

#### Usage Examples

**List files (limited support):**
```python
# Attempt to list files (returns partial_success with limitations note)
result = await manage_files("list")
# Note: Zulip doesn't have a direct file listing API
```

**Share file to stream:**
```python
# Share a file to a stream
result = await manage_files(
    operation="share",
    file_id="12345",
    share_in_stream="general",
    share_in_topic="Shared Resources"
)
```

**Get file permissions:**
```python
# Get file access permissions information
result = await manage_files(
    operation="get_permissions",
    file_id="12345"
)
```

#### Response Formats

**List Operation (Limited Support)**:
```python
{
    "status": "partial_success",
    "operation": "list",
    "message": "File listing through Zulip API is limited. Consider implementing custom file tracking.",
    "files": [],
    "note": "This operation requires custom implementation or message parsing for complete functionality"
}
```

**Get Operation (Limited Support)**:
```python
{
    "status": "partial_success",
    "operation": "get",
    "file_id": "12345",
    "message": "Direct file metadata retrieval through Zulip API is limited",
    "note": "File information is typically embedded in message context"
}
```

**Share Operation**:
```python
{
    "status": "success",
    "operation": "share",
    "file_id": "12345",
    "shared_to": {
        "stream": "general",
        "topic": "Shared Files",
        "message_id": 789456
    }
}
```

**Delete Operation (Not Supported)**:
```python
{
    "status": "partial_success",
    "operation": "delete",
    "file_id": "12345",
    "message": "Direct file deletion through Zulip API is not available",
    "note": "Files are typically removed by deleting the containing message"
}
```

**Get Permissions Operation**:
```python
{
    "status": "partial_success",
    "operation": "get_permissions",
    "file_id": "12345",
    "message": "File permissions follow Zulip stream/message access rules",
    "note": "Access is determined by stream subscription and message visibility",
    "permissions_info": {
        "access_model": "stream_based",
        "visibility": "follows_message_visibility",
        "sharing": "available_to_stream_members"
    }
}
```

## Limitations

**Important**: Many file management operations return `partial_success` because the Zulip API has limited file management capabilities:

- **No direct file listing API** - Cannot enumerate all uploaded files
- **No file deletion API** - Files are managed through messages
- **No metadata extraction** - Only basic MIME type detection
- **No thumbnail generation** - Not supported by Zulip API
- **Limited file information** - File details are embedded in message context

## Error Handling

### Common Error Scenarios

#### File Too Large
```python
{
    "status": "error",
    "error": "File size 30MB exceeds limit of 25MB",
    "validation_errors": ["File size 31457280 bytes exceeds maximum limit of 26214400 bytes"]
}
```

#### Missing File Input
```python
{
    "status": "error",
    "error": "Either file_path or file_content must be provided"
}
```

#### File Not Found
```python
{
    "status": "error",
    "error": "File not found: /path/to/file.pdf"
}
```

## Integration Examples

### Upload and Share Multiple Files
```python
async def upload_and_share_files(file_paths: List[str], stream: str, topic: str):
    """Upload multiple files and share them to a stream."""
    results = []
    
    for file_path in file_paths:
        try:
            result = await upload_file(
                file_path=file_path,
                stream=stream,
                topic=topic,
                message=f"Sharing {os.path.basename(file_path)}"
            )
            results.append({
                "file": os.path.basename(file_path),
                "status": "success",
                "url": result["file_url"]
            })
        except Exception as e:
            results.append({
                "file": os.path.basename(file_path),
                "status": "error",
                "error": str(e)
            })
    
    return results
```

### File Upload with Validation
```python
async def safe_upload(file_path: str, max_size_mb: int = 10):
    """Upload file with custom size validation."""
    
    # Check file size before upload
    file_size = os.path.getsize(file_path)
    max_size = max_size_mb * 1024 * 1024
    
    if file_size > max_size:
        return {
            "status": "error",
            "error": f"File too large: {file_size / (1024*1024):.2f}MB exceeds {max_size_mb}MB limit"
        }
    
    # Upload file
    return await upload_file(
        file_path=file_path,
        filename=os.path.basename(file_path)
    )
```

---

**Related**: [Messaging API](messaging.md) | [Streams API](streams.md) | [Users API](users.md)
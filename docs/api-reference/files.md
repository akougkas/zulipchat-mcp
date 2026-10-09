# Files API

File tools are extended mode only.

## Tools

- `upload_file(file_content=None, file_path=None, filename="", mime_type=None, chunk_size=1048576, stream=None, topic=None, message=None, file_content_base64=None)`
- `manage_files(operation, file_id=None, filters=None, download_path=None, share_in_stream=None, share_in_topic=None)`

## `manage_files` operations

- `list`
- `delete`
- `share`
- `download`
- `get_permissions`

## Examples

Upload and share:

```python
await upload_file(
    file_path="/tmp/report.pdf",
    stream="engineering",
    topic="report",
)
```

Download by path or URL identifier:

```python
await manage_files(
    operation="download",
    file_id="/user_uploads/abc/report.pdf",
    download_path="/tmp/report.pdf",
)
```

## Behavior notes

- Uploads include file validation and hash metadata.
- Delete uses the Zulip attachment deletion endpoint and requires `--unsafe`.
- Authenticated downloads accept only `/user_uploads/` paths on the configured Zulip origin, reject traversal, and do not follow redirects. For externally hosted or redirected files, omit `download_path` and open the returned URL in an authenticated browser.
- Upload reads and downloaded content are limited to 25 MB.
- Over HTTP, `file_path` and `download_path` are disabled to protect the server filesystem. Supply `file_content` for UTF-8 text, `file_content_base64` for arbitrary binary bytes, or omit `download_path` to obtain a URL. Local path operations remain available over stdio.
- Upload requires exactly one source. Base64 uses canonical standard encoding,
  rejects malformed input, and bounds encoded size before decoding. Empty
  content is valid. The decoded payload is limited to 25 MiB.

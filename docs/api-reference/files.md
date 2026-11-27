# Files API

File tools are extended mode only.

## Tools

- `upload_file(file_content=None, file_path=None, filename="", mime_type=None, chunk_size=1048576, stream=None, topic=None, message=None, file_content_base64=None)`
- `get_files(limit=50, cursor=None)`: read-only; your uploads, newest first
- `download_file(file_id, download_path=None)`: returns the download URL, or saves the file to a new local path
- `share_file(file_id, stream, topic=None)`: posts a link to the file in a channel topic
- `delete_file(attachment_id)`: destructive; requires `--unsafe`

## Examples

Upload and share:

```python
await upload_file(
    file_path="reports/report.pdf",
    stream="engineering",
    topic="report",
)
```

Download by path or URL identifier:

```python
await download_file(
    file_id="/user_uploads/abc/report.pdf",
    download_path="downloads/report.pdf",
)
```

List uploads one page at a time:

```python
page = await get_files(limit=50)
await get_files(limit=50, cursor=page["next_cursor"])
```

## Local file root

`file_path` and `download_path` must resolve inside the server's file root:
`--file-root DIR`, else `ZULIPCHAT_FILE_ROOT`, else the directory the server
was started in. Relative paths resolve against the server's working directory.
A path that leaves the root, through `..`, an absolute path or a symlink, is
refused with `PATH_OUTSIDE_ROOT` before any file is opened or any request is
made; the error's `recovery.hint` names the root. `download_file` never
overwrites: an existing `download_path` returns `ALREADY_EXISTS`.

## Behavior notes

- Uploads include file validation and hash metadata.
- `get_files` returns at most `limit` files (1-500) with `total`; when more
  remain, pass `next_cursor` back as `cursor`.
- Delete uses the Zulip attachment deletion endpoint and requires `--unsafe`.
- Authenticated downloads accept only `/user_uploads/` paths on the configured Zulip origin, reject traversal, and do not follow redirects. For externally hosted or redirected files, omit `download_path` and open the returned URL in an authenticated browser.
- Upload reads and downloaded content are limited to 25 MB.
- Over HTTP, `file_path` and `download_path` are disabled to protect the server filesystem. Supply `file_content` for UTF-8 text, `file_content_base64` for arbitrary binary bytes, or omit `download_path` to obtain a URL. Local path operations remain available over stdio.
- Upload requires exactly one source. Base64 uses canonical standard encoding,
  rejects malformed input, and bounds encoded size before decoding. Empty
  content is valid. The decoded payload is limited to 25 MiB.

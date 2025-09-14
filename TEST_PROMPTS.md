# Interactive Test Prompts for ZulipChat MCP v2.5.0

## Prerequisites
Set up your environment variables or use CLI flags:
```bash
export ZULIP_EMAIL="your@email.com"
export ZULIP_API_KEY="your-api-key"
export ZULIP_SITE="https://your-org.zulipchat.com"

# Or use .env file
cp .env.example .env
# Edit .env with your credentials
```

## Installation Test Commands

### 1. Test from GitHub (latest)
```bash
# Clean test - remove any cached versions first
uv cache clean

# Install and run from GitHub
uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp --help

# With credentials
uvx --from git+https://github.com/akougkas/zulipchat-mcp.git zulipchat-mcp \
  --zulip-email $ZULIP_EMAIL \
  --zulip-api-key $ZULIP_API_KEY \
  --zulip-site $ZULIP_SITE
```

### 2. Test specific tag
```bash
uvx --from git+https://github.com/akougkas/zulipchat-mcp.git@v2.5.0 zulipchat-mcp --help
```

### 3. Local development test
```bash
# In the project directory
uv run zulipchat-mcp --help
uv run zulipchat-mcp --zulip-email $ZULIP_EMAIL --zulip-api-key $ZULIP_API_KEY --zulip-site $ZULIP_SITE
```

## MCP Tool Test Prompts (Use with Claude Desktop)

### Test 1: Type Conversion Fix (Critical)
**Purpose**: Verify the string-to-int conversion fix works
```
Search for messages from the last 3 days
```
Expected: Should work without "'3' is not valid" error

### Test 2: Message Operations
```
Send a test message to the "general" stream with topic "test-v2.5.0" saying "Testing ZulipChat MCP v2.5.0 with type fixes"
```

### Test 3: Search with Filters
```
Search for messages in the last 24 hours that have links
```

### Test 4: Stream Operations
```
List all streams I have access to
```

### Test 5: User Information
```
Get information about my Zulip user profile
```

### Test 6: Analytics
```
Get analytics for the last 7 days
```

### Test 7: Bulk Operations
```
Mark all messages in the "general" stream as read
```

### Test 8: Reaction Management
```
Add a thumbs up reaction to message ID 12345
```
(Replace 12345 with an actual message ID from your Zulip)

### Test 9: Identity Switching
```
Switch to bot identity and tell me which identity is active
```

### Test 10: Complex Search
```
Search for messages from user@example.com in the "development" stream with attachments from the last 30 days
```

## Python API Test Script

Create `test_api.py`:
```python
#!/usr/bin/env python3
import asyncio
from src.zulipchat_mcp.tools.messaging_v25 import search_messages, message
from src.zulipchat_mcp.tools.streams_v25 import list_streams
from src.zulipchat_mcp.tools.users_v25 import get_own_user

async def test_type_conversion():
    """Test that string parameters are converted correctly"""
    print("Testing type conversion with string parameters...")

    # This should work with the fix
    result = await search_messages(
        last_days='3',  # String instead of int
        num_before='10',  # String instead of int
        num_after='20'   # String instead of int
    )

    assert result['status'] == 'success', f"Failed: {result}"
    print(f"✅ Type conversion test passed! Found {len(result.get('messages', []))} messages")

async def test_basic_operations():
    """Test basic MCP operations"""
    print("\nTesting basic operations...")

    # Test 1: Get user info
    user = await get_own_user()
    print(f"✅ User: {user.get('user', {}).get('full_name', 'Unknown')}")

    # Test 2: List streams
    streams = await list_streams()
    print(f"✅ Found {len(streams.get('streams', []))} streams")

    # Test 3: Search messages
    messages = await search_messages(last_hours=24)
    print(f"✅ Found {len(messages.get('messages', []))} messages in last 24 hours")

async def main():
    print("=== ZulipChat MCP v2.5.0 API Tests ===\n")

    try:
        await test_type_conversion()
        await test_basic_operations()
        print("\n🎉 All tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
```

Run with:
```bash
uv run python test_api.py
```

## TestPyPI Publishing Checklist

Before publishing to TestPyPI:

1. ✅ Version is v2.5.0 in all files
2. ✅ Tag v2.5.0 points to latest commit
3. ✅ GitHub release updated
4. ✅ All tests pass locally
5. ✅ uvx from GitHub works

### Build and Publish to TestPyPI
```bash
# Clean previous builds
rm -rf dist/

# Build the package
uv build

# Check the built files
ls -la dist/

# Upload to TestPyPI
uv publish --index-url https://test.pypi.org/legacy/ \
  --username __token__ \
  --password YOUR_TESTPYPI_TOKEN

# Test installation from TestPyPI
uvx --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    zulipchat-mcp --help
```

## Troubleshooting

### Issue: "3 is not valid under any of the given schemas"
**Solution**: This is fixed in v2.5.0. Make sure you're using the latest version.

### Issue: Import errors
**Solution**: Ensure you're using Python 3.10+ and have run `uv sync`

### Issue: Connection errors
**Solution**: Verify your credentials and that your Zulip site URL includes https://

### Issue: Package not found on TestPyPI
**Solution**: Wait 1-2 minutes after publishing, or check the exact package name

## Success Criteria

✅ All test prompts work without errors
✅ Type conversion works (string parameters accepted)
✅ uvx installation from GitHub succeeds
✅ TestPyPI installation works
✅ All MCP tools are accessible
✅ Identity switching works
✅ Analytics returns data
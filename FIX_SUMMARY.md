# Fix Summary: Bot Hanging on AI Reply Generation

## Problem

The bot was hanging when trying to generate AI replies. The logs showed:
```
[INFO] bot.handlers: Bot mentioned, using function calling flow
[INFO] bot.conversation_manager: Started conversation...
[INFO] bot.openai_integration: Generating AI reply for thread...
```

Then the bot would get stuck indefinitely.

## Root Cause

The issue was in `bot/openai_integration.py` in the `get_thread_context()` function at line 128:

```python
response = await client.room_messages(
    room_id=room.room_id,
    start="",  # ← PROBLEM: Empty string is invalid
    limit=limit * 2,
)
```

The `room_messages()` API requires a valid sync token for the `start` parameter. Passing an empty string causes the Matrix client to hang or behave incorrectly, as it doesn't know where to start fetching messages from.

## Solution

### 1. Fixed the `start` token issue (bot/openai_integration.py)

Updated `get_thread_context()` to properly use the room's `prev_batch` token:

```python
# Get the prev_batch token from the room timeline
# This is the proper way to fetch historical messages
start_token = room.prev_batch if hasattr(room, 'prev_batch') and room.prev_batch else ""

if not start_token:
    logger.warning(f"No prev_batch token available for room {room.room_id}, cannot fetch thread context")
    return []

logger.debug(f"Fetching thread context with token: {start_token[:20]}...")

response = await client.room_messages(
    room_id=room.room_id,
    start=start_token,  # ← Fixed: Use proper token
    limit=limit * 2,
)
```

### 2. Added timeout protection (bot/matrix_wrapper.py)

Enhanced `room_messages()` to include timeout protection:

```python
async def room_messages(
    self,
    room_id: str,
    start: str,
    end: Optional[str] = None,
    direction: str = "b",
    limit: int = 10,
    message_filter: Optional[dict] = None,
    timeout: int = 30  # ← Added timeout parameter
):
    """Get messages from a room (thread-safe)."""
    logger.debug(f"Acquiring lock for room_messages from {room_id}...")
    async with self._lock:
        logger.debug(f"Lock acquired, fetching messages from {room_id} (timeout={timeout}s)")
        try:
            return await asyncio.wait_for(
                self._client.room_messages(...),
                timeout=timeout  # ← Added timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"room_messages timed out after {timeout}s for room {room_id}")
            raise
```

### 3. Enhanced error handling in generate_ai_reply (bot/openai_integration.py)

Added timeout and exception handling when fetching thread context:

```python
# Fetch thread context with timeout protection
try:
    thread_messages = await asyncio.wait_for(
        get_thread_context(client, room, thread_root_id, MAX_CONTEXT_MESSAGES),
        timeout=45  # 45 seconds total timeout
    )
except asyncio.TimeoutError:
    logger.error(f"Thread context fetch timed out for {thread_root_id}")
    thread_messages = []
except Exception as e:
    logger.error(f"Error fetching thread context: {e}", exc_info=True)
    thread_messages = []

if not thread_messages:
    # No thread context, just use current message
    logger.info("Using current message only (no thread context available)")
    thread_messages = [event]
```

### 4. Improved logging for debugging (bot/matrix_wrapper.py)

Added detailed lock acquisition logging to help diagnose future issues:

```python
logger.debug(f"Acquiring lock for room_send to {room_id}...")
async with self._lock:
    logger.debug(f"Lock acquired, sending message to {room_id}")
    try:
        result = await self._client.room_send(...)
        logger.debug(f"Message sent to {room_id}, releasing lock")
        return result
    except Exception as e:
        logger.error(f"Error in room_send to {room_id}: {e}")
        raise
```

## Tests Added

Added three new tests in `tests/test_openai_integration.py`:

1. **test_get_thread_context_timeout**: Verifies timeout handling works correctly
2. **test_get_thread_context_no_prev_batch**: Verifies missing prev_batch is handled gracefully
3. **test_get_thread_context_empty_prev_batch**: Verifies empty prev_batch is handled gracefully

All new tests pass ✅

## Files Modified

1. `/Users/chrisowen/Documents/Code/MatrixBot/bot/openai_integration.py`
   - Fixed `get_thread_context()` to use proper prev_batch token
   - Added timeout protection when calling `get_thread_context()`
   - Added better error logging

2. `/Users/chrisowen/Documents/Code/MatrixBot/bot/matrix_wrapper.py`
   - Added timeout parameter to `room_messages()`
   - Added detailed lock acquisition logging for debugging
   - Enhanced error handling in `room_send()` and `room_messages()`

3. `/Users/chrisowen/Documents/Code/MatrixBot/tests/test_openai_integration.py`
   - Updated MockRoom to include prev_batch token
   - Added three new test cases for error handling

## Expected Behavior After Fix

1. **Bot will no longer hang** when generating AI replies
2. **Graceful degradation**: If thread context cannot be fetched, bot will respond using just the current message
3. **Timeout protection**: Operations will timeout after 30-45 seconds instead of hanging indefinitely
4. **Better diagnostics**: Detailed logging will help identify issues quickly

## Prevention

To prevent similar issues in the future:

1. Always use proper sync tokens when calling `room_messages()` - never pass empty strings
2. Always add timeout protection to Matrix API calls that might hang
3. Always provide graceful fallbacks when optional data (like thread context) cannot be fetched
4. Add logging at lock acquisition points to help diagnose deadlocks

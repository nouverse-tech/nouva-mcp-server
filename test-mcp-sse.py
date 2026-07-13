import asyncio
import json
import httpx
import sys

# Test script for Nouva MCP Server SSE transport
SERVER_URL = "http://localhost:8000"

async def test_mcp():
    print("🚀 Connecting to MCP SSE stream...")
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Establish SSE Connection
        async def read_sse():
            session_id = None
            message_url = None

            async with client.stream("GET", f"{SERVER_URL}/sse") as response:
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data_str = line[5:].strip()
                        if "session_id=" in data_str:
                            message_url = f"{SERVER_URL}{data_str}"
                            session_id = data_str.split("session_id=")[1]
                            print(f"✅ Connected! Session ID: {session_id}")
                            # Yield control to send initialize request
                            yield ("connected", message_url)
                        else:
                            # Handle incoming messages from server
                            try:
                                msg = json.loads(data_str)
                                yield ("message", msg)
                            except Exception:
                                pass

        sse_gen = read_sse()

        # Get connection info
        event_type, message_url = await sse_gen.__anext__()

        # 2. Send Initialize Request
        print("🔄 Sending 'initialize' request...")
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0"}
            }
        }
        res = await client.post(message_url, json=init_payload)
        if res.status_code != 202:
            print(f"❌ Initialize POST failed: {res.status_code}")
            return

        # Wait for initialize response on SSE stream
        event_type, init_response = await sse_gen.__anext__()
        print("✅ Received initialize response:")
        print(json.dumps(init_response, indent=2))

        # 3. Send Initialized Notification
        print("🔄 Sending 'notifications/initialized'...")
        initialized_payload = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        await client.post(message_url, json=initialized_payload)

        # 4. Call memory_query Tool
        query = "RTX 5060"
        if len(sys.argv) > 1:
            query = sys.argv[1]

        print(f"🔍 Calling 'memory_query' with query: '{query}'...")
        call_payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "memory_query",
                "arguments": {
                    "query": query
                }
            }
        }
        await client.post(message_url, json=call_payload)

        # Wait for tool response on SSE stream
        event_type, tool_response = await sse_gen.__anext__()
        print("\n=== TOOL RESPONSE ===")
        if "result" in tool_response:
            for content in tool_response["result"].get("content", []):
                print(content.get("text", ""))
        else:
            print(json.dumps(tool_response, indent=2))

if __name__ == "__main__":
    asyncio.run(test_mcp())

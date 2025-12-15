import asyncio
import websockets

async def test():
    uri = "ws://localhost:8000/chat/sources/github/user/repo-a"
    async with websockets.connect(uri) as websocket:
        print(await websocket.recv()) # Initial "Connected" message
        await websocket.send("Hello Jules")
        print(await websocket.recv()) # Response (mock)

asyncio.run(test())

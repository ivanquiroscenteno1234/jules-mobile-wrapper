import asyncio
import time
import httpx
import uvicorn
from fastapi import FastAPI, File, UploadFile
import os
import uuid
import sys

# Minimal version of the STT endpoint to test blocking
app = FastAPI()

# We will test two versions:
# /stt/sync (current implementation)
# /stt/async (optimized)

@app.post("/stt/sync")
async def stt_sync(file: UploadFile = File(...)):
    ext = file.filename.split('.')[-1] if file.filename and '.' in file.filename else 'raw'
    temp_filename = f"temp_{uuid.uuid4()}.{ext}"

    # Current code
    with open(temp_filename, "wb") as buffer:
        buffer.write(await file.read())

    os.remove(temp_filename)
    return {"status": "ok"}

@app.post("/stt/async")
async def stt_async(file: UploadFile = File(...)):
    ext = file.filename.split('.')[-1] if file.filename and '.' in file.filename else 'raw'
    temp_filename = f"temp_{uuid.uuid4()}.{ext}"

    # Optimized code
    content = await file.read()
    def write_file():
        with open(temp_filename, "wb") as buffer:
            buffer.write(content)
    await asyncio.to_thread(write_file)

    def remove_file():
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
    await asyncio.to_thread(remove_file)
    return {"status": "ok"}

@app.get("/ping")
async def ping():
    return {"status": "ok"}

async def run_benchmark():
    # Start server in background thread or process is complicated,
    # instead we can just benchmark the handlers directly, or run the server with uvicorn.
    # We will use another process to run the server.
    pass

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "server":
        uvicorn.run(app, host="127.0.0.1", port=8001)

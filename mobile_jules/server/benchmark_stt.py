import asyncio
import time
import httpx
import uvicorn
from fastapi import FastAPI, File, UploadFile
import os
import uuid
import sys
import multiprocessing

app = FastAPI()

# Sync implementation (baseline)
@app.post("/stt/sync")
async def stt_sync(file: UploadFile = File(...)):
    ext = file.filename.split('.')[-1] if file.filename and '.' in file.filename else 'raw'
    temp_filename = f"temp_{uuid.uuid4()}.{ext}"

    with open(temp_filename, "wb") as buffer:
        buffer.write(await file.read())

    os.remove(temp_filename)
    return {"status": "ok"}

# Async implementation (optimized)
@app.post("/stt/async")
async def stt_async(file: UploadFile = File(...)):
    ext = file.filename.split('.')[-1] if file.filename and '.' in file.filename else 'raw'
    temp_filename = f"temp_{uuid.uuid4()}.{ext}"

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

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="critical")

async def run_benchmark():
    # Wait for server to start
    await asyncio.sleep(1)

    # 50 MB file payload
    payload = b"0" * (50 * 1024 * 1024)
    file_tuple = ("test.bin", payload, "application/octet-stream")

    async with httpx.AsyncClient(timeout=30.0) as client:
        print("Benchmarking /stt/sync...")

        # Measure event loop blocking
        # We start a background task that repeatedly checks the time.
        # If the event loop is blocked, the time difference will be large.
        blocking_delays = []
        keep_running = True

        async def monitor_event_loop():
            while keep_running:
                start = time.perf_counter()
                await asyncio.sleep(0.01)
                delay = time.perf_counter() - start - 0.01
                if delay > 0.005:  # Only record significant delays
                    blocking_delays.append(delay)

        monitor_task = asyncio.create_task(monitor_event_loop())

        # Send concurrent requests
        start_time = time.perf_counter()
        tasks = []
        for _ in range(5):
            tasks.append(client.post("http://127.0.0.1:8001/stt/sync", files={"file": file_tuple}))

        await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start_time

        keep_running = False
        await monitor_task

        sync_max_delay = max(blocking_delays) if blocking_delays else 0
        sync_avg_delay = sum(blocking_delays)/len(blocking_delays) if blocking_delays else 0

        print(f"Sync Results:")
        print(f"Total time: {total_time:.3f}s")
        print(f"Max event loop blocking delay: {sync_max_delay*1000:.1f}ms")

        print("\nBenchmarking /stt/async...")
        blocking_delays.clear()
        keep_running = True
        monitor_task = asyncio.create_task(monitor_event_loop())

        start_time = time.perf_counter()
        tasks = []
        for _ in range(5):
            tasks.append(client.post("http://127.0.0.1:8001/stt/async", files={"file": file_tuple}))

        await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start_time

        keep_running = False
        await monitor_task

        async_max_delay = max(blocking_delays) if blocking_delays else 0

        print(f"Async Results:")
        print(f"Total time: {total_time:.3f}s")
        print(f"Max event loop blocking delay: {async_max_delay*1000:.1f}ms")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "run_client":
        asyncio.run(run_benchmark())
    else:
        # Start server in process
        server_process = multiprocessing.Process(target=run_server)
        server_process.start()

        try:
            # Run benchmark
            import subprocess
            subprocess.run([sys.executable, "benchmark_stt.py", "run_client"])
        finally:
            server_process.terminate()
            server_process.join()

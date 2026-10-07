#!/home/wolf/miniconda3/envs/messiah/bin/python3
import asyncio
import os
import sys
import logging

LOG_FILE = "/home/brice/polymarket-intelligence/scripts/proxy.log"
logging.basicConfig(
    filename=LOG_FILE,
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("tailscale_proxy")

LISTEN_HOST = "100.110.82.43"
LISTEN_PORT = 5433
TARGET_HOST = "127.0.0.1"
TARGET_PORT = 5433

async def pipe(reader, writer):
    try:
        while not reader.at_eof():
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

async def handle_client(client_reader, client_writer):
    peer = client_writer.get_extra_info("peername")
    logger.info(f"Incoming connection from {peer}")
    try:
        target_reader, target_writer = await asyncio.open_connection(TARGET_HOST, TARGET_PORT)
    except Exception as e:
        logger.error(f"Failed to connect to backend {TARGET_HOST}:{TARGET_PORT} - {e}")
        client_writer.close()
        return

    asyncio.create_task(pipe(client_reader, target_writer))
    asyncio.create_task(pipe(target_reader, client_writer))

def daemonize():
    if os.fork() > 0:
        sys.exit(0)
    os.setsid()
    if os.fork() > 0:
        sys.exit(0)
    sys.stdout.flush()
    sys.stderr.flush()
    with open('/dev/null', 'r') as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())
    with open(LOG_FILE, 'a') as log:
        os.dup2(log.fileno(), sys.stdout.fileno())
        os.dup2(log.fileno(), sys.stderr.fileno())

async def run_server():
    server = await asyncio.start_server(handle_client, LISTEN_HOST, LISTEN_PORT, reuse_address=True)
    logger.info(f"Tailscale PostgreSQL proxy active on {LISTEN_HOST}:{LISTEN_PORT} -> {TARGET_HOST}:{TARGET_PORT}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    daemonize()
    asyncio.run(run_server())

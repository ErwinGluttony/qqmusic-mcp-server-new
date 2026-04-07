"""
Simple MCP stdio <-> WebSocket pipe with optional unified config.
"""
import asyncio
import websockets
import subprocess
import logging
import os
import signal
import sys
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('MCP_PIPE')

INITIAL_BACKOFF = 1
MAX_BACKOFF = 600

async def connect_with_retry(uri, target):
    reconnect_attempt = 0
    backoff = INITIAL_BACKOFF
    while True:
        try:
            if reconnect_attempt > 0:
                logger.info(f"[{target}] Waiting {backoff}s before reconnection...")
                await asyncio.sleep(backoff)
            await connect_to_server(uri, target)
        except Exception as e:
            reconnect_attempt += 1
            logger.warning(f"[{target}] Connection closed (attempt {reconnect_attempt}): {e}")
            backoff = min(backoff * 2, MAX_BACKOFF)

async def connect_to_server(uri, target):
    try:
        logger.info(f"[{target}] Connecting to WebSocket server...")
        async with websockets.connect(uri) as websocket:
            logger.info(f"[{target}] Successfully connected")
            cmd, env = build_server_command(target)
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding='utf-8',
                text=True,
                env=env
            )
            logger.info(f"[{target}] Started server: {' '.join(cmd)}")
            await asyncio.gather(
                pipe_websocket_to_process(websocket, process, target),
                pipe_process_to_websocket(process, websocket, target)
            )
    except Exception as e:
        logger.error(f"[{target}] Error: {e}")
        raise

async def pipe_websocket_to_process(ws, process, target):
    try:
        async for msg in ws:
            if process.stdin:
                process.stdin.write(msg + '\n')
                process.stdin.flush()
    except Exception as e:
        logger.warning(f"[{target}] WebSocket read error: {e}")

async def pipe_process_to_websocket(process, ws, target):
    try:
        while True:
            line = process.stdout.readline()
            if not line:
                break
            await ws.send(line.strip())
    except Exception as e:
        logger.warning(f"[{target}] Process read error: {e}")

def load_config():
    config_path = os.environ.get('MCP_CONFIG', 'mcp_config.json')
    if os.path.exists(config_path):
        with open(config_path) as f:
            return json.load(f)
    return {}

def build_server_command(target):
    cfg = load_config()
    servers = cfg.get('mcpServers', {})
    entry = servers.get(target, {})
    cmd = [entry.get('command', 'python'), '-m', target]
    return cmd, os.environ.copy()

def signal_handler(sig, frame):
    logger.info("Interrupted")
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    endpoint_url = os.environ.get('MCP_ENDPOINT')
    if not endpoint_url:
        logger.error("Please set MCP_ENDPOINT environment variable")
        sys.exit(1)

    async def main():
        cfg = load_config()
        servers = cfg.get('mcpServers', {})
        enabled = [name for name, entry in servers.items() if not entry.get('disabled')]
        if not enabled:
            raise RuntimeError("No enabled servers")
        logger.info(f"Starting servers: {', '.join(enabled)}")
        tasks = [asyncio.create_task(connect_with_retry(endpoint_url, t)) for t in enabled]
        await asyncio.gather(*tasks)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted")
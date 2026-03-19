import argparse
import asyncio

from server.config import ServerConfig
from server.ircd import IRCd


async def main() -> None:
    parser = argparse.ArgumentParser(description="agentirc IRC server")
    parser.add_argument("--name", default="agentirc", help="Server name (used in nick prefix)")
    parser.add_argument("--host", default="0.0.0.0", help="Listen address")
    parser.add_argument("--port", type=int, default=6667, help="Listen port")
    args = parser.parse_args()

    config = ServerConfig(name=args.name, host=args.host, port=args.port)
    ircd = IRCd(config)
    await ircd.start()
    print(f"agentirc '{config.name}' listening on {config.host}:{config.port}")

    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        await ircd.stop()


if __name__ == "__main__":
    asyncio.run(main())

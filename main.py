import asyncio
import signal
import sys
from core.config import Config
from core.logger import logger
from core.orchestrator import Orchestrator

class TradingSystem:
    def __init__(self):
        self.orchestrator = None
        self.running = False

    async def start(self):
        logger.info('Initializing Trading System...')
        self.orchestrator = Orchestrator()
        success = await self.orchestrator.start()

        if success:
            self.running = True
            logger.info('Trading system is running. Press Ctrl+C to stop.')
            await self.keep_alive()
        else:
            logger.error('Failed to start trading system')
            sys.exit(1)

    async def keep_alive(self):
        loop = asyncio.get_event_loop()
        stop_event = asyncio.Event()

        def signal_handler():
            logger.info('Shutdown signal received')
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)

        await stop_event.wait()
        await self.shutdown()

    async def shutdown(self):
        logger.info('Shutting down trading system...')
        self.running = False
        if self.orchestrator:
            await self.orchestrator.stop()
        logger.info('System shutdown complete')
        sys.exit(0)

async def main():
    system = TradingSystem()
    await system.start()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('System interrupted by user')
    except Exception as e:
        logger.error(f'Fatal error: {e}', exc_info=True)
        sys.exit(1)

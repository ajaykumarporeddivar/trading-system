import ccxt
from typing import Dict, Any, Optional
from core.config import Config
from core.logger import logger
from storage.database import TradingJournal

class ExecutionAgent:
    def __init__(self):
        self.exchange = getattr(ccxt, Config.EXCHANGE)({
            'apiKey': Config.EXCHANGE_API_KEY,
            'secret': Config.EXCHANGE_API_SECRET,
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        if Config.USE_TESTNET:
            if Config.EXCHANGE == 'binance':
                self.exchange.set_sandbox_mode(True)
        self.journal = TradingJournal()
        logger.info(f'Execution Agent initialized - {Config.EXCHANGE}')

    async def place_market_order(self, symbol: str, side: str, quantity: float) -> Optional[Dict[str, Any]]:
        try:
            order = self.exchange.create_market_order(symbol, side, quantity)
            logger.info(f'Market order placed: {symbol} {side} {quantity} @ {order.get("average", order.get("price"))}')
            return {
                'order_id': order['id'],
                'symbol': symbol,
                'side': side,
                'quantity': order['amount'],
                'price': order.get('average', order.get('price')),
                'status': order['status'],
                'timestamp': order.get('datetime')
            }
        except Exception as e:
            logger.error(f'Failed to place market order for {symbol}: {e}')
            return None

    async def place_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> Optional[Dict[str, Any]]:
        try:
            order = self.exchange.create_limit_order(symbol, side, quantity, price)
            logger.info(f'Limit order placed: {symbol} {side} {quantity} @ {price}')
            return {
                'order_id': order['id'],
                'symbol': symbol,
                'side': side,
                'quantity': order['amount'],
                'price': price,
                'status': order['status'],
                'timestamp': order.get('datetime')
            }
        except Exception as e:
            logger.error(f'Failed to place limit order for {symbol}: {e}')
            return None

    async def set_stop_loss(self, symbol: str, side: str, quantity: float, stop_price: float) -> Optional[Dict[str, Any]]:
        try:
            order_side = 'sell' if side == 'buy' else 'buy'
            order = self.exchange.create_order(symbol, 'stop_loss', order_side, quantity, None, {'stopPrice': stop_price})
            logger.info(f'Stop loss set: {symbol} @ {stop_price}')
            return {'order_id': order['id'], 'stop_price': stop_price, 'status': order['status']}
        except Exception as e:
            logger.error(f'Failed to set stop loss for {symbol}: {e}')
            return None

    async def set_take_profit(self, symbol: str, side: str, quantity: float, take_profit_price: float) -> Optional[Dict[str, Any]]:
        try:
            order_side = 'sell' if side == 'buy' else 'buy'
            order = self.exchange.create_order(symbol, 'take_profit', order_side, quantity, None, {'stopPrice': take_profit_price})
            logger.info(f'Take profit set: {symbol} @ {take_profit_price}')
            return {'order_id': order['id'], 'take_profit_price': take_profit_price, 'status': order['status']}
        except Exception as e:
            logger.error(f'Failed to set take profit for {symbol}: {e}')
            return None

    async def execute_trade(self, trade_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        symbol = trade_data['symbol']
        side = trade_data['side'].lower()
        quantity = trade_data['quantity']
        stop_loss = trade_data.get('stop_loss')
        take_profit = trade_data.get('take_profit')

        order = await self.place_market_order(symbol, side, quantity)
        if not order:
            return None

        entry_price = order['price']
        result = {
            'entry_order': order,
            'stop_loss': None,
            'take_profit': None
        }

        if stop_loss:
            sl_order = await self.set_stop_loss(symbol, side, quantity, stop_loss)
            result['stop_loss'] = sl_order

        if take_profit:
            tp_order = await self.set_take_profit(symbol, side, quantity, take_profit)
            result['take_profit'] = tp_order

        await self.journal.log_trade({
            'symbol': symbol,
            'side': side.upper(),
            'entry_price': entry_price,
            'quantity': quantity,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'status': 'open',
            'agent_verdict': trade_data.get('verdict'),
            'confidence': trade_data.get('confidence'),
            'order_id': order['order_id']
        })

        logger.info(f'Trade executed: {symbol} {side.upper()} {quantity} @ {entry_price}')
        return result

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        try:
            self.exchange.cancel_order(order_id, symbol)
            logger.info(f'Order cancelled: {order_id}')
            return True
        except Exception as e:
            logger.error(f'Failed to cancel order {order_id}: {e}')
            return False

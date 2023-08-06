import asyncio
import logging
import platform
import signal
from datetime import datetime
from typing import List

import pandas as pd
from hades.core import Strategy, Messenger, Order, Position, Tick, TradeBotConf, MessageFactory, MessageEnum, \
    TradeExecutor, ExchangeEnum


class NotificationStrategy(Strategy):
    def __init__(self, messenger: Messenger) -> None:
        super().__init__(strategy_id='a4e16024-ec4c-42f6-a6ad-845419df0788',
                         symbols=['BTCUSDT'],  # Binance is BTCUSDT, OKX is BTC-USDT-SWAP
                         instrument_type='SWAP',
                         klines=['1m'])
        self.messenger = messenger

    def on_order_status(self, orders: List[Order]):
        now = datetime.now().strftime("%H:%M:%S")
        for order in orders:
            if order.status == 'TRADE':
                self.messenger.notify(f'{now}-Order Filled')
            elif order.status == 'NEW':
                self.messenger.notify(f'{now}-New Order')
            elif order.status == 'CANCELED':
                self.messenger.notify(f'{now}-Order Cancelled')

    def on_position_status(self, positions: List[Position]):
        super().on_position_status(positions)
        for pos in positions:
            if pos.unrealized_profit_ratio < -20:
                self.messenger.notify_with_interval(
                    f'{datetime.now().strftime("%H:%M:%S")}-{pos.unrealized_profit_ratio}', 60 * 3)

    def on_tick(self, ticks: List[Tick]):
        super().on_tick(ticks)
        df = pd.DataFrame([tick.model_dump() for tick in self.ticks[-200:]])
        if df.price.std() > 30:
            self.messenger.notify_with_interval(
                f'{datetime.now().strftime("%H:%M:%S")} rapid price change, current = {self.ticks[-1].price}')


async def shutdown() -> None:
    tasks = []
    for task in asyncio.all_tasks(loop):
        if task is not asyncio.current_task(loop):
            task.cancel()
            tasks.append(task)
    results = await asyncio.gather(*tasks, return_exceptions=True)
    print("Finished awaiting cancelled tasks, results: {0}".format(results))
    loop.stop()


if __name__ == '__main__':
    logging.info('[1] init conf')
    conf = TradeBotConf.load()

    logging.info('[2] init messenger')
    _messenger = MessageFactory.build_messenger(MessageEnum.DingDing, conf)

    logging.info('[3] init strategy')
    strategy = NotificationStrategy(_messenger)

    logging.info('[4] init executor')
    executor = TradeExecutor(strategy, exchange=ExchangeEnum.Binance)

    loop = asyncio.get_event_loop()
    if platform.platform().find('Windows') == -1:
        for sig in [signal.SIGINT, signal.SIGTERM]:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
    try:
        loop.create_task(executor.execute())
        loop.run_forever()
    finally:
        loop.close()
        logging.info("Successfully shutdown the Mayhem service.")

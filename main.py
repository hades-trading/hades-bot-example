import signal
import asyncio
import logging
import platform
import json
from typing import List
from hades.core import *
import pandas as pd
import json
from typing import List



class NotificationStrategy(Strategy):
    def __init__(self, messager: Messager) -> None:
        super().__init__(id='a4e16024-ec4c-42f6-a6ad-845419df0788', 
                         # Binance is BTCUSDT
                         # OKX is BTC-USDT-SWAP
                         symbols=['BTCUSDT'],
                         instrumentType='SWAP', 
                         klines=['1m'])
        self.messager = messager

    def on_order_status(self, orders: List[Order]):
        for order in orders:
            self.messager.notify(f'{json.dumps(order._asdict(), default=str)}')

    def on_position_status(self, positions: List[Position]):
        super().on_position_status(positions)
        for pos in positions:
            if pos.unrealized_profit_ratio < -20:
                self.messager.notify_with_interval(f'{json.dumps(pos._asdict(), default=str)}')

    def on_tick(self, ticks: List[Tick]):
        super().on_tick(ticks)
        sample = [tick._asdict() for tick in self.ticks[-200:]]
        df = pd.DataFrame(sample)
        if df.price.std() > 15:
            self.messager.notify_with_interval(f'price rapid change, current = {sample[-1]["price"]}')



async def shutdown(sig: signal.Signals) -> None:
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

    logging.info('[2] init messager')
    messager = Messager(conf)

    logging.info('[3] init stragety')
    stragety = NotificationStrategy(messager)
  
    logging.info('[4] init executor')
    executor = TradeExecutor(stragety, backtesting=False, exchange=ExchangeEnum.Binance)

    loop = asyncio.get_event_loop()
    if platform.platform().find('Windows') == -1:
        for sig in [signal.SIGINT, signal.SIGTERM]:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(sig)))
    try:
        loop.create_task(executor.execute())
        loop.run_forever()
    finally:
        loop.close()
        logging.info("Successfully shutdown the Mayhem service.")
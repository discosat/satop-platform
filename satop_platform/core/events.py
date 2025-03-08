import logging
from dataclasses import dataclass
from queue import Queue
from typing import TypeVar, Generic, List, Any
from collections.abc import Callable, Awaitable

_T = TypeVar('EventData')

logger = logging.getLogger(__name__)

class SatOPEventManager:
    subscriptions: dict[str, dict[int, Callable[[_T], None]]]
    last_subscription_id: int

    def __init__(self):
        logger.debug('Initializing event manager')
        self.subscriptions = dict()
        self.last_subscription_id = 0

    def publish(self, event_key: str, message: _T) -> int:
        logger.debug(f'Publishing event: {event_key}')
        subs = self.subscriptions.get(event_key, dict())
        logger.debug(f'event subs: {subs}')
        for callback in subs.values():
            callback(message)

    def unsubscribe(self, event_key: str, subscriber_id: int):
        if not event_key in self.subscriptions:
            return
        
        if not subscriber_id in self.subscriptions[event_key]:
            return
        
        del self.subscriptions[event_key][subscriber_id]

    def subscribe(self, event_key: str, callback: Callable[[_T], None]) -> int:
        logger.debug(f'New subscription to event: {event_key}')
        subscription_id = self.last_subscription_id + 1

        if not event_key in self.subscriptions:
            self.subscriptions[event_key] = dict()
        
        self.subscriptions[event_key][subscription_id] = callback

        self.last_subscription_id = subscription_id

        return subscription_id
        
    # def subscribe_before(self, event_key: str, callback: Callable[[_T], None]) -> int:
    #     raise NotImplementedError
    
    # def subscribe_after(self, event_key: str, callback: Callable[[_T], None]) -> int:
    #     raise NotImplementedError
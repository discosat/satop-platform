import logging
from collections.abc import Callable
from typing import TypeVar

_T = TypeVar("EventData")

logger = logging.getLogger(__name__)


class SatOPEventManager:
    subscriptions: dict[str, dict[int, Callable[[_T], None]]]
    last_subscription_id: int

    def __init__(self):
        logger.debug("Initializing event manager")
        self.subscriptions = dict()
        self.last_subscription_id = 0

    def publish(self, event_key: str, message: _T) -> int:
        logger.debug(f"Publishing event: {event_key}")
        subs = self.subscriptions.get(event_key, dict())
        logger.debug(f"event subs: {subs}")
        for callback in subs.values():
            callback(message)

    def unsubscribe(self, event_key: str, subscriber_id: int):
        if event_key not in self.subscriptions:
            return

        if subscriber_id not in self.subscriptions[event_key]:
            return

        del self.subscriptions[event_key][subscriber_id]

    def subscribe(self, event_key: str, callback: Callable[[_T], None]) -> int:
        logger.debug(f"New subscription to event: {event_key}")
        subscription_id = self.last_subscription_id + 1

        if event_key not in self.subscriptions:
            self.subscriptions[event_key] = dict()

        self.subscriptions[event_key][subscription_id] = callback

        self.last_subscription_id = subscription_id

        return subscription_id

    # def subscribe_before(self, event_key: str, callback: Callable[[_T], None]) -> int:
    #     raise NotImplementedError

    # def subscribe_after(self, event_key: str, callback: Callable[[_T], None]) -> int:
    #     raise NotImplementedError

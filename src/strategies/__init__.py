from .default_strategy import default_strategy
from .blocking_strategy import blocking_strategy

from enum import Enum


class Strategy(Enum):
    DEFAULT = "default"
    BLOCKING = "blocking"


strategies = {
    Strategy.DEFAULT: default_strategy,
    Strategy.BLOCKING: blocking_strategy,
}


__all__ = ["Strategy", "strategies"]

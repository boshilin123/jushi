"""Public resources-module use cases.

Keep this module as the stable import facade used by Flask routes, the snapshot
script, application startup, and the deploy precheck. Implementation details
live in focused modules so callers do not need to change during the refactor.
"""

from .collector import quotas
from .recommendation import recommendation
from .snapshot import start_resource_snapshot_collector
from .trend import _build_trend_response, trend
from .trend_cache import start_resource_trend_cache_refresher as _start_trend_cache_refresher
from .views import cards, gpus, nodes, summary


def start_resource_trend_cache_refresher():
    return _start_trend_cache_refresher(_build_trend_response)


__all__ = [
    "start_resource_snapshot_collector",
    "start_resource_trend_cache_refresher",
    "summary",
    "nodes",
    "gpus",
    "quotas",
    "cards",
    "trend",
    "recommendation",
]

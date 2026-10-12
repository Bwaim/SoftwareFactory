from . import adapters
from .adapters.base import AdapterError


def notify(ctx, text):
    adapter = adapters.get_adapter(ctx)
    if "notify" not in adapter.capabilities():
        return
    try:
        adapter.notify(text)
    except AdapterError:
        pass

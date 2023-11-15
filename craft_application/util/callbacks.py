from __future__ import annotations
from typing import Callable, Iterable


def get_unique_callbacks(cls: type, callback_name: str) -> Iterable[Callable]:
    """Get all unique callbacks in a class's inheritance tree.

    Guarantees order to be the reverse of the method resolution order (that is,
    starting with ``object`` and working its way down the resolution tree to the
    class itself). This means that the callbacks for child classes may depend on
    or modify the results of the callbacks for the parent class.
    """
    callbacks = []
    for class_ in reversed(cls.mro()):
        callback = getattr(class_, callback_name, None)
        if callback is not None and callback not in callbacks:
            callbacks.append(callback)
    return callbacks

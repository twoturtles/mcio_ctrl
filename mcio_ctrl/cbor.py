"""CBOR processing helpers"""

import logging
from typing import Any, Final, TypeVar

import cbor2

LOG = logging.getLogger(__name__)

MCIO_PROTOCOL_TYPE: Final[str] = "__mcio_type__"


T = TypeVar("T")

_CBOR_TYPE_REGISTRY: dict[str, type] = {}


def MCioType(cls: type[T]) -> type[T]:
    _CBOR_TYPE_REGISTRY[cls.__name__] = cls
    return cls


def decode(data: bytes) -> Any | None:
    """Decode CBOR using MCioType classes where possible. Returns None on error"""
    try:
        return cbor2.loads(data, object_hook=object_hook)
    except Exception as e:
        LOG.error(f"CBOR load error: {type(e).__name__}: {e}")
        return None


def object_hook(decoder: cbor2.CBORDecoder, obj_dict: dict[Any, Any]) -> Any:
    mcio_type = obj_dict.pop(MCIO_PROTOCOL_TYPE, None)
    if isinstance(mcio_type, str):
        # The jackson MINIMAL_CLASS includes a leading dot
        mcio_type = mcio_type[1:] if len(mcio_type) > 0 else ""
        cls = _CBOR_TYPE_REGISTRY.get(mcio_type)
        if cls:
            return cls(**obj_dict)
        else:
            LOG.error(f"Unknown MCioType type: {mcio_type}")

    return obj_dict

"""CBOR processing helpers"""

import logging
from dataclasses import asdict
from typing import Any, Final, TypeVar

import cbor2

LOG = logging.getLogger(__name__)

# Used by MCio and mcio_ctrl to annotate protocol classes
MCIO_PROTOCOL_TYPE: Final[str] = "__mcio_type__"

# Maps protcol class names to the type and vice versa
_MCIO_NAME_TO_TYPE: dict[str, type] = {}
_MCIO_TYPE_TO_NAME: dict[type, str] = {}


T = TypeVar("T")


def MCioType(cls: type[T]) -> type[T]:
    """Decorator to register a class as used in the MCio protocol"""
    _MCIO_NAME_TO_TYPE[cls.__name__] = cls
    _MCIO_TYPE_TO_NAME[cls] = cls.__name__
    return cls


def encode(obj: Any) -> bytes:
    """Encode object to CBOR using MCioType class annotations"""
    return cbor2.dumps(obj, default=_default_encoder)


def decode(data: bytes) -> Any | None:
    """Decode CBOR using MCioType classes where possible. Returns None on error"""
    try:
        return cbor2.loads(data, object_hook=_object_hook)
    except Exception as e:
        LOG.error(f"CBOR load error: {type(e).__name__}: {e}")
        return None


def _object_hook(decoder: cbor2.CBORDecoder, obj_dict: dict[Any, Any]) -> Any:
    """Used by the CBOR parser. Decodes packet entries into MCioType classes where possible."""
    mcio_type = obj_dict.pop(MCIO_PROTOCOL_TYPE, None)
    if isinstance(mcio_type, str):
        # The jackson MINIMAL_CLASS includes a leading dot
        mcio_type = mcio_type[1:] if len(mcio_type) > 0 else ""
        cls = _MCIO_NAME_TO_TYPE.get(mcio_type)
        if cls:
            return cls(**obj_dict)
        else:
            LOG.error(f"Unknown MCioType type: {mcio_type}")

    return obj_dict


def _default_encoder(encoder: cbor2.CBOREncoder, value: Any) -> Any:
    cls = type(value)
    name = _MCIO_TYPE_TO_NAME.get(cls)
    if name:
        obj_dict = asdict(value)
        # Prepend the dot for Jackson
        obj_dict[MCIO_PROTOCOL_TYPE] = "." + name
        encoder.encode(obj_dict)
    else:
        raise TypeError(f"Cannot encode object of type {cls}")

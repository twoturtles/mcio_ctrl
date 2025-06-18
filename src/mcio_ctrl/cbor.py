"""CBOR processing helpers"""

import logging
from dataclasses import fields, is_dataclass
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
    # Use the Java Jackson style MINIMAL_CLASS name which includes a leading dot.
    name = "." + cls.__name__
    _MCIO_NAME_TO_TYPE[name] = cls
    _MCIO_TYPE_TO_NAME[cls] = name
    return cls


def encode(obj: Any) -> bytes:
    """Encode object to CBOR using MCioType class annotations"""
    return cbor2.dumps(typed_asdict(obj))


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
        cls = _MCIO_NAME_TO_TYPE.get(mcio_type)
        if cls:
            return cls(**obj_dict)
        else:
            LOG.error(f"Unknown MCioType type: {mcio_type}")

    # Non MCioType
    return obj_dict


def typed_asdict(obj: Any) -> Any:
    """Like dataclass asdict, but annotates MCioType classes with type info.
    Recursively walks the dataclass.
    """
    if is_dataclass(obj):
        cls = type(obj)
        cls_name = _MCIO_TYPE_TO_NAME.get(cls)
        result = {
            key: typed_asdict(getattr(obj, key))
            for key in (f.name for f in fields(obj))
        }
        if cls_name:
            result[MCIO_PROTOCOL_TYPE] = cls_name
        return result
    elif isinstance(obj, (list, tuple)):
        return [typed_asdict(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: typed_asdict(v) for k, v in obj.items()}
    else:
        return obj

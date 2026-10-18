"""Ordinary dataclass state construction; values belong to the user instance."""

from dataclasses import is_dataclass

from typing_extensions import TypeVar

_State_co = TypeVar("_State_co", covariant=True, default=object)  # noqa: PYI018 -- shared owner parameter


def _new_state(schema: type[object] | None) -> object | None:
    """Construct one dataclass without arguments, or return None for an unconfigured owner."""
    if schema is None:
        return None
    if not isinstance(schema, type) or not is_dataclass(schema):
        raise TypeError("state must be a dataclass class, not an instance")
    return schema()

"""Blob variable types for representing JavaScript Blob objects in Reflex."""

import dataclasses
from typing import TYPE_CHECKING, TypeVar

from reflex.vars.base import (
    LiteralVar,
    Var,
    VarData,
    var_operation,
    var_operation_return,
)

if TYPE_CHECKING:
    from reflex.vars import Var


@dataclasses.dataclass
class Blob:
    """Represents a JavaScript Blob object."""


BLOB_T = TypeVar("BLOB_T", bound=bytes | str, covariant=True)


class BlobVar(Var[BLOB_T], python_types=Blob):
    """A variable representing a JavaScript Blob object."""

    @classmethod
    def create(
        cls,
        value: str | bytes | Var,
        mime_type: str | Var,
        _var_data: VarData | None = None,
    ):
        """Create a BlobVar from the given value and MIME type.

        Args:
            value: The data to create the Blob from (string, bytes, or Var).
            mime_type: The MIME type of the Blob (string or Var).
            _var_data: Optional variable data.

        Returns:
            A BlobVar instance representing the JavaScript Blob object.
        """
        if not isinstance(value, Var):
            value = LiteralVar.create(value)
        if not isinstance(mime_type, Var):
            mime_type = LiteralVar.create(mime_type)
        elif type(value).__qualname__.endswith("BytesCastedVar"):
            value = f"new Uint8Array({value})"
        return cls(
            _js_expr=f"new Blob([{value}], {{ type: {mime_type} }})",
            _var_type=Blob,
            _var_data=_var_data,
        )

    def create_object_url(self):
        """Create a URL from this Blob object using window.URL.createObjectURL.

        Returns:
            A URL string representing the Blob object.
        """
        return create_url_from_blob_operation(self)


@var_operation
def create_url_from_blob_operation(value: BlobVar):
    """Create a URL from a Blob variable using window.URL.createObjectURL.

    Args:
        value: The Blob variable to create a URL from.

    Returns:
        A URL string representing the Blob object.
    """
    return var_operation_return(
        js_expression=f"window.URL.createObjectURL({value})",
        var_type=str,
    )


@dataclasses.dataclass(
    eq=False,
    frozen=True,
    slots=True,
)
class LiteralBlobVar(LiteralVar, BlobVar):
    """A literal version of a Blob variable."""

    _var_value: Blob = dataclasses.field(default_factory=Blob)

    @classmethod
    def create(
        cls,
        value: bytes | str,
        mime_type: str,
        _var_data: VarData | None = None,
    ) -> BlobVar:
        """Create a literal Blob variable from bytes or string data.

        Args:
            value: The data to create the Blob from (bytes or string).
            mime_type: The MIME type of the Blob.
            _var_data: Optional variable data.

        Returns:
            A BlobVar instance representing the Blob.
        """
        return cls(
            _js_expr=(
                f"new Blob([new Uint8Array({list(value)})], {{ type: '{mime_type}' }})"
                if isinstance(value, bytes)
                else f"new Blob([{value}], {{ type: '{mime_type}' }})"
            ),
            _var_type=bytes,
            _var_data=_var_data,
        )

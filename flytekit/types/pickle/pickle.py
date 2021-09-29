import os
import typing
from typing import Type

import cloudpickle

from flytekit.core.context_manager import FlyteContext
from flytekit.core.type_engine import TypeEngine, TypeTransformer
from flytekit.models import types as _type_models
from flytekit.models.core import types as _core_types
from flytekit.models.literals import Blob, BlobMetadata, Literal, Scalar
from flytekit.models.types import LiteralType

T = typing.TypeVar("T")


class FlytePickle(object):
    """
    This type is only used by flytekit internally. User should not use this type.
    Any type that flyte can't recognize will become FlytePickle
    """

    def __init__(self, python_type: Type[T]):
        self.python_type = python_type


class FlytePickleTransformer(TypeTransformer[FlytePickle]):
    PICKLE = "pickle"
    PYTHON_PICKLE_FORMAT = "PythonPickle"

    def __init__(self):
        super().__init__(name="FlytePickle", t=FlytePickle)

    def to_python_value(self, ctx: FlyteContext, lv: Literal, expected_python_type: Type[T]) -> T:
        uri = lv.scalar.blob.uri
        # Deserialize the pickle, and return data in the pickle,
        # and download pickle file to local first if file is not in the local file systems.
        if ctx.file_access.is_remote(uri):
            ctx.file_access.get_data(uri, self.PICKLE, False)
            uri = self.PICKLE
        infile = open(uri, "rb")
        data = cloudpickle.load(infile)
        infile.close()
        return data

    def to_literal(self, ctx: FlyteContext, python_val: T, python_type: Type[T], expected: LiteralType) -> Literal:
        meta = BlobMetadata(
            type=_core_types.BlobType(
                format=self.PYTHON_PICKLE_FORMAT, dimensionality=_core_types.BlobType.BlobDimensionality.SINGLE
            )
        )
        # Dump the task output into pickle
        local_dir = ctx.file_access.get_random_local_directory()
        os.makedirs(local_dir, exist_ok=True)
        uri = os.path.join(local_dir, self.PICKLE)
        outfile = open(uri, "w+b")
        cloudpickle.dump(python_val, outfile)
        outfile.close()

        remote_path = ctx.file_access.get_random_remote_path(uri)
        ctx.file_access.put_data(uri, remote_path, is_multipart=False)
        return Literal(scalar=Scalar(blob=Blob(metadata=meta, uri=remote_path)))

    def get_literal_type(self, t: Type[T]) -> LiteralType:
        return _type_models.LiteralType(
            blob=_core_types.BlobType(
                format=self.PYTHON_PICKLE_FORMAT, dimensionality=_core_types.BlobType.BlobDimensionality.SINGLE
            )
        )


TypeEngine.register(FlytePickleTransformer())
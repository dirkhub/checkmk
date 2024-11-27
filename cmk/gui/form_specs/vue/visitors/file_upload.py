#!/usr/bin/env python3
# Copyright (C) 2024 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
import base64
import uuid
from dataclasses import dataclass, field
from typing import Optional

from werkzeug.datastructures import FileStorage

from cmk.gui.form_specs.vue import shared_type_defs as VueComponents
from cmk.gui.form_specs.vue.validators import build_vue_validators
from cmk.gui.hooks import request_memoize
from cmk.gui.http import request
from cmk.gui.i18n import _
from cmk.gui.utils.encrypter import Encrypter

from cmk.rulesets.v1 import Title
from cmk.rulesets.v1.form_specs import FileUpload

from ._base import FormSpecVisitor
from ._type_defs import DataOrigin, DefaultValue, EMPTY_VALUE, EmptyValue
from ._utils import (
    compute_validators,
    create_validation_error,
    get_title_and_help,
)

FileName = str
FileType = str
FileContent = bytes
FileContentEncrypted = str


@dataclass(frozen=True, kw_only=True)
class FileUploadModel:
    input_uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    file_name: Optional[FileName] = None
    file_type: Optional[FileType] = None
    file_content_encrypted: Optional[FileContentEncrypted] = None


@request_memoize()
def read_content_of_uploaded_file(file_storage: FileStorage) -> FileContent:
    # We have to memoize the file content extraction, since the data can only be read once
    return file_storage.read()


class FileUploadVisitor(FormSpecVisitor[FileUpload, FileUploadModel]):
    def _parse_value(self, raw_value: object) -> FileUploadModel | EmptyValue:
        if isinstance(raw_value, DefaultValue):
            return EMPTY_VALUE

        if self.options.data_origin == DataOrigin.DISK:
            if not isinstance(raw_value, tuple):
                return EMPTY_VALUE

            return FileUploadModel(
                file_name=raw_value[0],
                file_type=raw_value[1],
                file_content_encrypted=self.encrypt_content(raw_value[2]),
            )

        # Handle DataOrigin.FRONTEND
        if not isinstance(raw_value, dict):
            return EMPTY_VALUE

        input_uuid = raw_value["input_uuid"]
        uploaded_file = request.files.get(input_uuid)

        if uploaded_file is not None:
            file_content = read_content_of_uploaded_file(uploaded_file) if uploaded_file else None

            if file_content is not None:
                # New file
                return FileUploadModel(
                    input_uuid=input_uuid,
                    file_name=uploaded_file.filename,
                    file_type=uploaded_file.content_type,
                    file_content_encrypted=self.encrypt_content(file_content),
                )

        if raw_value.get("file_name") is None:
            return EMPTY_VALUE

        # Existing file, all data is already in raw_value
        return FileUploadModel(
            input_uuid=input_uuid,
            file_name=raw_value["file_name"],
            file_type=raw_value["file_type"],
            file_content_encrypted=raw_value["file_content_encrypted"],
        )

    @classmethod
    def encrypt_content(cls, content: bytes) -> str:
        return base64.b64encode(
            Encrypter.encrypt(base64.b64encode(content).decode("ascii"))
        ).decode("ascii")

    @classmethod
    def decrypt_content(cls, content: str) -> bytes:
        return base64.b64decode(Encrypter.decrypt(base64.b64decode(content)))

    def _to_vue(
        self, raw_value: object, parsed_value: FileUploadModel | EmptyValue
    ) -> tuple[VueComponents.FileUpload, FileUploadModel]:
        title, help_text = get_title_and_help(self.form_spec)
        if isinstance(parsed_value, EmptyValue):
            parsed_value = FileUploadModel()

        return (
            VueComponents.FileUpload(
                title=title,
                help=help_text,
                validators=build_vue_validators(compute_validators(self.form_spec)),
                i18n=VueComponents.FileUploadI18n(
                    replace_file=_("Replace file"),
                ),
            ),
            parsed_value,
        )

    def _validate(
        self, raw_value: object, parsed_value: FileUploadModel | EmptyValue
    ) -> list[VueComponents.ValidationMessage]:
        if isinstance(parsed_value, EmptyValue):
            return create_validation_error("", Title("Invalid file"))
        return []

    def _to_disk(self, raw_value: object, parsed_value: FileUploadModel) -> object:
        assert parsed_value.file_name is not None
        assert parsed_value.file_type is not None
        assert parsed_value.file_content_encrypted is not None
        return (
            parsed_value.file_name,
            parsed_value.file_type,
            self.decrypt_content(parsed_value.file_content_encrypted),
        )
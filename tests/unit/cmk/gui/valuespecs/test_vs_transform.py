#!/usr/bin/env python3
# Copyright (C) 2022 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

import pytest

import cmk.gui.valuespec as vs

from .utils import (
    expect_validate_failure_migrate_or_transform,
    expect_validate_success_migrate_or_transform,
    request_var,
)


@pytest.fixture(name="transformed_age")
def fixture_transformed_age() -> vs.Transform[vs.Seconds]:
    return vs.Transform(
        vs.Age(minvalue=1, default_value=60),
        forth=lambda v: int(v * 60),
        back=lambda v: float(v) / 60.0,
        title="Normal check interval for service checks",
    )


class TestTransform:
    def test_allow_empty_is_passed_throught(self) -> None:
        assert (
            vs.Transform(
                vs.TextInput(allow_empty=False),
                forth=lambda v: v,
                back=lambda v: v,
            ).allow_empty()
            is False
        )
        assert (
            vs.Transform(
                vs.TextInput(allow_empty=True),
                forth=lambda v: v,
                back=lambda v: v,
            ).allow_empty()
            is True
        )

    def test_title(self) -> None:
        assert (
            vs.Transform(
                vs.TextInput(title="text_input_title"),
                forth=lambda v: v,
                back=lambda v: v,
            ).title()
            == "text_input_title"
        )
        assert (
            vs.Transform(
                vs.TextInput(title="text_input_title"),
                forth=lambda v: v,
                back=lambda v: v,
                title="transform_title",
            ).title()
            == "transform_title"
        )

    def test_help(self) -> None:
        assert (
            vs.Transform(
                vs.TextInput(help="text_input_help"),
                forth=lambda v: v,
                back=lambda v: v,
            ).help()
            == "text_input_help"
        )
        assert (
            vs.Transform(
                vs.TextInput(help="text_input_help"),
                forth=lambda v: v,
                back=lambda v: v,
                help="transform_help",
            ).help()
            == "transform_help"
        )

    # TODO: render_input

    def test_canonical_value(self, transformed_age: vs.Transform[vs.Seconds]) -> None:
        assert transformed_age.canonical_value() == 1 / 60

    def test_default_value(self, transformed_age: vs.Transform[vs.Seconds]) -> None:
        assert transformed_age.default_value() == 60 / 60

    def test_mask(self, transformed_age: vs.Transform[vs.Seconds]) -> None:
        assert transformed_age.mask(60) == 60

    def test_value_to_html(self, transformed_age: vs.Transform[vs.Seconds]) -> None:
        assert transformed_age.value_to_html(60) == "1 hours"

    def test_from_html_vars(self, transformed_age: vs.Transform[vs.Seconds]) -> None:
        with request_var(age_minutes="1"):
            # normal age field (without transfrom) would return 60 as it saves
            # the age in seconds.
            assert transformed_age.from_html_vars("age") == 1

    def test_validate(self, transformed_age: vs.Transform[vs.Seconds]) -> None:
        expect_validate_success_migrate_or_transform(transformed_age, 1)
        expect_validate_success_migrate_or_transform(transformed_age, 0.1)
        expect_validate_failure_migrate_or_transform(transformed_age, 0.0000001)


def test_transform_value_with_transform_vs() -> None:
    valuespec = vs.Transform(
        vs.TextInput(),
        forth=lambda x: x if x == "lala" else x.upper(),
        back=lambda x: x + "aaa",
    )

    assert valuespec.transform_value("lala") == "lalaaaa"
    assert valuespec.transform_value("AAA") == "AAAaaa"


def test_transform_value_in_dict() -> None:
    valuespec = vs.Dictionary(
        elements=[
            (
                "a",
                vs.Transform(
                    vs.TextInput(),
                    forth=lambda x: x if x == "lala" else x.upper(),
                    back=lambda x: x + "aaa",
                ),
            ),
        ]
    )

    assert valuespec.transform_value({"a": "lala"}) == {"a": "lalaaaa"}
    assert valuespec.transform_value({"a": "AAA"}) == {"a": "AAAaaa"}


def test_transform_value_in_tuple() -> None:
    assert vs.Tuple[tuple[str, str]](
        elements=[
            vs.Transform(
                vs.TextInput(),
                forth=lambda x: x if x == "lala" else x.upper(),
                back=lambda x: x + "aaa",
            ),
            vs.Transform(
                vs.TextInput(),
                forth=lambda x: x if x == "lala" else x.upper(),
                back=lambda x: x + "aaa",
            ),
        ]
    ).transform_value(("lala", "AAA")) == ("lalaaaa", "AAAaaa")


def test_transform_value_in_cascading_dropdown() -> None:
    valuespec = vs.CascadingDropdown(
        choices=[
            ("a", "Title a", vs.TextInput()),
            (
                "b",
                "Title b",
                vs.Transform(
                    vs.TextInput(),
                    forth=lambda x: x if x == "lala" else x.upper(),
                    back=lambda x: x + "aaa",
                ),
            ),
        ]
    )

    assert valuespec.transform_value(("a", "abc")) == ("a", "abc")
    assert valuespec.transform_value(("b", "lala")) == ("b", "lalaaaa")
    assert valuespec.transform_value(("b", "AAA")) == ("b", "AAAaaa")


def test_transform_value_and_json() -> None:
    # before all keys where upper case, then we decided to move to lower case,
    # but want to keep compatibility with old values saved in the config
    valuespec = vs.Transform(
        vs.Dictionary(
            elements=[
                ("key1", vs.TextInput()),
            ]
        ),
        forth=lambda x: {k.lower(): v for k, v in x.items()},
        back=lambda x: x,
    )
    assert valuespec.transform_value({"KEY1": "value1"}) == {"key1": "value1"}

    assert valuespec.value_to_json({"KEY1": "value1"}) == {"key1": "value1"}
    assert valuespec.value_from_json({"key1": "value1"}) == {"key1": "value1"}

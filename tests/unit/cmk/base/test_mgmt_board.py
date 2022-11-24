#!/usr/bin/env python3
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

# TODO: This should be realized as unit tests

from collections.abc import Mapping

import pytest
from pytest import MonkeyPatch

# No stub file
from tests.testlib.base import Scenario

from cmk.utils.type_defs import HostName


@pytest.mark.parametrize(
    "protocol,cred_attribute,credentials",
    [
        ("snmp", "management_snmp_credentials", "HOST"),
        (
            "ipmi",
            "management_ipmi_credentials",
            {
                "username": "USER",
                "password": "PASS",
            },
        ),
    ],
)
def test_mgmt_explicit_settings(
    monkeypatch: MonkeyPatch,
    protocol: str,
    cred_attribute: str,
    credentials: str | Mapping[str, str],
) -> None:
    host = HostName("mgmt-host")

    ts = Scenario()
    ts.add_host(host)
    ts.set_option("ipaddresses", {host: "127.0.0.1"})
    ts.set_option("management_protocol", {host: protocol})
    ts.set_option(cred_attribute, {host: credentials})

    config_cache = ts.apply(monkeypatch)
    assert config_cache.has_management_board(host)
    assert config_cache.management_protocol(host) == protocol

    host_config = config_cache.make_host_config(host)
    assert host_config.management_address == "127.0.0.1"
    assert host_config.management_credentials == credentials


def test_mgmt_explicit_address(monkeypatch: MonkeyPatch) -> None:
    host = HostName("mgmt-host")

    ts = Scenario()
    ts.add_host(host)
    ts.set_option("ipaddresses", {host: "127.0.0.1"})
    ts.set_option("management_protocol", {host: "snmp"})
    ts.set_option("host_attributes", {host: {"management_address": "127.0.0.2"}})

    config_cache = ts.apply(monkeypatch)
    assert config_cache.has_management_board(host)
    assert config_cache.management_protocol(host) == "snmp"

    host_config = config_cache.make_host_config(host)
    assert host_config.management_address == "127.0.0.2"
    assert host_config.management_credentials == "public"


def test_mgmt_disabled(monkeypatch: MonkeyPatch) -> None:
    host = HostName("mgmt-host")

    ts = Scenario()
    ts.add_host(host)
    ts.set_option("ipaddresses", {host: "127.0.0.1"})
    ts.set_option("management_protocol", {host: None})
    ts.set_option("host_attributes", {host: {"management_address": "127.0.0.1"}})
    ts.set_option("management_snmp_credentials", {host: "HOST"})

    config_cache = ts.apply(monkeypatch)
    assert config_cache.has_management_board(host) is False
    assert config_cache.management_protocol(host) is None

    host_config = config_cache.make_host_config(host)
    assert host_config.management_address == "127.0.0.1"
    assert host_config.management_credentials is None


@pytest.mark.parametrize(
    "protocol,cred_attribute,credentials,ruleset_credentials",
    [
        ("snmp", "management_snmp_credentials", "HOST", "RULESET"),
        (
            "ipmi",
            "management_ipmi_credentials",
            {
                "username": "USER",
                "password": "PASS",
            },
            {
                "username": "RULESETUSER",
                "password": "RULESETPASS",
            },
        ),
    ],
)
def test_mgmt_config_ruleset(
    monkeypatch, protocol, cred_attribute, credentials, ruleset_credentials
):
    ts = Scenario()
    ts.set_ruleset(
        "management_board_config",
        [
            {
                "condition": {},
                "options": {},
                "value": (protocol, ruleset_credentials),
            },
        ],
    )

    host = HostName("mgmt-host")
    ts.add_host(host, host_path="/wato/folder1/hosts.mk")
    ts.set_option("ipaddresses", {host: "127.0.0.1"})
    ts.set_option("management_protocol", {host: protocol})

    config_cache = ts.apply(monkeypatch)
    assert config_cache.has_management_board(host)
    assert config_cache.management_protocol(host) == protocol

    host_config = config_cache.make_host_config(host)
    assert host_config.management_address == "127.0.0.1"
    assert host_config.management_credentials == ruleset_credentials


@pytest.mark.parametrize(
    "protocol,cred_attribute,folder_credentials,ruleset_credentials",
    [
        ("snmp", "management_snmp_credentials", "FOLDER", "RULESET"),
        (
            "ipmi",
            "management_ipmi_credentials",
            {
                "username": "FOLDERUSER",
                "password": "FOLDERPASS",
            },
            {
                "username": "RULESETUSER",
                "password": "RULESETPASS",
            },
        ),
    ],
)
def test_mgmt_config_ruleset_order(
    monkeypatch, protocol, cred_attribute, folder_credentials, ruleset_credentials
):
    ts = Scenario()
    ts.set_ruleset(
        "management_board_config",
        [
            {
                "condition": {},
                "options": {},
                "value": ("snmp", "RULESET1"),
            },
            {
                "condition": {},
                "options": {},
                "value": ("snmp", "RULESET2"),
            },
        ],
    )

    host = HostName("mgmt-host")
    ts.add_host(host, host_path="/wato/folder1/hosts.mk")
    ts.set_option("ipaddresses", {host: "127.0.0.1"})
    ts.set_option("management_protocol", {host: "snmp"})

    config_cache = ts.apply(monkeypatch)
    assert config_cache.has_management_board(host)
    assert config_cache.management_protocol(host) == "snmp"

    host_config = config_cache.make_host_config(host)
    assert host_config.management_address == "127.0.0.1"
    assert host_config.management_credentials == "RULESET1"


@pytest.mark.parametrize(
    "protocol,cred_attribute,host_credentials,ruleset_credentials",
    [
        ("snmp", "management_snmp_credentials", "FOLDER", "RULESET"),
        (
            "ipmi",
            "management_ipmi_credentials",
            {
                "username": "FOLDERUSER",
                "password": "FOLDERPASS",
            },
            {
                "username": "RULESETUSER",
                "password": "RULESETPASS",
            },
        ),
    ],
)
def test_mgmt_config_ruleset_overidden_by_explicit_setting(
    monkeypatch, protocol, cred_attribute, host_credentials, ruleset_credentials
):
    ts = Scenario()
    ts.set_ruleset(
        "management_board_config",
        [
            {
                "condition": {},
                "options": {},
                "value": (protocol, ruleset_credentials),
            },
        ],
    )

    host = HostName("mgmt-host")
    ts.add_host(host, host_path="/wato/folder1/hosts.mk")
    ts.set_option("ipaddresses", {host: "127.0.0.1"})
    ts.set_option("management_protocol", {host: protocol})
    ts.set_option(cred_attribute, {host: host_credentials})

    config_cache = ts.apply(monkeypatch)
    assert config_cache.has_management_board(host)
    assert config_cache.management_protocol(host) == protocol

    host_config = config_cache.make_host_config(host)
    assert host_config.management_address == "127.0.0.1"
    assert host_config.management_credentials == host_credentials


@pytest.mark.parametrize(
    "protocol, cred_attribute, credentials",
    [
        ("snmp", "management_snmp_credentials", "HOST"),
        (
            "ipmi",
            "management_ipmi_credentials",
            {
                "username": "USER",
                "password": "PASS",
            },
        ),
    ],
)
@pytest.mark.parametrize(
    "tags, host_attributes, ipaddresses, ipv6addresses, ip_address_result",
    [
        ({}, {}, {}, {}, None),
        # Explicit management_address
        ({}, {"management_address": "127.0.0.1"}, {}, {}, "127.0.0.1"),
        (
            {
                "address_family": "ip-v4-only",
            },
            {"management_address": "127.0.0.1"},
            {},
            {},
            "127.0.0.1",
        ),
        (
            {
                "address_family": "ip-v6-only",
            },
            {"management_address": "127.0.0.1"},
            {},
            {},
            "127.0.0.1",
        ),
        (
            {
                "address_family": "ip-v4v6",
            },
            {"management_address": "127.0.0.1"},
            {},
            {},
            "127.0.0.1",
        ),
        # Explicit management_address + ipaddresses
        ({}, {"management_address": "127.0.0.1"}, {"mgmt-host": "127.0.0.2"}, {}, "127.0.0.1"),
        (
            {
                "address_family": "ip-v4-only",
            },
            {"management_address": "127.0.0.1"},
            {"mgmt-host": "127.0.0.2"},
            {},
            "127.0.0.1",
        ),
        (
            {
                "address_family": "ip-v6-only",
            },
            {"management_address": "127.0.0.1"},
            {"mgmt-host": "127.0.0.2"},
            {},
            "127.0.0.1",
        ),
        (
            {
                "address_family": "ip-v4v6",
            },
            {"management_address": "127.0.0.1"},
            {"mgmt-host": "127.0.0.2"},
            {},
            "127.0.0.1",
        ),
        # Explicit management_address + ipv6addresses
        ({}, {"management_address": "127.0.0.1"}, {}, {"mgmt-host": "::2"}, "127.0.0.1"),
        (
            {
                "address_family": "ip-v4-only",
            },
            {"management_address": "127.0.0.1"},
            {},
            {"mgmt-host": "::2"},
            "127.0.0.1",
        ),
        (
            {
                "address_family": "ip-v6-only",
            },
            {"management_address": "127.0.0.1"},
            {},
            {"mgmt-host": "::2"},
            "127.0.0.1",
        ),
        (
            {
                "address_family": "ip-v4v6",
            },
            {"management_address": "127.0.0.1"},
            {},
            {"mgmt-host": "::2"},
            "127.0.0.1",
        ),
        # ipv4 host
        (
            {
                "address_family": "ip-v4-only",
            },
            {},
            {"mgmt-host": "127.0.0.1"},
            {},
            "127.0.0.1",
        ),
        (
            {
                "address_family": "ip-v4-only",
            },
            {},
            {},
            {"mgmt-host": "::1"},
            None,
        ),
        (
            {
                "address_family": "ip-v4-only",
            },
            {},
            {"mgmt-host": "127.0.0.1"},
            {"mgmt-host": "::1"},
            "127.0.0.1",
        ),
        # ipv6 host
        (
            {
                "address_family": "ip-v6-only",
            },
            {},
            {"mgmt-host": "127.0.0.1"},
            {},
            None,
        ),
        (
            {
                "address_family": "ip-v6-only",
            },
            {},
            {},
            {"mgmt-host": "::1"},
            "::1",
        ),
        (
            {
                "address_family": "ip-v6-only",
            },
            {},
            {"mgmt-host": "127.0.0.1"},
            {"mgmt-host": "::1"},
            "::1",
        ),
        # dual host
        (
            {
                "address_family": "ip-v4v6",
            },
            {},
            {"mgmt-host": "127.0.0.1"},
            {},
            "127.0.0.1",
        ),
        (
            {
                "address_family": "ip-v4v6",
            },
            {},
            {},
            {"mgmt-host": "::1"},
            None,
        ),
        (
            {
                "address_family": "ip-v4v6",
            },
            {},
            {"mgmt-host": "127.0.0.1"},
            {"mgmt-host": "::1"},
            "127.0.0.1",
        ),
    ],
)
def test_mgmt_board_ip_addresses(
    monkeypatch,
    protocol,
    cred_attribute,
    credentials,
    tags,
    host_attributes,
    ipaddresses,
    ipv6addresses,
    ip_address_result,
):
    hostname = HostName("mgmt-host")

    ts = Scenario()
    ts.add_host(hostname, tags=tags)
    ts.set_option("host_attributes", {hostname: host_attributes})
    ts.set_option("ipaddresses", ipaddresses)
    ts.set_option("ipv6addresses", ipv6addresses)
    ts.set_option("management_protocol", {hostname: protocol})
    ts.set_option(cred_attribute, {hostname: credentials})

    config_cache = ts.apply(monkeypatch)
    assert config_cache.has_management_board(hostname)
    assert config_cache.management_protocol(hostname) == protocol

    host_config = config_cache.make_host_config(hostname)
    assert host_config.management_address == ip_address_result
    assert host_config.management_credentials == credentials

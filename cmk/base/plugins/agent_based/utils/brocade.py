#!/usr/bin/env python3
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from typing import Mapping


def brocade_fcport_inventory_this_port(
    admstate: int,
    phystate: int,
    opstate: int,
    settings: Mapping[str, tuple[int, ...]],
) -> bool:
    if admstate not in settings.get("admstates", (1, 3, 4)):
        return False
    if phystate not in settings.get("phystates", (3, 4, 5, 6, 7, 8, 9, 10)):
        return False
    return opstate in settings.get("opstates", (1, 2, 3, 4))


def brocade_fcport_getitem(
    number_of_ports: int,
    index: int,
    portname: str,
    is_isl: bool,
    settings: Mapping[str, bool],
) -> str:

    uses_portname = settings.get("use_portname", True)
    shows_isl = settings.get("show_isl", True)

    itemname = ("%0" + str(len(str(number_of_ports))) + "d") % (index - 1)
    if is_isl and shows_isl:
        itemname += " ISL"
    if portname.strip() and uses_portname:
        itemname += " " + portname.strip()
    return itemname

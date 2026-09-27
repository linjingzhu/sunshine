#!/usr/bin/env python3
"""Availability of the Security Center command, and nothing else.

`docs/SECURITY_CENTER_CONTRACT.md` §14 still holds two owner decisions -- what a
provider `block` verdict may do, and whether origin-only egress is accepted --
and neither is settled here. This module deliberately answers the one question
that does not depend on them: may the command be offered?

Opening the surface was never one of the open questions. The Security Center
WebUI exists at the pinned revision through
`downstream/patches/0005-sunshine-security-webui.patch`; what is undecided is
what it may *do* about a verdict, not whether a user may look at it.

There is no operation here to match the predicate. `security_center.open`
navigates to a Sunshine WebUI surface and commits no Sunshine state, so it
carries no `implementation` and is named in
`scripts/validate_commands.py`'s `NO_SUNSHINE_SIDE_EFFECT` for exactly that
reason.
"""

from __future__ import annotations


def can_open_security_center(*, browser_window_open: bool) -> str | None:
    """`no_browser_window` when there is nowhere to open it, otherwise None.

    `first_party/commands.json` declares one unavailable reason for this
    command, and this returns that token or nothing. The profile is not
    consulted: the Security Center reports on the browser's posture, which a
    window has whether or not a profile has finished loading.
    """

    return None if browser_window_open else "no_browser_window"

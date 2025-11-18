"""Tests for smart permission inference helpers."""

from typing import List

from tengil.core.smart_permissions import (
    SmartPermissionEvent,
    apply_smart_defaults,
    summarize_smart_permission_events,
)


def test_unknown_container_appdata_profile_gets_readwrite_defaults():
    dataset = {
        "profile": "appdata",
        "containers": [
            {
                "name": "my-nodejs-api",
                "mount": "/app",
            }
        ],
        "shares": {
            "smb": {
                "name": "WebServices",
            }
        },
    }

    events: List[SmartPermissionEvent] = []
    apply_smart_defaults(dataset, "tank/webservices", events=events)

    container = dataset["containers"][0]
    smb_share = dataset["shares"]["smb"]

    assert container["readonly"] is False
    assert smb_share["writable"] == "yes"
    assert smb_share["read only"] == "no"
    assert events == []


def test_fuzzy_match_emits_event_for_known_pattern():
    dataset = {
        "profile": "media",
        "containers": [
            {
                "name": "jellyfin-nightly",
                "mount": "/media",
            }
        ],
        "shares": {},
    }

    events: List[SmartPermissionEvent] = []
    apply_smart_defaults(dataset, "tank/media", events=events)

    container = dataset["containers"][0]

    assert container["readonly"] is True
    assert events
    event = events[0]
    assert event.type == "fuzzy-match"
    assert event.container == "jellyfin-nightly"
    assert event.pattern == "jellyfin"
    assert event.access == "readonly"
    assert event.dataset == "tank/media"
    assert event.exact is False


def test_summarize_events_produces_human_message():
    events = [
        SmartPermissionEvent(
            type="fuzzy-match",
            container="jellyfin-nightly",
            pattern="jellyfin",
            access="readonly",
            dataset="tank/media",
            exact=False,
        )
    ]

    summaries = summarize_smart_permission_events(events)

    assert summaries
    assert "jellyfin-nightly" in summaries[0]
    assert "readonly" in summaries[0]

from fastapi.testclient import TestClient

from lichord.models import Stream, Track
from lichord.providers import ProviderHub, ProviderSearchError
from lichord.server import app


class FakeProvider:
    def __init__(self, name, tracks):
        self.name, self.tracks = name, tracks

    def search(self, query, limit, region):
        return self.tracks[:limit]

    def stream(self, track_id, quality):
        return Stream("https://cdn.example/audio.m4a", "m4a", "aac", 192, 44100)


def test_manifest_matches_addon_contract():
    data = TestClient(app).get("/manifest.json").json()
    assert data["id"] == "lichord-multicatalogue"
    assert {"search", "stream"}.issubset(data["resources"])
    assert data["allowDownloads"] == 0


def test_track_serialization_uses_addon_fields():
    row = Track("ytm:abc", "Track", "Artist", "Album", 183, "https://img/a.jpg").addon_json()
    assert row["id"] == "ytm:abc"
    assert row["duration"] == 183.0
    assert row["artworkURL"] == "https://img/a.jpg"
    assert row["audioQuality"] == "HIGH"


def test_stream_serialization_reports_observed_codec():
    row = Stream("https://cdn.example/a", "m4a", "aac", 192, 44100).addon_json()
    assert row["codec"] == "aac"
    assert row["quality"] == "HIGH"
    assert "bitDepth" not in row


def test_health_endpoint():
    assert TestClient(app).get("/health").json()["status"] == "ok"


def test_provider_hub_deduplicates_and_isolates_failures():
    first = FakeProvider("first", [Track("ytm:1", "Song", "Artist"), Track("ytm:2", "Other", "Artist")])
    second = FakeProvider("second", [Track("sc:1", " song ", " ARTIST "), Track("sc:2", "Third", "Artist")])
    hub = ProviderHub({"first": first, "second": second})
    results = hub.search("query", 10, "IN", "all")
    assert len(results) == 3
    assert {t.title.strip() for t in results} == {"Song", "Other", "Third"}



class BrokenProvider(FakeProvider):
    def search(self, query, limit, region):
        raise RuntimeError("provider unavailable")


def test_provider_hub_reports_total_search_failure():
    hub = ProviderHub({"broken": BrokenProvider("broken", [])})
    try:
        hub.search("query", 10, "IN", "all")
    except ProviderSearchError:
        pass
    else:
        raise AssertionError("all-provider failure should not look like an empty result")


def test_provider_hub_preserves_results_when_one_provider_fails():
    good = FakeProvider("good", [Track("ytm:1", "Song", "Artist")])
    broken = BrokenProvider("broken", [])
    hub = ProviderHub({"good": good, "broken": broken})
    results = hub.search("query", 10, "IN", "all")
    assert [track.id for track in results] == ["ytm:1"]

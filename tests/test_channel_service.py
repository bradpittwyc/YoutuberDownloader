import threading
from pathlib import Path
import pytest
from channel_service import source_url, scan, Entry, Settings, History, run_queue, Cancelled


@pytest.mark.parametrize("value,category,tail", [
    ("https://www.youtube.com/@hubermanlab", "videos", "/@hubermanlab/videos"),
    ("youtube.com/@hubermanlab/videos", "shorts", "/@hubermanlab/shorts"),
    ("https://youtube.com/channel/UC123", "playlists", "/channel/UC123/playlists"),
    ("https://youtu.be/abcdefghijk", "videos", "/watch?v=abcdefghijk"),
    ("https://youtube.com/shorts/abcdefghijk", "shorts", "/watch?v=abcdefghijk"),
    ("https://youtube.com/watch?v=abcdefghijk&list=PL123", "videos", "/watch?v=abcdefghijk"),
    ("https://youtube.com/playlist?list=PL123", "videos", "/playlist?list=PL123"),
])
def test_routes(value, category, tail):
    assert source_url(value, category) == "https://www.youtube.com" + tail


@pytest.mark.parametrize("value", ["", "https://youtube.com.evil.org/@abc", "https://evil.org", "file:///etc/passwd",
    "https://youtube.com@evil.org/@abc", "http://youtube.com/@abc", "https://youtube.com/watch?v=bad",
    "https://youtube.com/@abc/podcasts", "https://youtube.com/@abc/videos/extra"])
def test_reject_invalid(value):
    with pytest.raises(ValueError):
        source_url(value)


class FakeYDL:
    def __init__(self, opts, behavior):
        self.opts = opts
        self.behavior = behavior
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def extract_info(self, url, download):
        return self.behavior(self.opts, url, download)
    def prepare_filename(self, info):
        return info["filepath"]


def test_scan_deduplicates_and_never_downloads():
    def behavior(opts, url, download):
        assert not download
        assert opts["skip_download"]
        assert opts["playlistend"] == 3
        return {"title": "频道", "entries": iter([None, {"id": "abcdefghijk", "title": "one"}, {"id": "abcdefghijk"}])}
    title, entries = scan("youtube.com/@abc", limit=3, ydl_factory=lambda opts: FakeYDL(opts, behavior))
    assert title == "频道" and len(entries) == 1
    assert entries[0].kind == "video"


def test_playlist_catalog():
    _, entries = scan("youtube.com/@abc", "playlists", ydl_factory=lambda opts:
                      FakeYDL(opts, lambda *a: {"entries": [{"id": "PL123", "title": "series"}]}))
    assert entries == [Entry("PL123", "series", "https://www.youtube.com/playlist?list=PL123", "playlist")]


def test_cancel_before_scan():
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(Cancelled):
        scan("youtube.com/@abc", cancel=cancel)


def test_history_checks_file_and_rejects_escape(tmp_path):
    h = History(tmp_path)
    file = tmp_path / "a.mp4"
    file.write_bytes(b"media")
    h.record("a", file)
    assert History(tmp_path).has("a")
    file.unlink()
    assert not h.has("a")
    h.data["a"] = "../outside.mp4"
    assert not h.has("a")


def test_broken_history_is_not_silently_overwritten(tmp_path):
    (tmp_path / ".youtube-history.json").write_text("broken")
    with pytest.raises(ValueError):
        History(tmp_path)


def make_entries():
    return [Entry(key, key, "https://www.youtube.com/watch?v=" + key) for key in ["abcdefghijk", "lmnopqrstuv"]]


def test_empty_subtitle_result_is_failure(tmp_path):
    entry = make_entries()[0]
    media = tmp_path / 'video.mp4'
    media.write_bytes(b'media')
    History(tmp_path).record(entry.id, media)
    events = []
    run_queue([entry], Settings(str(tmp_path)), lambda *e: events.append(e),
              ydl_factory=lambda opts: FakeYDL(opts, lambda *a: None))
    assert '字幕失败' in str(events)
    assert History(tmp_path).has(entry.id)


def test_progress_resets_for_each_entry(tmp_path):
    events = []
    run_queue(make_entries(), Settings(str(tmp_path)), lambda *e: events.append(e),
              ydl_factory=lambda opts: FakeYDL(opts, lambda *a: None))
    assert events.count(('progress', 0)) == 2


def test_failure_continues_and_repeat_only_downloads_subtitles(tmp_path):
    calls, events = [], []
    def behavior(opts, url, download):
        key = url.split("=")[-1]
        subtitle = opts.get("skip_download", False)
        calls.append((key, subtitle))
        if key == "abcdefghijk":
            raise RuntimeError("unavailable")
        if subtitle:
            return {"requested_subtitles": {"en": {}}}
        file = tmp_path / key / (key + ".mp4")
        file.parent.mkdir(exist_ok=True)
        file.write_bytes(b"video")
        return {"filepath": str(file)}
    provider = lambda opts: FakeYDL(opts, behavior)
    entries = make_entries()
    run_queue(entries, Settings(str(tmp_path)), lambda *e: events.append(e), ydl_factory=provider)
    assert calls == [(entries[0].id, False), (entries[1].id, False), (entries[1].id, True)]
    assert "失败" in str(events)
    calls.clear()
    run_queue([entries[1], entries[1]], Settings(str(tmp_path)), lambda *a: None, ydl_factory=provider)
    assert calls == [(entries[1].id, True)]


def test_subtitle_failure_keeps_media_history(tmp_path):
    entry = make_entries()[0]
    def behavior(opts, url, download):
        if opts.get("skip_download"):
            raise RuntimeError("subtitle HTTP 429")
        file = tmp_path / "video.mp4"
        file.write_bytes(b"media")
        return {"filepath": str(file)}
    events = []
    run_queue([entry], Settings(str(tmp_path)), lambda *e: events.append(e), ydl_factory=lambda opts: FakeYDL(opts, behavior))
    assert History(tmp_path).has(entry.id)
    assert "字幕失败" in str(events)


def test_cancel_stops_remaining_queue(tmp_path):
    cancel, calls = threading.Event(), []
    def behavior(opts, url, download):
        calls.append(url)
        cancel.set()
        opts["progress_hooks"][0]({})
    run_queue(make_entries(), Settings(str(tmp_path)), lambda *a: None, cancel, lambda opts: FakeYDL(opts, behavior))
    assert len(calls) == 1


def test_missing_media_not_recorded_as_success(tmp_path):
    entry = make_entries()[0]
    events = []
    run_queue([entry], Settings(str(tmp_path), subtitles=False), lambda *e: events.append(e),
              ydl_factory=lambda opts: FakeYDL(opts, lambda *a: {"filepath": str(tmp_path / "missing.mp4")}))
    assert not History(tmp_path).has(entry.id)
    assert "失败" in str(events)

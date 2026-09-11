"""Channel discovery and sequential download jobs, independent of the UI."""
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode
import json
import re
import threading

from yt_downloader import find_ffmpeg_bin_dir, find_deno_exe


class Cancelled(Exception):
    pass


def source_url(value, category="videos"):
    """Canonicalize only supported YouTube sources, never arbitrary hosts."""
    value = value.strip()
    if "://" not in value:
        value = "https://" + value
    p = urlparse(value)
    if p.scheme != "https" or p.username or p.password or p.port:
        raise ValueError("请输入 HTTPS YouTube 链接")
    if p.hostname not in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}:
        raise ValueError("只支持 YouTube 链接")
    if category not in {"videos", "shorts", "playlists"}:
        raise ValueError("不支持此栏目")
    q = parse_qs(p.query)
    parts = p.path.strip("/").split("/")
    video_id = None
    if p.hostname == "youtu.be":
        video_id = parts[0] if len(parts) == 1 else ""
    elif p.path == "/watch":
        video_id = q.get("v", [""])[0]
    elif len(parts) == 2 and parts[0] == "shorts":
        video_id = parts[1]
    if video_id is not None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            raise ValueError("视频链接无效")
        return "https://www.youtube.com/watch?" + urlencode({"v": video_id})
    if p.path == "/playlist" and q.get("list"):
        playlist = q["list"][0]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", playlist):
            raise ValueError("播放列表链接无效")
        return "https://www.youtube.com/playlist?" + urlencode({"list": playlist})
    if parts[0].startswith("@") and len(parts[0]) > 1:
        root, tail = parts[:1], parts[1:]
    elif len(parts) >= 2 and parts[0] in {"channel", "c", "user"} and parts[1]:
        root, tail = parts[:2], parts[2:]
    else:
        raise ValueError("请输入频道、视频或播放列表链接")
    if tail and (len(tail) != 1 or tail[0] not in {"videos", "shorts", "playlists", "featured"}):
        raise ValueError("此栏目暂不支持；请选择 Videos、Shorts 或播放列表")
    return "https://www.youtube.com/" + "/".join(root + [category])


def runtime_options():
    opts = {"quiet": True, "noprogress": True, "socket_timeout": 15,
            "retries": 2, "fragment_retries": 2, "extractor_retries": 1}
    if ffmpeg := find_ffmpeg_bin_dir():
        opts["ffmpeg_location"] = ffmpeg
    if deno := find_deno_exe():
        opts["js_runtimes"] = {"deno": {"path": deno}}
        opts["remote_components"] = ["ejs:github"]
    return opts


def factory(opts):
    import yt_dlp
    return yt_dlp.YoutubeDL(opts)


@dataclass(frozen=True)
class Entry:
    id: str
    title: str
    url: str
    kind: str = "video"


def scan(value, category="videos", limit=0, cancel=None, ydl_factory=factory):
    cancel = cancel or threading.Event()
    if cancel.is_set():
        raise Cancelled()
    if limit < 0:
        raise ValueError("扫描数量不能为负数")
    url = source_url(value, category)
    opts = runtime_options()
    opts.update(extract_flat="in_playlist", skip_download=True, lazy_playlist=True)
    if limit:
        opts["playlistend"] = limit
    with ydl_factory(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if not info:
            raise ValueError("没有读取到内容")
        rows, seen = [], set()
        is_catalog = url.endswith("/playlists")
        for item in info.get("entries", [info]):
            if cancel.is_set():
                raise Cancelled()
            if not item or not item.get("id"):
                continue
            key = item["id"]
            if key in seen:
                continue
            seen.add(key)
            if is_catalog:
                target = "https://www.youtube.com/playlist?" + urlencode({"list": key})
            else:
                if not re.fullmatch(r"[A-Za-z0-9_-]{11}", key):
                    continue
                target = "https://www.youtube.com/watch?" + urlencode({"v": key})
            rows.append(Entry(key, item.get("title") or key, target,
                              "playlist" if is_catalog else "video"))
        return info.get("title", "YouTube"), rows


@dataclass(frozen=True)
class Settings:
    output: str
    height: int = 1080
    subtitles: bool = True
    auto_subtitles: bool = True
    languages: tuple = ("en.*", "zh.*")


class History:
    def __init__(self, output):
        self.root = Path(output).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / ".youtube-history.json"
        self.data = {}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(self.data, dict):
                    raise ValueError("not an object")
            except (ValueError, OSError) as exc:
                raise ValueError("下载历史无法读取，请备份后修复 .youtube-history.json") from exc

    def has(self, video_id):
        relative = self.data.get(video_id)
        if not isinstance(relative, str):
            return False
        p = (self.root / relative).resolve()
        return p.is_relative_to(self.root) and p.is_file()

    def record(self, video_id, filepath):
        p = Path(filepath).resolve()
        if p.is_file() and p.is_relative_to(self.root):
            self.data[video_id] = str(p.relative_to(self.root))
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(self.path)


def run_queue(entries, settings, emit, cancel=None, ydl_factory=factory):
    """One active worker per UI. Persist only verified media; fetch subtitles separately."""
    cancel = cancel or threading.Event()
    history = History(settings.output)
    unique = list({e.id: e for e in entries}.values())
    for index, entry in enumerate(unique, 1):
        if cancel.is_set():
            break
        emit("status", (entry.id, f"处理中 {index}/{len(unique)}"))
        def hook(data):
            if cancel.is_set():
                raise Cancelled()
            total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
            if total:
                emit("progress", min(1, data.get("downloaded_bytes", 0) / total))
        try:
            opts = runtime_options()
            opts.update(noplaylist=True, continuedl=True, nopart=False,
                        outtmpl=str(history.root / "%(id)s" / "%(id)s.%(ext)s"),
                        progress_hooks=[hook], postprocessor_hooks=[hook],
                        format=(f"bestvideo*[height<={settings.height}]+bestaudio/"
                                f"best[height<={settings.height}]" if settings.height else
                                "bestvideo*+bestaudio/best"), merge_output_format="mp4/mkv")
            existed = history.has(entry.id)
            if not existed:
                with ydl_factory(opts) as ydl:
                    info = ydl.extract_info(entry.url, download=True)
                    if not info:
                        raise RuntimeError("没有下载结果")
                    path = info.get("filepath") or ydl.prepare_filename(info)
                    if not Path(path).is_file():
                        candidates = [p for p in (history.root / entry.id).glob(entry.id + ".*")
                                      if p.suffix in {".mp4", ".mkv", ".webm"}]
                        path = candidates[0] if len(candidates) == 1 else path
                    history.record(entry.id, path)
                    if not history.has(entry.id):
                        raise RuntimeError("下载返回成功，但未找到合并后的媒体文件")
            if cancel.is_set():
                raise Cancelled()
            subtitle_status = ""
            if settings.subtitles:
                # Separate pass: a subtitle error must not erase successful media history.
                opts.update(skip_download=True, writesubtitles=True,
                            writeautomaticsub=settings.auto_subtitles,
                            subtitleslangs=list(settings.languages), subtitlesformat="srt/best",
                            postprocessors=[{"key": "FFmpegSubtitlesConvertor", "format": "srt"}])
                with ydl_factory(opts) as ydl:
                    sub_info = ydl.extract_info(entry.url, download=True)
                    subtitle_status = "；字幕已处理" if (sub_info or {}).get("requested_subtitles") else "；无所选语言字幕"
            emit("status", (entry.id, ("视频已存在" if existed else "完成") + subtitle_status))
        except Exception as exc:
            if isinstance(exc, Cancelled) or cancel.is_set():
                emit("status", (entry.id, "已取消，可重新开始续传"))
                break
            prefix = "视频已保存；字幕失败" if history.has(entry.id) and settings.subtitles else "失败"
            emit("status", (entry.id, f"{prefix}：{exc}"))
    emit("finished", "已取消；未完成项可重新开始" if cancel.is_set() else "队列处理结束，请查看每项结果")

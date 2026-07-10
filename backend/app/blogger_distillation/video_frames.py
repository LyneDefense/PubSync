"""视频抽帧 + 镜头切分(video_profile 的 L1/L2 原料)。

设计(见 docs/视频笔记档案化_方案设计.md 第五节):
- **节奏交给 CPU**:ffmpeg 场景切换滤镜(`select=gt(scene,T),showinfo`)给出镜头边界 → 镜头数/时长/cuts·min(准,不花 VLM 钱)。
- **风格交给少量帧**:每个镜头取 1 张代表帧(镜头中点),自适应、封顶 `video_shot_frame_cap`;缩到 512px 省 VLM token。
- 不用均匀抽帧(3 分钟快剪太稀、测不出节奏),也不直接喂视频模式(按 ~1fps ~180 帧、贵且 LLM 数不准镜头)。

纯解析(parse_scene_times / compute_pacing / pick_frame_timestamps)可单测;IO(ffmpeg)薄封装,失败返回 None 让上层降级。
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from app.blogger_distillation.asr import ASRError, download_video, probe_duration
from app.config import Settings

logger = logging.getLogger(__name__)

_PTS_RE = re.compile(r"pts_time:(\d+(?:\.\d+)?)")


@dataclass
class MotionExtract:
    """一条视频的 L1(节奏)+ 代表帧;帧给 L2 的 VLM 描述用。"""

    duration_s: float | None
    pacing: dict  # {shot_count, avg_shot_s, cuts_per_min, pace}
    frames: list[bytes] = field(default_factory=list)  # 代表帧 JPEG 字节,≤ cap


# —— 纯函数(可单测)—— #

def parse_scene_times(ffmpeg_stderr: str) -> list[float]:
    """从 ffmpeg `select=gt(scene,T),showinfo` 的 stderr 里抽出被选中(场景切换)帧的 pts_time。升序去重。"""
    times = sorted({float(m) for m in _PTS_RE.findall(ffmpeg_stderr or "")})
    return times


def compute_pacing(scene_times: list[float], duration: float | None, *, fast_cpm: float, slow_cpm: float) -> dict:
    """镜头边界 + 时长 → 节奏指标。scene_times 是切换点,镜头数 = 切换数 + 1。"""
    shot_count = len(scene_times) + 1
    out: dict = {"shot_count": shot_count}
    if duration and duration > 0:
        avg = duration / shot_count
        cpm = shot_count / (duration / 60.0)
        out["avg_shot_s"] = round(avg, 2)
        out["cuts_per_min"] = round(cpm, 1)
        out["pace"] = "fast" if cpm >= fast_cpm else "slow" if cpm <= slow_cpm else "medium"
    return out


def pick_frame_timestamps(scene_times: list[float], duration: float | None, cap: int) -> list[float]:
    """每个镜头取中点作代表帧;镜头数 > cap 时按均匀间隔降采样到 cap。"""
    if not duration or duration <= 0:
        return []
    bounds = [0.0, *[t for t in scene_times if 0 < t < duration], float(duration)]
    mids = [(bounds[i] + bounds[i + 1]) / 2 for i in range(len(bounds) - 1)]
    if len(mids) <= max(1, cap):
        return mids
    step = len(mids) / cap
    return [mids[min(len(mids) - 1, int(i * step))] for i in range(cap)]


# —— IO(ffmpeg)—— #

def _detect_scene_times(video_path: Path, threshold: float) -> list[float]:
    proc = subprocess.run(
        ["ffmpeg", "-nostdin", "-i", str(video_path), "-filter:v", f"select='gt(scene,{threshold})',showinfo", "-f", "null", "-"],
        capture_output=True, text=True, errors="replace", timeout=180,
    )
    return parse_scene_times(proc.stderr)


def _extract_frame(video_path: Path, timestamp: float, out_path: Path) -> bool:
    """在 timestamp 处取 1 帧,缩到宽 512(-ss 放 -i 前=快速 seek)。成功且文件非空返回 True。"""
    subprocess.run(
        ["ffmpeg", "-nostdin", "-y", "-ss", f"{timestamp:.2f}", "-i", str(video_path),
         "-frames:v", "1", "-vf", "scale=512:-2", "-q:v", "4", str(out_path)],
        capture_output=True, timeout=60,
    )
    return out_path.exists() and out_path.stat().st_size > 0


def analyze_video_motion(settings: Settings, video_url: str, *, video_path: Path | None = None) -> MotionExtract | None:
    """下载 → 镜头切分(节奏)→ 代表帧(字节)。任何失败返回 None,上层降级(不掀翻采集)。

    video_path 给了(ASR 已下过的共享文件)则跳过下载、直接用;否则自行下载 video_url。
    """
    if not shutil.which("ffmpeg"):
        logger.warning("未装 ffmpeg,跳过视频抽帧")
        return None
    if video_path is None and not video_url:
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="pubsync-motion-") as tmp_dir:
            tmp = Path(tmp_dir)
            source = video_path
            if source is None:  # 未共享则自行下载(向后兼容)
                source = tmp / "video.mp4"
                try:
                    download_video(settings, video_url, source)
                except ASRError as exc:
                    logger.info("视频抽帧下载失败,降级:%s", exc)
                    return None
            duration = probe_duration(source)
            scene_times = _detect_scene_times(source, settings.video_scene_threshold)
            pacing = compute_pacing(scene_times, duration, fast_cpm=settings.video_pace_fast_cpm, slow_cpm=settings.video_pace_slow_cpm)
            frames: list[bytes] = []
            for i, ts in enumerate(pick_frame_timestamps(scene_times, duration, settings.video_shot_frame_cap)):
                frame_path = tmp / f"f{i:03d}.jpg"
                if _extract_frame(source, ts, frame_path):
                    frames.append(frame_path.read_bytes())
            return MotionExtract(duration_s=duration, pacing=pacing, frames=frames)
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("视频抽帧失败,降级:%s", exc)
        return None

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from app.config import Settings


logger = logging.getLogger(__name__)


class ASRError(RuntimeError):
    pass


@dataclass
class ASRResult:
    text: str
    task_id: str = ""
    duration_seconds: float | None = None
    provider: str = "tencent_rec_task"


class ASRProvider:
    def transcribe_video_url(self, video_url: str, *, source_id: str = "") -> ASRResult:
        raise NotImplementedError


class DisabledASRProvider(ASRProvider):
    def transcribe_video_url(self, video_url: str, *, source_id: str = "") -> ASRResult:
        raise ASRError("ASR 未开启")


class TencentRecTaskASRProvider(ASRProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        missing = [
            name
            for name, value in {
                "TENCENT_ASR_SECRET_ID": settings.tencent_asr_secret_id,
                "TENCENT_ASR_SECRET_KEY": settings.tencent_asr_secret_key,
                "TENCENT_COS_SECRET_ID": settings.tencent_cos_secret_id,
                "TENCENT_COS_SECRET_KEY": settings.tencent_cos_secret_key,
                "TENCENT_COS_BUCKET": settings.tencent_cos_bucket,
            }.items()
            if not value
        ]
        if missing:
            raise ASRError(f"腾讯云 ASR/COS 配置不完整：{', '.join(missing)}")
        if not shutil.which("ffmpeg"):
            raise ASRError("服务器未安装 ffmpeg，无法从视频提取音频")

    def transcribe_video_url(self, video_url: str, *, source_id: str = "") -> ASRResult:
        started_at = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="pubsync-asr-") as tmp_dir:
            tmp_path = Path(tmp_dir)
            video_path = tmp_path / "source-video"
            audio_path = tmp_path / "audio.mp3"
            self.download_video(video_url, video_path)
            streams = probe_media_streams(video_path)
            if "audio" not in streams["types"]:
                codecs = ", ".join(streams["codecs"][:6]) or "unknown"
                raise ASRError(f"下载内容不包含音频流，可能是图片封面或无声视频：codecs={codecs}")
            duration = probe_duration(video_path)
            if duration and duration > self.settings.asr_max_duration_seconds:
                raise ASRError(f"视频时长 {int(duration)} 秒，超过 ASR 上限 {self.settings.asr_max_duration_seconds} 秒")
            extract_audio(video_path, audio_path)
            cos_key = self.upload_audio(audio_path, source_id=source_id)
            audio_url = self.get_presigned_url(cos_key)
            task_id = self.create_rec_task(audio_url)
            text = self.wait_result(task_id)
            elapsed = round(time.perf_counter() - started_at, 2)
            logger.info("腾讯云长音频识别完成：source=%s，task_id=%s，耗时=%ss，文本长度=%s", source_id, task_id, elapsed, len(text))
            return ASRResult(text=text, task_id=task_id, duration_seconds=duration, provider="tencent_rec_task")

    def download_video(self, video_url: str, video_path: Path) -> None:
        """下载视频:优先 https(快约 3 倍),失败则回退 http 重试一次;带总时长+体积硬上限。"""
        max_seconds = self.settings.asr_download_max_seconds
        max_bytes = max(self.settings.asr_download_max_mb, 1) * (1 << 20)
        https_url = video_url.replace("http://", "https://", 1) if video_url.startswith("http://") else video_url
        try:
            download_file(https_url, video_path, max_seconds=max_seconds, max_bytes=max_bytes)
            return
        except httpx.HTTPError as exc:
            http_url = "http://" + https_url[len("https://") :] if https_url.startswith("https://") else https_url
            if http_url == https_url:
                raise ASRError(f"视频下载失败：{exc}") from exc
            logger.info("https 下载失败,回退 http 重试：%s", exc)
            try:
                download_file(http_url, video_path, max_seconds=max_seconds, max_bytes=max_bytes)
            except httpx.HTTPError as exc2:
                raise ASRError(f"视频下载失败(https/http 均失败)：{exc2}") from exc2

    def upload_audio(self, audio_path: Path, *, source_id: str = "") -> str:
        from qcloud_cos import CosConfig, CosS3Client

        config = CosConfig(
            Region=self.settings.tencent_cos_region,
            SecretId=self.settings.tencent_cos_secret_id,
            SecretKey=self.settings.tencent_cos_secret_key,
            Timeout=60,  # 连接/读取超时,避免上传卡死把整个采集任务挂住
        )
        client = CosS3Client(config)
        safe_source = source_id or str(uuid4())
        prefix = self.settings.tencent_cos_prefix.strip("/")
        cos_key = f"{prefix}/{safe_source}-{uuid4().hex}.mp3"
        client.upload_file(
            Bucket=self.settings.tencent_cos_bucket,
            LocalFilePath=str(audio_path),
            Key=cos_key,
            PartSize=5,
            MAXThread=3,
        )
        return cos_key

    def get_presigned_url(self, cos_key: str) -> str:
        from qcloud_cos import CosConfig, CosS3Client

        config = CosConfig(
            Region=self.settings.tencent_cos_region,
            SecretId=self.settings.tencent_cos_secret_id,
            SecretKey=self.settings.tencent_cos_secret_key,
            Timeout=60,  # 连接/读取超时,避免上传卡死把整个采集任务挂住
        )
        client = CosS3Client(config)
        return client.get_presigned_url(
            Method="GET",
            Bucket=self.settings.tencent_cos_bucket,
            Key=cos_key,
            Expired=max(self.settings.asr_timeout_seconds + 1800, 3600),
        )

    def create_rec_task(self, audio_url: str) -> str:
        from tencentcloud.asr.v20190614 import asr_client, models
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile

        http_profile = HttpProfile(endpoint="asr.tencentcloudapi.com")
        http_profile.reqTimeout = 60  # 单次 API 调用超时,避免无限挂
        client_profile = ClientProfile(httpProfile=http_profile)
        cred = credential.Credential(self.settings.tencent_asr_secret_id, self.settings.tencent_asr_secret_key)
        client = asr_client.AsrClient(cred, self.settings.tencent_asr_region, client_profile)
        request = models.CreateRecTaskRequest()
        request.from_json_string(
            json.dumps(
                {
                    "EngineModelType": self.settings.tencent_asr_engine_model_type,
                    "ChannelNum": 1,
                    "ResTextFormat": self.settings.tencent_asr_res_text_format,
                    "SourceType": 0,
                    "Url": audio_url,
                }
            )
        )
        response = client.CreateRecTask(request)
        payload = json.loads(response.to_json_string())
        task_id = str((payload.get("Data") or {}).get("TaskId") or payload.get("TaskId") or "")
        if not task_id:
            raise ASRError(f"腾讯云 ASR 未返回 TaskId：{payload}")
        return task_id

    def wait_result(self, task_id: str) -> str:
        from tencentcloud.asr.v20190614 import asr_client, models
        from tencentcloud.common import credential
        from tencentcloud.common.profile.client_profile import ClientProfile
        from tencentcloud.common.profile.http_profile import HttpProfile

        http_profile = HttpProfile(endpoint="asr.tencentcloudapi.com")
        http_profile.reqTimeout = 60  # 单次 API 调用超时,避免无限挂
        client_profile = ClientProfile(httpProfile=http_profile)
        cred = credential.Credential(self.settings.tencent_asr_secret_id, self.settings.tencent_asr_secret_key)
        client = asr_client.AsrClient(cred, self.settings.tencent_asr_region, client_profile)
        deadline = time.monotonic() + self.settings.asr_timeout_seconds
        last_payload: dict[str, Any] = {}
        while time.monotonic() < deadline:
            request = models.DescribeTaskStatusRequest()
            request.from_json_string(json.dumps({"TaskId": int(task_id) if task_id.isdigit() else task_id}))
            response = client.DescribeTaskStatus(request)
            payload = json.loads(response.to_json_string())
            last_payload = payload
            data = payload.get("Data") or {}
            status = str(data.get("StatusStr") or data.get("Status") or "").lower()
            result = (data.get("Result") or "").strip()
            error_msg = data.get("ErrorMsg") or data.get("ErrorMessage") or ""
            if result:
                return result
            if status in {"failed", "failure", "error", "3"}:
                raise ASRError(f"腾讯云 ASR 任务失败：{error_msg or payload}")
            time.sleep(max(self.settings.asr_poll_interval_seconds, 3))
        raise ASRError(f"腾讯云 ASR 任务超时：task_id={task_id}，最后状态={last_payload}")


def build_asr_provider(settings: Settings) -> ASRProvider:
    if not settings.asr_enabled:
        return DisabledASRProvider()
    if settings.asr_provider == "tencent_rec_task":
        return TencentRecTaskASRProvider(settings)
    raise ASRError(f"不支持的 ASR_PROVIDER：{settings.asr_provider}")


def download_file(url: str, output_path: Path, *, max_seconds: int = 120, max_bytes: int = 0) -> None:
    """流式下载,带总墙钟时长 + 文件体积硬上限。超限抛 ASRError(上层据此降级)。

    httpx 的 timeout 是「单块读取」超时,对慢速涓流不生效;必须额外用总时长 deadline 兜底。
    """
    deadline = time.monotonic() + max_seconds if max_seconds and max_seconds > 0 else None
    timeout = httpx.Timeout(connect=15.0, read=30.0, write=30.0, pool=15.0)
    total = 0
    with httpx.stream("GET", url, timeout=timeout, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 PubSync/1.0"}) as response:
        response.raise_for_status()
        with output_path.open("wb") as file:
            for chunk in response.iter_bytes():
                if not chunk:
                    continue
                file.write(chunk)
                total += len(chunk)
                if max_bytes and total > max_bytes:
                    raise ASRError(f"视频体积超过上限 {max_bytes // (1 << 20)}MB,跳过转写并降级分析")
                if deadline and time.monotonic() > deadline:
                    raise ASRError(f"视频下载超过 {max_seconds}s 仍未完成,跳过转写并降级分析")


def probe_duration(input_path: Path) -> float | None:
    if not shutil.which("ffprobe"):
        return None
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(input_path),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return None
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def probe_media_streams(input_path: Path) -> dict[str, list[str]]:
    if not shutil.which("ffprobe"):
        return {"types": [], "codecs": []}
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type,codec_name",
                "-of",
                "json",
                str(input_path),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {"types": [], "codecs": []}
    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return {"types": [], "codecs": []}
    streams = payload.get("streams")
    if not isinstance(streams, list):
        return {"types": [], "codecs": []}
    types = []
    codecs = []
    for stream in streams:
        if not isinstance(stream, dict):
            continue
        codec_type = stream.get("codec_type")
        codec_name = stream.get("codec_name")
        if isinstance(codec_type, str) and codec_type:
            types.append(codec_type)
        if isinstance(codec_name, str) and codec_name:
            codecs.append(codec_name)
    return {"types": types, "codecs": codecs}


def extract_audio(video_path: Path, audio_path: Path) -> None:
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", str(audio_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
        )
    except subprocess.TimeoutExpired as exc:
        raise ASRError("ffmpeg 提取音频超时(180s)") from exc
    if result.returncode != 0 or not audio_path.exists():
        raise ASRError(f"ffmpeg 提取音频失败：{result.stderr[-800:]}")

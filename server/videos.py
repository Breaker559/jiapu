"""Validate browser-playable video containers and create a local poster image."""
import io
from pathlib import Path

import av
from fastapi import HTTPException

IMAGE_LIMIT = 12 * 1024**2
VIDEO_LIMIT = 64 * 1024**2
FAMILY_MEDIA_LIMIT = 128 * 1024**2


def looks_like_video(raw: bytes, filename: str = '', content_type: str = '') -> bool:
    return raw[4:8] == b'ftyp' or raw[:4] == b'\x1aE\xdf\xa3' or content_type.startswith('video/') or Path(filename).suffix.lower() in {'.mp4', '.webm', '.mov', '.avi', '.mkv', '.m4v'}


def make_video(raw: bytes, path: Path) -> dict:
    if len(raw) > VIDEO_LIMIT:
        raise HTTPException(413, '单个视频最大 64 MB')
    if raw[4:8] == b'ftyp':
        container_format, mime, codecs, audio_codecs = 'mov', 'video/mp4', {'h264'}, {'aac', 'mp3'}
    elif raw[:4] == b'\x1aE\xdf\xa3':
        container_format, mime, codecs, audio_codecs = 'matroska', 'video/webm', {'vp8', 'vp9', 'av1'}, {'opus', 'vorbis'}
    else:
        raise HTTPException(422, '请上传 MP4（H.264）或 WebM 视频')
    try:
        with av.open(io.BytesIO(raw), format=container_format, options={'protocol_whitelist': 'file,pipe'}) as container:
            if not container.streams.video:
                raise HTTPException(422, '文件中没有可播放的视频画面')
            stream = container.streams.video[0]
            if stream.codec_context.name not in codecs or any(audio.codec_context.name not in audio_codecs for audio in container.streams.audio):
                raise HTTPException(422, '视频编码不支持网页播放，请转换为 MP4（H.264 视频、AAC 音频）后上传')
            width, height = stream.codec_context.width, stream.codec_context.height
            if width <= 0 or height <= 0 or width * height > 30_000_000:
                raise HTTPException(422, '视频画面尺寸无效或过大')
            stream.codec_context.thread_count = 2
            frame = next(container.decode(stream), None)
            if frame is None:
                raise HTTPException(422, '视频无法解码，请检查文件是否完整')
            poster = frame.to_image().convert('RGB')
            duration = container.duration / av.time_base if container.duration else 0
            info = {'media_type': 'video', 'mime_type': mime, 'width': width, 'height': height,
                    'duration': round(max(0, duration), 2), 'video_codec': stream.codec_context.name}
    except HTTPException:
        raise
    except (av.FFmpegError, ValueError, OverflowError, OSError) as exc:
        raise HTTPException(422, '视频无法读取，请检查文件是否完整或转换为 MP4（H.264）') from exc
    path.mkdir(parents=True, exist_ok=False)
    (path / 'original').write_bytes(raw)
    poster.thumbnail((520, 520))
    poster.save(path / 'thumb.jpg', quality=85)
    return info

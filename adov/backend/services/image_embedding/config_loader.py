from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from pathlib import Path

import yaml


class ImageEmbeddingConfigError(RuntimeError):
    """Raised when the screenshot processing configuration is invalid."""


@dataclass(frozen=True)
class FeatureFlags:
    screenshot_processing_enabled: bool
    screenshot_remote_fallback_enabled: bool


@dataclass(frozen=True)
class StorageConfig:
    bucket_env_var: str
    storage_prefix: str
    sanitize_filenames: bool


@dataclass(frozen=True)
class UploadConfig:
    max_file_size_bytes: int
    allowed_mime_types: tuple[str, ...]


@dataclass(frozen=True)
class LocalOCRMessages:
    summary_prefix: str
    summary_fallback: str


@dataclass(frozen=True)
class LocalOCRConfig:
    grayscale: bool
    max_dimension_px: int
    messages: LocalOCRMessages
    keyword_hints: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class QualityConfig:
    pass_score: float
    min_width: int
    min_height: int
    min_text_length: int
    min_average_confidence: float
    min_detected_signal_items: int
    weights: dict[str, float]


@dataclass(frozen=True)
class RemoteConfig:
    api_key_env_var: str
    model: str
    base_url: str
    timeout_seconds: int
    max_output_tokens: int
    prompt: str


@dataclass(frozen=True)
class ReplyConfig:
    fallback_summary: str
    extracted_text_label: str
    section_labels: dict[str, str]
    extracted_text_preview_chars: int


@dataclass(frozen=True)
class ImageEmbeddingConfig:
    feature_flags: FeatureFlags
    storage: StorageConfig
    upload: UploadConfig
    local_ocr: LocalOCRConfig
    quality: QualityConfig
    remote: RemoteConfig
    reply: ReplyConfig

    @property
    def screenshot_processing_enabled(self) -> bool:
        return self.feature_flags.screenshot_processing_enabled

    @property
    def screenshot_remote_fallback_enabled(self) -> bool:
        return self.feature_flags.screenshot_remote_fallback_enabled

    @property
    def storage_bucket_name(self) -> str | None:
        return os.getenv(self.storage.bucket_env_var)

    @property
    def openai_api_key(self) -> str | None:
        return os.getenv(self.remote.api_key_env_var)


_CONFIG_CACHE: ImageEmbeddingConfig | None = None


def _config_path() -> Path:
    override = os.getenv("IMAGE_EMBEDDING_CONFIG_PATH")
    if override:
        return Path(override)
    return Path(__file__).with_name("config.yaml")


def _require_module(module_name: str) -> None:
    try:
        importlib.import_module(module_name)
    except ImportError as exc:
        raise ImageEmbeddingConfigError(
            f"Missing required dependency: {module_name}"
        ) from exc


def _load_raw_config() -> dict:
    path = _config_path()
    if not path.exists():
        raise ImageEmbeddingConfigError(f"Missing config file: {path}")

    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ImageEmbeddingConfigError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ImageEmbeddingConfigError("config.yaml must contain a mapping at the top level")
    return payload


def _as_bool(value: object, key: str) -> bool:
    if not isinstance(value, bool):
        raise ImageEmbeddingConfigError(f"{key} must be a boolean")
    return value


def _as_str(value: object, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ImageEmbeddingConfigError(f"{key} must be a non-empty string")
    return value.strip()


def _as_int(value: object, key: str) -> int:
    if not isinstance(value, int) or value <= 0:
        raise ImageEmbeddingConfigError(f"{key} must be a positive integer")
    return value


def _as_float(value: object, key: str) -> float:
    if not isinstance(value, (int, float)):
        raise ImageEmbeddingConfigError(f"{key} must be numeric")
    return float(value)


def load_config(*, force_reload: bool = False) -> ImageEmbeddingConfig:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None and not force_reload:
        return _CONFIG_CACHE

    raw = _load_raw_config()

    flags = raw.get("feature_flags", {})
    storage = raw.get("storage", {})
    upload = raw.get("upload", {})
    local_ocr = raw.get("local_ocr", {})
    quality = raw.get("quality", {})
    remote = raw.get("remote", {})
    reply = raw.get("reply", {})

    if not all(isinstance(section, dict) for section in (flags, storage, upload, local_ocr, quality, remote, reply)):
        raise ImageEmbeddingConfigError("All config sections must be mappings")

    feature_flags = FeatureFlags(
        screenshot_processing_enabled=_as_bool(
            flags.get("screenshot_processing_enabled", False),
            "feature_flags.screenshot_processing_enabled",
        ),
        screenshot_remote_fallback_enabled=_as_bool(
            flags.get("screenshot_remote_fallback_enabled", False),
            "feature_flags.screenshot_remote_fallback_enabled",
        ),
    )

    storage_config = StorageConfig(
        bucket_env_var=_as_str(storage.get("bucket_env_var", ""), "storage.bucket_env_var"),
        storage_prefix=_as_str(storage.get("storage_prefix", ""), "storage.storage_prefix"),
        sanitize_filenames=_as_bool(
            storage.get("sanitize_filenames", True),
            "storage.sanitize_filenames",
        ),
    )

    allowed_mime_types = upload.get("allowed_mime_types", [])
    if not isinstance(allowed_mime_types, list) or not allowed_mime_types:
        raise ImageEmbeddingConfigError("upload.allowed_mime_types must be a non-empty list")

    upload_config = UploadConfig(
        max_file_size_bytes=_as_int(
            upload.get("max_file_size_bytes", 0),
            "upload.max_file_size_bytes",
        ),
        allowed_mime_types=tuple(_as_str(item, "upload.allowed_mime_types[]") for item in allowed_mime_types),
    )

    local_messages = local_ocr.get("messages", {})
    keyword_hints = local_ocr.get("keyword_hints", {})
    if not isinstance(local_messages, dict) or not isinstance(keyword_hints, dict):
        raise ImageEmbeddingConfigError("local_ocr.messages and local_ocr.keyword_hints must be mappings")

    local_ocr_config = LocalOCRConfig(
        grayscale=_as_bool(local_ocr.get("grayscale", True), "local_ocr.grayscale"),
        max_dimension_px=_as_int(
            local_ocr.get("max_dimension_px", 0),
            "local_ocr.max_dimension_px",
        ),
        messages=LocalOCRMessages(
            summary_prefix=_as_str(
                local_messages.get("summary_prefix", ""),
                "local_ocr.messages.summary_prefix",
            ),
            summary_fallback=_as_str(
                local_messages.get("summary_fallback", ""),
                "local_ocr.messages.summary_fallback",
            ),
        ),
        keyword_hints={
            key: tuple(_as_str(item, f"local_ocr.keyword_hints.{key}[]") for item in value)
            for key, value in keyword_hints.items()
            if isinstance(value, list)
        },
    )

    weights = quality.get("weights", {})
    if not isinstance(weights, dict):
        raise ImageEmbeddingConfigError("quality.weights must be a mapping")

    quality_config = QualityConfig(
        pass_score=_as_float(quality.get("pass_score", 0), "quality.pass_score"),
        min_width=_as_int(quality.get("min_width", 0), "quality.min_width"),
        min_height=_as_int(quality.get("min_height", 0), "quality.min_height"),
        min_text_length=_as_int(
            quality.get("min_text_length", 0),
            "quality.min_text_length",
        ),
        min_average_confidence=_as_float(
            quality.get("min_average_confidence", 0),
            "quality.min_average_confidence",
        ),
        min_detected_signal_items=_as_int(
            quality.get("min_detected_signal_items", 0),
            "quality.min_detected_signal_items",
        ),
        weights={key: _as_float(value, f"quality.weights.{key}") for key, value in weights.items()},
    )

    remote_config = RemoteConfig(
        api_key_env_var=_as_str(remote.get("api_key_env_var", ""), "remote.api_key_env_var"),
        model=_as_str(remote.get("model", ""), "remote.model"),
        base_url=str(remote.get("base_url", "") or "").strip(),
        timeout_seconds=_as_int(remote.get("timeout_seconds", 0), "remote.timeout_seconds"),
        max_output_tokens=_as_int(
            remote.get("max_output_tokens", 0),
            "remote.max_output_tokens",
        ),
        prompt=_as_str(remote.get("prompt", ""), "remote.prompt"),
    )

    section_labels = reply.get("section_labels", {})
    if not isinstance(section_labels, dict):
        raise ImageEmbeddingConfigError("reply.section_labels must be a mapping")

    reply_config = ReplyConfig(
        fallback_summary=_as_str(reply.get("fallback_summary", ""), "reply.fallback_summary"),
        extracted_text_label=_as_str(
            reply.get("extracted_text_label", ""),
            "reply.extracted_text_label",
        ),
        section_labels={key: _as_str(value, f"reply.section_labels.{key}") for key, value in section_labels.items()},
        extracted_text_preview_chars=_as_int(
            reply.get("extracted_text_preview_chars", 0),
            "reply.extracted_text_preview_chars",
        ),
    )

    _CONFIG_CACHE = ImageEmbeddingConfig(
        feature_flags=feature_flags,
        storage=storage_config,
        upload=upload_config,
        local_ocr=local_ocr_config,
        quality=quality_config,
        remote=remote_config,
        reply=reply_config,
    )
    return _CONFIG_CACHE


def validate_runtime_configuration(*, force_reload: bool = False) -> ImageEmbeddingConfig:
    config = load_config(force_reload=force_reload)

    if not config.upload.allowed_mime_types:
        raise ImageEmbeddingConfigError("upload.allowed_mime_types must not be empty")

    if config.screenshot_processing_enabled:
        if not config.storage_bucket_name:
            raise ImageEmbeddingConfigError(
                f"Environment variable {config.storage.bucket_env_var} is required when screenshot processing is enabled"
            )
        _require_module("PIL")
        _require_module("rapidocr_onnxruntime")

    if config.screenshot_remote_fallback_enabled:
        if not config.openai_api_key:
            raise ImageEmbeddingConfigError(
                f"Environment variable {config.remote.api_key_env_var} is required when remote fallback is enabled"
            )
        _require_module("openai")

    return config


def screenshot_processing_enabled() -> bool:
    return load_config().screenshot_processing_enabled

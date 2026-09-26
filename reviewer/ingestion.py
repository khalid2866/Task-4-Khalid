"""Phase 1 — Input & Payload Capture.

Streams a raw source file from the local OS into application memory as an
untrusted string payload. All whitespace, carriage returns and indentation
are preserved perfectly — the payload is never stripped or normalised.

Triage (context-manager try/except, per the blueprint):
    FileNotFoundError   -> FileMissingError      (clean exit, clear explanation)
    PermissionError     -> AccessDeniedError     (safely reject the attempt)
    UnicodeDecodeError  -> robust codec fallback, else EncodingValidationError
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path

from .exceptions import (
    AccessDeniedError,
    EncodingValidationError,
    FileMissingError,
    IngestionError,
)

# Extension -> markdown language tag. The core kit targets .py / .js / .java;
# the blueprint additionally shows .ts / .cpp / .go / .json flowing through.
SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".go": "go",
    ".json": "json",
}

# Robust codec fallback chain for the UnicodeDecodeError triage branch.
_FALLBACK_CODECS = ("utf-8-sig", "cp1252", "latin-1")

_MAX_BYTES = 2 * 1024 * 1024  # 2 MiB safety cap on a single payload


@dataclass
class IngestedFile:
    """The raw payload buffer handed to Phase 2."""

    path: str
    language: str
    raw_text: str
    size_bytes: int
    line_count: int
    sha256: str
    encoding: str = "utf-8"
    encoding_fallback: bool = False
    warnings: list[str] = field(default_factory=list)


def _reject_binary(path: Path, head: bytes) -> None:
    if b"\x00" in head:
        raise IngestionError(
            f"'{path}': binary asset detected (NUL byte in header). "
            "Only source-code text files can be ingested."
        )


def _decode_with_fallback(path: Path) -> tuple[str, str, bool]:
    """Return (text, codec_used, fell_back). Never crashes on bad encoding."""
    last_error: Exception | None = None
    for i, codec in enumerate(_FALLBACK_CODECS):
        try:
            # newline="" disables universal-newline translation so \r\n
            # sequences are preserved byte-for-byte in the payload.
            with open(path, "r", encoding=codec, newline="") as fh:
                return fh.read(), codec, i > 0
        except UnicodeDecodeError as exc:
            last_error = exc
    raise EncodingValidationError(
        f"'{path}': could not decode with any robust codec "
        f"({', '.join(_FALLBACK_CODECS)}): {last_error}"
    )


def ingest(path: str | os.PathLike) -> IngestedFile:
    """Capture a source file into the raw payload buffer.

    Raises:
        FileMissingError: path is not a valid file.
        AccessDeniedError: read permissions are restricted.
        EncodingValidationError: no robust codec could decode the file.
        IngestionError: unsupported extension, empty file, binary asset,
            or file larger than the safety cap.
    """
    p = Path(path)
    if not p.is_file():
        raise FileMissingError(
            f"'{path}': the specified path does not point to a valid file."
        )
    ext = p.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise IngestionError(
            f"'{path}': unsupported extension '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    # --- context-manager triage block ------------------------------------
    try:
        size = p.stat().st_size
    except FileNotFoundError:
        raise FileMissingError(
            f"'{path}': no such file. Check the path and try again."
        ) from None
    except PermissionError:
        raise AccessDeniedError(
            f"'{path}': read permission denied. The access attempt was "
            "rejected safely; no partial data was captured."
        ) from None
    except OSError as exc:
        raise IngestionError(f"'{path}': cannot stat file: {exc}") from None

    if size == 0:
        raise IngestionError(f"'{path}': file is empty — nothing to review.")
    if size > _MAX_BYTES:
        raise IngestionError(
            f"'{path}': {size} bytes exceeds the 2 MiB payload cap."
        )

    try:
        with open(p, "rb") as fh:
            _reject_binary(p, fh.read(8192))
    except PermissionError:
        raise AccessDeniedError(
            f"'{path}': read permission denied. The access attempt was "
            "rejected safely; no partial data was captured."
        ) from None
    except OSError as exc:
        raise IngestionError(f"'{path}': cannot read file: {exc}") from None

    try:
        text, codec, fell_back = _decode_with_fallback(p)
    except PermissionError:
        raise AccessDeniedError(
            f"'{path}': read permission denied. The access attempt was "
            "rejected safely; no partial data was captured."
        ) from None

    warnings: list[str] = []
    if fell_back:
        warnings.append(
            f"UTF-8 decoding failed; fell back to '{codec}'. "
            "Non-ASCII characters may be approximate."
        )

    return IngestedFile(
        path=str(p),
        language=SUPPORTED_EXTENSIONS[ext],
        raw_text=text,  # byte-for-byte; never stripped
        size_bytes=size,
        line_count=text.count("\n") + 1,
        sha256=hashlib.sha256(text.encode("utf-8", "replace")).hexdigest(),
        encoding=codec,
        encoding_fallback=fell_back,
        warnings=warnings,
    )


def list_supported() -> dict[str, str]:
    """Extension -> language tag map."""
    return dict(SUPPORTED_EXTENSIONS)

"""Document chunk processor — split textbooks / courseware into semantic chunks.

Strategy: split by heading hierarchy + paragraph boundaries, max ~500 tokens per chunk.
Metadata (chapter, section, page) is preserved for citation display in RAG responses.
"""

import hashlib
import re
from dataclasses import dataclass, field


@dataclass
class Chunk:
    """A single document chunk with metadata for citation."""

    chunk_text: str
    source: str  # filename / document name
    chapter: str | None = None
    section: str | None = None
    page: str | None = None
    content_hash: str = ""
    meta: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.content_hash:
            self.content_hash = hashlib.sha256(
                self.chunk_text.encode("utf-8")
            ).hexdigest()[:64]


# ── rough token estimator (Chinese ~1.5 chars/token, English ~4 chars/token) ──

def _estimate_tokens(text: str) -> int:
    """Conservative token count estimate (GPT-family ~2 chars/token mixed)."""
    return max(1, len(text) // 2)


# ── heading detection ──

_HEADING_RE = re.compile(
    r"^(第[一二三四五六七八九十百千万\d]+[章节篇节][^\n]*|"
    r"Chapter\s+\d+[^\n]*|"
    r"\d+(?:[\.\、]\d*)*\s+[^\n]+|"  # e.g. "1.1 定义", "2. 概述"
    r"[一二三四五六七八九十]+[\.\、\s][^\n]+|"
    r"§\d+[^\n]*)",
    re.MULTILINE,
)


def _detect_headings(text: str) -> list[tuple[int, str, int]]:
    """Return [(line_start, heading_text, level), ...] for major structural breaks."""
    headings: list[tuple[int, str, int]] = []
    for m in _HEADING_RE.finditer(text):
        full = m.group().strip()
        # Skip lines that look like code or very long (probably not headings)
        if len(full) > 80:
            continue
        headings.append((m.start(), full, 1))
    return headings


# ── paragraph splitter ──

def _split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs on double newlines."""
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


# ── main processor ──

class DocProcessor:
    """Process raw textbook / courseware text into semantic chunks."""

    def __init__(self, max_tokens: int = 500) -> None:
        self.max_tokens = max_tokens

    # ─────────────────────────────────────────────────────────────────

    def chunk_markdown(self, text: str, source: str) -> list[Chunk]:
        """Chunk markdown text (from PDF/PPT extraction) by headings + paragraphs.

        Strategy:
          1. Detect heading positions.
          2. Split text into sections by heading.
          3. Within each section, split by paragraphs.
          4. Merge small paragraphs up to max_tokens; split oversized ones.
        """
        headings = _detect_headings(text)
        chunks: list[Chunk] = []
        current_chapter: str | None = None
        current_section: str | None = None

        if not headings:
            # Fallback: treat whole text as one section, split by paragraph
            return self._chunk_paragraphs(
                text, source=source, chapter=None, section=None
            )

        # Split at heading boundaries
        sections: list[tuple[str | None, str | None, str]] = []
        for i, (pos, heading, _level) in enumerate(headings):
            next_pos = headings[i + 1][0] if i + 1 < len(headings) else len(text)
            body = text[pos + len(heading) : next_pos].strip()
            full_body = heading + "\n" + body if body else heading
            if i == 0 or _level == 1:
                current_chapter = heading
                current_section = None
            else:
                current_section = heading
            sections.append((current_chapter, current_section, full_body))

        # If no heading found at start, prepend the text before first heading
        if headings and headings[0][0] > 0:
            prefix = text[: headings[0][0]].strip()
            if prefix:
                sections.insert(0, (None, None, prefix))

        for ch, sec, body in sections:
            chunks.extend(
                self._chunk_paragraphs(body, source=source, chapter=ch, section=sec)
            )

        return chunks

    def _chunk_paragraphs(
        self,
        text: str,
        source: str,
        chapter: str | None = None,
        section: str | None = None,
    ) -> list[Chunk]:
        """Split text into paragraph-granularity chunks respecting max_tokens."""
        paragraphs = _split_paragraphs(text)
        chunks: list[Chunk] = []
        buffer: str = ""
        buffer_tokens = 0

        def _flush() -> None:
            nonlocal buffer, buffer_tokens
            if buffer.strip():
                chunks.append(
                    Chunk(
                        chunk_text=buffer.strip(),
                        source=source,
                        chapter=chapter,
                        section=section,
                    )
                )
            buffer = ""
            buffer_tokens = 0

        for para in paragraphs:
            t = _estimate_tokens(para)
            # If a single paragraph exceeds max_tokens, split by sentences
            if t > self.max_tokens:
                _flush()
                for sub in self._split_long_paragraph(para):
                    chunks.append(
                        Chunk(
                            chunk_text=sub,
                            source=source,
                            chapter=chapter,
                            section=section,
                        )
                    )
                continue

            if buffer_tokens + t > self.max_tokens:
                _flush()
            buffer = (buffer + "\n\n" + para) if buffer else para
            buffer_tokens += t

        _flush()
        return chunks

    def _split_long_paragraph(self, text: str) -> list[str]:
        """Split an oversized paragraph on sentence boundaries."""
        sentences = re.split(r"(?<=[。！？.!?])\s*", text)
        result: list[str] = []
        buf = ""
        for s in sentences:
            if _estimate_tokens(buf + s) > self.max_tokens and buf:
                result.append(buf.strip())
                buf = s
            else:
                buf += s
        if buf.strip():
            result.append(buf.strip())
        return result or [text]


# ── module-level convenience ──

processor = DocProcessor()

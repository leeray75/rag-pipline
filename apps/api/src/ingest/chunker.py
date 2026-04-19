"""Token-aware Markdown chunker with heading-path tracking."""

import uuid
from dataclasses import dataclass, field

import tiktoken


@dataclass
class Chunk:
    """A single chunk extracted from a Markdown document."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    job_id: str = ""
    chunk_index: int = 0
    total_chunks: int = 0
    content: str = ""
    token_count: int = 0
    heading_path: str = ""
    metadata: dict = field(default_factory=dict)


class MarkdownChunker:
    """Split Markdown into token-bounded chunks preserving heading context.

    Strategy
    --------
    1. Parse the Markdown into sections delimited by headings (# / ## / ###).
    2. For each section, split into paragraphs (double newline).
    3. Greedily accumulate paragraphs until the token budget is reached.
    4. Emit a Chunk with the heading path as context.
    5. If a single paragraph exceeds the budget, split on sentence boundaries.
    """

    def __init__(
        self,
        *,
        target_tokens: int = 512,
        max_tokens: int = 1024,
        overlap_tokens: int = 64,
        encoding_name: str = "cl100k_base",
    ) -> None:
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.enc = tiktoken.get_encoding(encoding_name)

    def count_tokens(self, text: str) -> int:
        """Return token count for a text string."""
        return len(self.enc.encode(text, disallowed_special=()))

    def chunk_document(
        self,
        *,
        markdown: str,
        document_id: str,
        job_id: str,
        metadata: dict | None = None,
    ) -> list[Chunk]:
        """Chunk a Markdown document into a list of Chunks."""
        sections = self._split_into_sections(markdown)
        raw_chunks: list[str] = []
        heading_paths: list[str] = []

        for heading_path, section_text in sections:
            paragraphs = self._split_paragraphs(section_text)
            section_chunks, section_headings = self._greedy_merge(
                paragraphs, heading_path
            )
            raw_chunks.extend(section_chunks)
            heading_paths.extend(section_headings)

        # Apply overlap between consecutive chunks
        overlapped = self._apply_overlap(raw_chunks)

        # Build Chunk objects
        total = len(overlapped)
        chunks: list[Chunk] = []
        for idx, content in enumerate(overlapped):
            token_count = self.count_tokens(content)
            chunks.append(
                Chunk(
                    document_id=document_id,
                    job_id=job_id,
                    chunk_index=idx,
                    total_chunks=total,
                    content=content,
                    token_count=token_count,
                    heading_path=heading_paths[min(idx, len(heading_paths) - 1)],
                    metadata=metadata or {},
                )
            )
        return chunks

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _split_into_sections(self, markdown: str) -> list[tuple[str, str]]:
        """Split Markdown by headings, returning (heading_path, body) tuples."""
        lines = markdown.split("\n")
        sections: list[tuple[str, str]] = []
        heading_stack: list[str] = []
        current_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                # Flush current section
                if current_lines:
                    path = " > ".join(heading_stack) if heading_stack else "Introduction"
                    sections.append((path, "\n".join(current_lines)))
                    current_lines = []

                # Parse heading level and text
                level = len(stripped) - len(stripped.lstrip("#"))
                heading_text = stripped.lstrip("#").strip()

                # Update heading stack
                while len(heading_stack) >= level:
                    heading_stack.pop()
                heading_stack.append(heading_text)
            else:
                current_lines.append(line)

        # Final section
        if current_lines:
            path = " > ".join(heading_stack) if heading_stack else "Introduction"
            sections.append((path, "\n".join(current_lines)))

        return sections

    def _split_paragraphs(self, text: str) -> list[str]:
        """Split text on double newlines, filtering empties."""
        paragraphs = text.split("\n\n")
        return [p.strip() for p in paragraphs if p.strip()]

    def _greedy_merge(
        self, paragraphs: list[str], heading_path: str
    ) -> tuple[list[str], list[str]]:
        """Greedily merge paragraphs up to target_tokens."""
        chunks: list[str] = []
        headings: list[str] = []
        buffer: list[str] = []
        buffer_tokens = 0

        for para in paragraphs:
            para_tokens = self.count_tokens(para)

            # Single paragraph exceeds max — split on sentences
            if para_tokens > self.max_tokens:
                if buffer:
                    chunks.append("\n\n".join(buffer))
                    headings.append(heading_path)
                    buffer = []
                    buffer_tokens = 0
                sentence_chunks = self._split_long_paragraph(para)
                chunks.extend(sentence_chunks)
                headings.extend([heading_path] * len(sentence_chunks))
                continue

            if buffer_tokens + para_tokens > self.target_tokens and buffer:
                chunks.append("\n\n".join(buffer))
                headings.append(heading_path)
                buffer = []
                buffer_tokens = 0

            buffer.append(para)
            buffer_tokens += para_tokens

        if buffer:
            chunks.append("\n\n".join(buffer))
            headings.append(heading_path)

        return chunks, headings

    def _split_long_paragraph(self, text: str) -> list[str]:
        """Split an oversized paragraph on sentence boundaries."""
        import re

        sentences = re.split(r"(?<=[.!?])\s+", text)
        chunks: list[str] = []
        buffer: list[str] = []
        buffer_tokens = 0

        for sentence in sentences:
            s_tokens = self.count_tokens(sentence)
            if buffer_tokens + s_tokens > self.target_tokens and buffer:
                chunks.append(" ".join(buffer))
                buffer = []
                buffer_tokens = 0
            buffer.append(sentence)
            buffer_tokens += s_tokens

        if buffer:
            chunks.append(" ".join(buffer))

        return chunks

    def _apply_overlap(self, chunks: list[str]) -> list[str]:
        """Add trailing overlap from previous chunk to the start of each chunk."""
        if not chunks or self.overlap_tokens <= 0:
            return chunks

        result = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tokens = self.enc.encode(chunks[i - 1], disallowed_special=())
            overlap_token_ids = prev_tokens[-self.overlap_tokens :]
            overlap_text = self.enc.decode(overlap_token_ids)
            result.append(f"{overlap_text}\n\n{chunks[i]}")
        return result

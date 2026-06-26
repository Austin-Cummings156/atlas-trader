"""Small PDF report writer for server-generated review files."""

from collections.abc import Sequence
from pathlib import Path


def write_text_pdf(
    path: Path,
    *,
    title: str,
    lines: Sequence[str],
) -> None:
    """Write a simple text-only PDF without external dependencies."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text_lines = [title, ""] + list(lines)
    pages = [_pdf_page_lines(chunk) for chunk in _chunks(text_lines, 42)]
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        _pages_object(len(pages)),
    ]

    for page_index, page_lines in enumerate(pages):
        page_number = 3 + page_index * 2
        content_number = page_number + 1
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 "
                f"/BaseFont /Helvetica >> >> >> /Contents {content_number} 0 R >>"
            ).encode("ascii")
        )
        content = _content_stream(page_lines)
        objects.append(
            f"<< /Length {len(content)} >>\nstream\n".encode("ascii")
            + content
            + b"\nendstream"
        )

    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_number, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_number} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(bytes(output))


def _pages_object(page_count: int) -> bytes:
    kids = " ".join(f"{3 + index * 2} 0 R" for index in range(page_count))
    return f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode("ascii")


def _content_stream(lines: Sequence[str]) -> bytes:
    commands = ["BT", "/F1 10 Tf", "72 740 Td", "14 TL"]
    for line in lines:
        commands.append(f"({_escape_pdf_text(line[:100])}) Tj")
        commands.append("T*")
    commands.append("ET")
    return "\n".join(commands).encode("ascii")


def _pdf_page_lines(lines: Sequence[str]) -> list[str]:
    return [line.encode("ascii", "replace").decode("ascii") for line in lines]


def _chunks(lines: Sequence[str], size: int) -> list[list[str]]:
    return [list(lines[index : index + size]) for index in range(0, len(lines), size)] or [[]]


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

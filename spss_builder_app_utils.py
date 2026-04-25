from __future__ import annotations

import json
import re
import tempfile
import uuid
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class QuestionOption:
    code: str
    label: str


@dataclass
class QuestionBlock:
    label: str
    var: str
    tipo: str
    tamanho: str = ""
    max_respostas: str = ""
    logica: str = ""
    nota: str = ""
    options: list[QuestionOption] = field(default_factory=list)


@dataclass
class QuestionnaireDocument:
    questionario: str = ""
    versao: str = "1"
    obs: str = ""
    blocks: list[QuestionBlock] = field(default_factory=list)


def _strip_bom(text: str) -> str:
    return text.lstrip("\ufeff")


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _after_colon(line: str) -> str:
    return line.split(":", 1)[1].strip() if ":" in line else ""


def _is_marker(line: str) -> bool:
    return line.strip().startswith("#")


def load_document_from_text(text: str) -> QuestionnaireDocument:
    text = _strip_bom(text)
    doc = QuestionnaireDocument()
    lines = text.splitlines()

    current: QuestionBlock | None = None
    mode: str | None = None

    def finalize() -> None:
        nonlocal current
        if current is not None:
            doc.blocks.append(current)
            current = None

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("#QUESTIONARIO:"):
            doc.questionario = _after_colon(stripped)
            continue
        if stripped.startswith("#VERSAO:"):
            doc.versao = _after_colon(stripped)
            continue
        if stripped.startswith("#OBS:"):
            doc.obs = _after_colon(stripped)
            continue

        if stripped.startswith("#LABEL:"):
            finalize()
            current = QuestionBlock(label=_after_colon(stripped).rstrip("#").strip(), var="", tipo="")
            mode = None
            continue

        if current is None:
            continue

        if stripped.startswith("#VAR:"):
            current.var = _after_colon(stripped)
            mode = None
            continue
        if stripped.startswith("#TIPO:"):
            current.tipo = _after_colon(stripped)
            mode = None
            continue
        if stripped.startswith("#TAMANHO:"):
            current.tamanho = _after_colon(stripped)
            mode = None
            continue
        if stripped.startswith("#MAX_RESPOSTAS:"):
            current.max_respostas = _after_colon(stripped)
            mode = None
            continue
        if stripped.startswith("#LOGICA:"):
            current.logica = _after_colon(stripped)
            mode = "logica"
            continue
        if stripped.startswith("#NOTA:"):
            current.nota = _after_colon(stripped)
            mode = "nota"
            continue
        if stripped.startswith("#OPCOES:"):
            mode = "opcoes"
            continue
        if stripped.startswith("#FIM"):
            finalize()
            mode = None
            continue

        if mode == "opcoes":
            if "|" in stripped:
                code, label = stripped.split("|", 1)
                current.options.append(QuestionOption(code=code.strip(), label=label.strip()))
            else:
                current.options.append(QuestionOption(code="", label=stripped))
            continue

        if mode == "logica":
            current.logica = (current.logica + " " + stripped).strip()
            continue

        if mode == "nota":
            current.nota = (current.nota + " " + stripped).strip()
            continue

    finalize()
    return doc


def load_document_from_path(path: str | Path) -> QuestionnaireDocument:
    return load_document_from_text(Path(path).read_text(encoding="utf-8"))


def serialize_document(doc: QuestionnaireDocument) -> str:
    lines: list[str] = []
    if doc.questionario:
        lines.append(f"#QUESTIONARIO: {doc.questionario}")
    if doc.versao:
        lines.append(f"#VERSAO: {doc.versao}")
    if doc.obs:
        lines.append(f"#OBS: {doc.obs}")
    lines.append("")

    for block in doc.blocks:
        lines.append(f"#LABEL: {block.label}#")
        lines.append(f"#VAR: {block.var}")
        lines.append(f"#TIPO: {block.tipo}")
        if block.tamanho and block.tipo == "aberta_texto":
            lines.append(f"#TAMANHO: {block.tamanho}")
        if block.max_respostas and block.tipo == "rm":
            lines.append(f"#MAX_RESPOSTAS: {block.max_respostas}")
        if block.logica.strip():
            lines.append(f"#LOGICA: {block.logica.strip()}")
        if block.nota.strip():
            lines.append(f"#NOTA: {block.nota.strip()}")
        if block.tipo in {"ru", "rm"}:
            lines.append("#OPCOES:")
            for option in block.options:
                lines.append(f"{option.code} | {option.label}".strip())
        lines.append("#FIM")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def label_bytes(label: str) -> int:
    return len(label.encode("cp1252", errors="replace"))


def safe_internal_name(base_name: str) -> str:
    ascii_base = _strip_accents(base_name).encode("ascii", errors="ignore").decode("ascii")
    slug = "".join(ch if ch.isalnum() else "_" for ch in ascii_base.lower()).strip("_")
    slug = "_".join(part for part in slug.split("_") if part)
    if not slug:
        slug = "questionario"
    return f"{slug}_{uuid.uuid4().hex[:8]}"


def generate_next_var(doc: QuestionnaireDocument) -> str:
    max_number = 0
    pattern = re.compile(r"^VAR(\d{5})$")
    for block in doc.blocks:
        match = pattern.match((block.var or "").strip().upper())
        if match:
            max_number = max(max_number, int(match.group(1)))
    return f"VAR{max_number + 1:05d}"


def make_new_block(doc: QuestionnaireDocument) -> QuestionBlock:
    return QuestionBlock(
        label="Nova questão",
        var=generate_next_var(doc),
        tipo="ru",
        options=[
            QuestionOption(code="1", label="Opção 1"),
            QuestionOption(code="2", label="Opção 2"),
        ],
    )


def append_new_block(doc: QuestionnaireDocument) -> QuestionBlock:
    block = make_new_block(doc)
    doc.blocks.append(block)
    return block


def delete_block(doc: QuestionnaireDocument, index: int) -> QuestionBlock | None:
    if index < 0 or index >= len(doc.blocks):
        return None
    return doc.blocks.pop(index)


def document_summary(doc: QuestionnaireDocument) -> dict[str, Any]:
    return {
        "questionario": doc.questionario,
        "versao": doc.versao,
        "total_blocos": len(doc.blocks),
        "total_ru": sum(1 for b in doc.blocks if b.tipo == "ru"),
        "total_rm": sum(1 for b in doc.blocks if b.tipo == "rm"),
        "total_aberta_texto": sum(1 for b in doc.blocks if b.tipo == "aberta_texto"),
        "total_aberta_numero": sum(1 for b in doc.blocks if b.tipo == "aberta_numero"),
        "max_label_bytes": max((label_bytes(b.label) for b in doc.blocks), default=0),
    }


def make_runtime_dir(prefix: str = "spss_builder") -> Path:
    root = Path(tempfile.gettempdir()) / prefix
    root.mkdir(parents=True, exist_ok=True)
    run_dir = root / uuid.uuid4().hex[:8]
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_runtime_input(doc: QuestionnaireDocument, run_dir: Path, base_name: str) -> tuple[Path, Path]:
    internal_name = safe_internal_name(base_name)
    txt_path = run_dir / f"{internal_name}.txt"
    output_base = run_dir / internal_name
    txt_path.write_text(serialize_document(doc), encoding="utf-8")
    return txt_path, output_base


def blocks_to_json(doc: QuestionnaireDocument) -> str:
    payload = {
        "questionario": doc.questionario,
        "versao": doc.versao,
        "obs": doc.obs,
        "blocks": [asdict(block) for block in doc.blocks],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)

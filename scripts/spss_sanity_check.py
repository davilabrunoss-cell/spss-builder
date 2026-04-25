#!/usr/bin/env python3
"""Deterministic structural sanity check for SPSS/iPesquisa questionnaire TXT files."""

from __future__ import annotations

import argparse
import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyreadstat

from spss_questionnaire_v2 import (
    QuestionnaireParserV2,
    after_colon,
    marker_key,
    strip_accents,
    write_sav,
    write_sav_with_mrsets,
)


VALID_TYPES = {"ru", "rm", "aberta_texto", "aberta_numero"}


def safe_ascii_stem(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", errors="ignore").decode("ascii")
    slug = "".join(ch if ch.isalnum() else "_" for ch in ascii_value.lower()).strip("_")
    slug = "_".join(part for part in slug.split("_") if part)
    return slug or "questionario"


@dataclass
class BlockScan:
    label_line: int
    label_text: str
    explicit_var: str | None = None
    explicit_type: str | None = None
    has_tamanho: bool = False
    has_max_respostas: bool = False
    option_lines: list[str] = field(default_factory=list)
    in_options: bool = False
    closed: bool = False


def make_error(stage: str, code: str, message: str, *, var: str | None = None, line: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "stage": stage,
        "code": code,
        "message": message,
    }
    if var:
        payload["var"] = var
    if line:
        payload["line"] = line
    return payload


def read_questionnaire_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lstrip("\ufeff")


def scan_blocks(text: str) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    current: BlockScan | None = None
    seen_vars: dict[str, int] = {}

    def finalize_current() -> None:
        nonlocal current
        if current is None:
            return

        block_ref = current.explicit_var or current.label_text

        if not current.closed:
            errors.append(
                make_error(
                    "block_scan",
                    "missing_fim",
                    "Bloco sem #FIM.",
                    var=current.explicit_var,
                    line=current.label_line,
                )
            )

        if not current.explicit_var:
            errors.append(
                make_error(
                    "block_scan",
                    "missing_var",
                    "Bloco sem #VAR.",
                    line=current.label_line,
                )
            )

        if not current.explicit_type:
            errors.append(
                make_error(
                    "block_scan",
                    "missing_tipo",
                    "Bloco sem #TIPO.",
                    var=current.explicit_var,
                    line=current.label_line,
                )
            )
        else:
            normalized_type = strip_accents(current.explicit_type).lower()
            if normalized_type not in VALID_TYPES:
                errors.append(
                    make_error(
                        "block_scan",
                        "invalid_tipo",
                        f"Tipo de pergunta inválido: {current.explicit_type}.",
                        var=current.explicit_var,
                        line=current.label_line,
                    )
                )
            if normalized_type == "aberta_texto" and not current.has_tamanho:
                errors.append(
                    make_error(
                        "block_scan",
                        "missing_tamanho",
                        "Pergunta aberta_texto sem #TAMANHO.",
                        var=current.explicit_var,
                        line=current.label_line,
                    )
                )
            if normalized_type in {"ru", "rm"} and not current.option_lines:
                errors.append(
                    make_error(
                        "block_scan",
                        "missing_options",
                        f"Pergunta {normalized_type} sem opções.",
                        var=current.explicit_var,
                        line=current.label_line,
                    )
                )
            if normalized_type == "rm" and not current.has_max_respostas:
                errors.append(
                    make_error(
                        "block_scan",
                        "missing_max_respostas",
                        "Pergunta rm sem #MAX_RESPOSTAS.",
                        var=current.explicit_var,
                        line=current.label_line,
                    )
                )

        if current.explicit_var:
            if current.explicit_var in seen_vars:
                errors.append(
                    make_error(
                        "block_scan",
                        "duplicate_var",
                        f"VAR duplicada: {current.explicit_var}.",
                        var=current.explicit_var,
                        line=current.label_line,
                    )
                )
            else:
                seen_vars[current.explicit_var] = current.label_line

        current = None

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        key = marker_key(line)

        if key == "label":
            finalize_current()
            label = after_colon(line) if ":" in line else line
            current = BlockScan(label_line=line_number, label_text=label)
            continue

        if current is None:
            continue

        if key == "var":
            current.explicit_var = after_colon(line)
            continue

        if key == "tipo":
            current.explicit_type = after_colon(line)
            continue

        if key == "tamanho":
            current.has_tamanho = True
            continue

        if key == "max_respostas":
            current.has_max_respostas = True
            continue

        if key == "opcoes":
            current.in_options = True
            first_option = after_colon(line)
            if first_option:
                current.option_lines.append(first_option)
            continue

        if key == "fim":
            current.closed = True
            finalize_current()
            continue

        if current.in_options and key is None and current.explicit_type and strip_accents(current.explicit_type).lower() in {"ru", "rm"}:
            current.option_lines.append(line)

    finalize_current()
    return errors


def validate_schema(schema: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []

    validation = schema.get("validation", {})
    for message in validation.get("errors", []):
        errors.append(make_error("schema_validation", "schema_error", message))

    for var in schema.get("variables", []):
        label = var.get("label_full", "")
        label_bytes = len(label.encode("cp1252", errors="replace"))
        if label_bytes > 255:
            errors.append(
                make_error(
                    "schema_validation",
                    "label_too_long",
                    f"Label acima de 255 bytes em Windows-1252: {label_bytes} bytes.",
                    var=var.get("name"),
                )
            )

        if var.get("logical_type") == "rm":
            max_responses = var.get("max_responses")
            if max_responses is None:
                errors.append(
                    make_error(
                        "schema_validation",
                        "missing_max_responses_schema",
                        "Pergunta rm sem max_responses no schema.",
                        var=var.get("name"),
                    )
                )
            elif not isinstance(max_responses, int) or max_responses < 1:
                errors.append(
                    make_error(
                        "schema_validation",
                        "invalid_max_responses_schema",
                        f"max_responses inválido no schema: {max_responses}.",
                        var=var.get("name"),
                    )
                )

    return errors


def build_sav(schema: dict[str, Any], output_base: Path, rm_mode: str) -> tuple[Path, Path]:
    schema_path = output_base.with_name(output_base.name + "_schema.json")
    sav_path = output_base.with_suffix(".sav")
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    if rm_mode == "mrsets":
        write_sav_with_mrsets(schema, sav_path)
    else:
        write_sav(schema, sav_path, rm_mode=rm_mode)
    return schema_path, sav_path


def readback_sav(sav_path: Path) -> list[dict[str, Any]]:
    attempts: list[str] = []
    for encoding in (None, "WINDOWS-1252", "CP1252", "LATIN1"):
        try:
            kwargs = {"metadataonly": True}
            if encoding is not None:
                kwargs["encoding"] = encoding
            pyreadstat.read_sav(str(sav_path), **kwargs)
            return []
        except Exception as exc:  # pragma: no cover - defensive path
            label = encoding or "default"
            attempts.append(f"{label}: {type(exc).__name__}: {exc}")
    return [
        make_error(
            "sav_readback",
            "sav_readback_failed",
            "Falha ao reler o .sav gerado. Tentativas: " + " | ".join(attempts),
        )
    ]


def default_output_base(input_path: Path) -> Path:
    safe_stem = safe_ascii_stem(input_path.stem)
    return input_path.with_name(f"{safe_stem}_sanity")


def run_sanity_check(input_path: Path, output_base: Path, rm_mode: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "bloqueado",
        "input_path": str(input_path),
        "schema_generated": False,
        "sav_generated": False,
        "sav_readback_ok": False,
        "error_count": 0,
        "errors": [],
        "artifacts": {},
    }

    try:
        text = read_questionnaire_text(input_path)
    except Exception as exc:
        result["errors"] = [
            make_error(
                "read_input",
                "input_read_failed",
                f"Falha ao ler o arquivo de entrada: {type(exc).__name__}: {exc}",
            )
        ]
        result["error_count"] = len(result["errors"])
        return result

    block_errors = scan_blocks(text)
    if block_errors:
        result["errors"] = block_errors
        result["error_count"] = len(block_errors)
        return result

    try:
        schema = QuestionnaireParserV2().parse(text)
        result["schema_generated"] = True
    except Exception as exc:  # pragma: no cover - defensive path
        result["errors"] = [
            make_error(
                "parse",
                "parse_failed",
                f"Falha ao gerar schema: {type(exc).__name__}: {exc}",
            )
        ]
        result["error_count"] = len(result["errors"])
        return result

    schema_errors = validate_schema(schema)
    if schema_errors:
        schema_path = output_base.with_name(output_base.name + "_schema.json")
        schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
        result["artifacts"]["schema_path"] = str(schema_path)
        result["errors"] = schema_errors
        result["error_count"] = len(schema_errors)
        return result

    try:
        schema_path, sav_path = build_sav(schema, output_base, rm_mode)
        result["artifacts"]["schema_path"] = str(schema_path)
        result["artifacts"]["sav_path"] = str(sav_path)
        result["sav_generated"] = True
    except Exception as exc:
        result["errors"] = [
            make_error(
                "sav_build",
                "sav_build_failed",
                f"Falha ao gerar o .sav: {type(exc).__name__}: {exc}",
            )
        ]
        result["error_count"] = len(result["errors"])
        return result

    readback_errors = readback_sav(sav_path)
    if readback_errors:
        result["errors"] = readback_errors
        result["error_count"] = len(readback_errors)
        return result

    result["sav_readback_ok"] = True
    result["status"] = "apto"
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Structural sanity check for SPSS questionnaire TXT files.")
    parser.add_argument("input", help="Path to the questionnaire TXT file.")
    parser.add_argument("--output-base", help="Base path for generated schema and SAV artifacts.")
    parser.add_argument("--rm-mode", choices=["mrsets", "single", "slots"], default="mrsets")
    parser.add_argument("--json-out", help="Optional path to save the sanity-check result as JSON.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    output_base = Path(args.output_base) if args.output_base else default_output_base(input_path)
    result = run_sanity_check(input_path, output_base, args.rm_mode)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        Path(args.json_out).write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if result["status"] == "apto" else 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Parse questionnaire text into a validated SPSS/iPesquisa schema and optional .sav."""

from __future__ import annotations

import argparse
import collections
import collections.abc
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def marker_key(line: str) -> str | None:
    text = strip_accents(line.strip()).lower()
    if re.match(r"^#?label\s*:", text):
        return "label"
    if re.match(r"^#\s*\d+(?:\.\d+)*\.?.*#$", text):
        return "label"
    if re.match(r"^#?q\s*:", text):
        return "q"
    if re.match(r"^#?tipo\s*:", text):
        return "tipo"
    if re.match(r"^#?var\s*:", text):
        return "var"
    if re.match(r"^#?tamanho\s*:", text):
        return "tamanho"
    if re.match(r"^#?max[_\s-]?respostas?\s*:", text):
        return "max_respostas"
    if re.match(r"^#?opcoes?\s*:", text):
        return "opcoes"
    if re.match(r"^#?logica\s*:", text):
        return "logica"
    if re.match(r"^#?nota\s*:", text):
        return "nota"
    if re.match(r"^#?fim\s*$", text):
        return "fim"
    return None


def after_colon(line: str) -> str:
    return line.split(":", 1)[1].strip() if ":" in line else ""


def collapse_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def remove_inline_hash_label(value: str) -> str:
    value = value.strip()
    value = re.sub(r"#\s*label\s*:\s*$", "", value, flags=re.IGNORECASE).strip()
    if value.endswith("#"):
        value = value[:-1].strip()
    if value.startswith("#"):
        value = value[1:].strip()
    return value


def parse_option(line: str, fallback_code: int) -> tuple[int, str]:
    cleaned = line.strip()
    cleaned = re.sub(r"^[\-\*\u2022]\s*", "", cleaned)
    coded = re.match(r"^(\d+)\s*(?:[\|\-\.\)]\s+|\s+)(.+)$", cleaned)
    if coded:
        return int(coded.group(1)), coded.group(2).strip()
    return fallback_code, cleaned


@dataclass
class QuestionBlock:
    raw_number: str | None = None
    explicit_var: str | None = None
    explicit_type: str | None = None
    max_responses: int | None = None
    text_size: int | None = None
    label_lines: list[str] = field(default_factory=list)
    option_lines: list[str] = field(default_factory=list)
    logic_lines: list[str] = field(default_factory=list)
    note_lines: list[str] = field(default_factory=list)

    def label_full(self) -> str:
        return collapse_ws(" ".join(line.strip() for line in self.label_lines if line.strip()))


class QuestionnaireParserV2:
    def parse(self, text: str) -> dict[str, Any]:
        blocks = self._parse_blocks(text)
        variables = []
        warnings = []

        for index, block in enumerate(blocks, start=1):
            variable = self._block_to_variable(block, index)
            if variable["logical_type"] == "instrucao":
                continue
            variables.append(variable)

        errors = self._validate_variables(variables, warnings)
        return {
            "schema_version": "2.0",
            "created_at": datetime.now().isoformat(),
            "total_variables": len(variables),
            "variables": variables,
            "validation": {
                "ok": not errors,
                "errors": errors,
                "warnings": warnings,
            },
        }

    def _parse_blocks(self, text: str) -> list[QuestionBlock]:
        lines = text.splitlines()
        blocks: list[QuestionBlock] = []
        current: QuestionBlock | None = None
        mode = "label"

        def finish_current() -> None:
            nonlocal current
            if current and (current.label_full() or current.option_lines or current.explicit_type):
                blocks.append(current)
            current = None

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            key = marker_key(line)

            if key == "label":
                finish_current()
                current = QuestionBlock()
                label = after_colon(line) if ":" in line else line
                current.label_lines.append(remove_inline_hash_label(label))
                number_match = re.match(r"^(\d+(?:\.\d+)*)\.?\s*(.*)$", current.label_lines[0])
                if number_match:
                    current.raw_number = number_match.group(1)
                mode = "label"
                continue

            if key == "q":
                finish_current()
                current = QuestionBlock(raw_number=after_colon(line))
                mode = "label"
                continue

            if current is None:
                continue

            if key == "tipo":
                current.explicit_type = strip_accents(after_colon(line)).lower()
                mode = "label"
                continue

            if key == "var":
                current.explicit_var = after_colon(line)
                mode = "label"
                continue

            if key == "tamanho":
                size_match = re.search(r"\d+", after_colon(line))
                if size_match:
                    current.text_size = int(size_match.group(0))
                mode = "label"
                continue

            if key == "max_respostas":
                max_text = after_colon(line)
                max_match = re.search(r"\d+", max_text)
                if max_match:
                    current.max_responses = int(max_match.group(0))
                mode = "label"
                continue

            if key == "opcoes":
                first_option = after_colon(line)
                if first_option:
                    current.option_lines.append(first_option)
                mode = "options"
                continue

            if key == "logica":
                logic = after_colon(line)
                if logic:
                    current.logic_lines.append(logic)
                mode = "logic"
                continue

            if key == "nota":
                note = after_colon(line)
                if note:
                    current.note_lines.append(note)
                mode = "note"
                continue

            if key == "fim":
                finish_current()
                mode = "label"
                continue

            if mode == "options":
                current.option_lines.append(line)
            elif mode == "logic":
                current.logic_lines.append(line)
            elif mode == "note":
                current.note_lines.append(line)
            else:
                current.label_lines.append(line)

        finish_current()
        return blocks

    def _block_to_variable(self, block: QuestionBlock, index: int) -> dict[str, Any]:
        options = self._parse_options(block.option_lines)
        logical_type = self._infer_type(block, options)
        var_name = block.explicit_var or f"VAR{index:05d}"
        label_full = block.label_full()

        return {
            "name": var_name,
            "source_number": block.raw_number,
            "label_full": label_full,
            "label_short": self._short_label(label_full),
            "logical_type": logical_type,
            "max_responses": self._max_responses(block, logical_type, options),
            "storage_type": "numeric" if logical_type in {"ru", "rm", "aberta_numero"} else "string",
            "measure": "nominal" if logical_type in {"ru", "rm"} else "scale" if logical_type == "aberta_numero" else "nominal",
            "format": "F8.0" if logical_type in {"ru", "rm", "aberta_numero"} else f"A{block.text_size or 255}",
            "missing": [97, 98, 99] if logical_type in {"ru", "rm", "aberta_numero"} else ["NS", "NR"],
            "has_options": bool(options),
            "options": options,
            "logic": collapse_ws(" ".join(block.logic_lines)),
            "notes": collapse_ws(" ".join(block.note_lines)),
            "max_responses_explicit": block.max_responses is not None,
        }

    def _parse_options(self, option_lines: list[str]) -> dict[int, str]:
        options: dict[int, str] = {}
        next_code = 1
        for line in option_lines:
            key = marker_key(line)
            if key in {"label", "q", "tipo", "var", "opcoes", "fim", "logica", "nota"}:
                continue
            if not line.strip():
                continue
            code, label = parse_option(line, next_code)
            if label:
                options[code] = label
                next_code = max(next_code + 1, code + 1)
        return options

    def _infer_type(self, block: QuestionBlock, options: dict[int, str]) -> str:
        label_hint = strip_accents(block.label_full()).lower()
        if block.explicit_type:
            value = block.explicit_type
            if "rm" in value or "multipla" in value:
                return "rm"
            if "numero" in value or "numeric" in value:
                return "aberta_numero"
            if "instrucao" in value:
                return "instrucao"
            if "aberta" in value or "texto" in value:
                return "aberta_texto"
            if "ru" in value or "unica" in value:
                return "ru"
        if re.search(r"(^|[\[\(\-\s])rm($|[\]\)\-\s])", label_hint) or "multipla" in label_hint or "pode marcar mais de uma" in label_hint or "escolha ate" in label_hint:
            return "rm"
        if options:
            return "ru"
        return "aberta_texto"

    def _max_responses(self, block: QuestionBlock, logical_type: str, options: dict[int, str]) -> int | None:
        if logical_type != "rm":
            return None
        if block.max_responses:
            return block.max_responses
        label_hint = strip_accents(block.label_full()).lower()
        limit_patterns = [
            r"ate\s+(\d+)",
            r"ate\s+(\d+)\s+op",
            r"escolh[ae]\s+(?:as\s+|os\s+)?(\d+)",
            r"marcar\s+(?:ate\s+)?(\d+)",
        ]
        for pattern in limit_patterns:
            match = re.search(pattern, label_hint)
            if match:
                return int(match.group(1))
        return len(options) if options else None

    def _short_label(self, label: str, limit: int = 120) -> str:
        if len(label) <= limit:
            return label
        return label[: limit - 3].rstrip() + "..."

    def _validate_variables(self, variables: list[dict[str, Any]], warnings: list[str]) -> list[str]:
        errors = []
        if not variables:
            errors.append("No variables were detected.")

        seen_names = set()
        for var in variables:
            name = var["name"]
            if name in seen_names:
                errors.append(f"Duplicate variable name: {name}")
            seen_names.add(name)

            if not var["label_full"]:
                errors.append(f"{name}: empty label.")

            if var["logical_type"] == "ru":
                if not var["options"]:
                    errors.append(f"{name}: single-response question must define options.")
                elif len(var["options"]) == 1:
                    warnings.append(f"{name}: single-response question has only one option; confirm this is intentional.")

            if var["logical_type"] == "rm":
                if not var.get("max_responses"):
                    errors.append(f"{name}: RM question must define max_responses.")
                elif var["max_responses"] > max(1, len(var["options"])):
                    warnings.append(f"{name}: max_responses is greater than the number of options.")
                elif var["max_responses"] == len(var["options"]) and not var.get("max_responses_explicit"):
                    warnings.append(f"{name}: max_responses was inferred as the number of options; prefer #MAX_RESPOSTAS for production.")

            label_bytes = len(var["label_full"].encode("cp1252", errors="replace"))
            if label_bytes > 255:
                warnings.append(f"{name}: label_full is longer than 255 bytes in Windows-1252; SPSS/iPesquisa compatibility should be checked.")

        return errors


def write_sav(schema: dict[str, Any], output_path: Path, rm_mode: str = "mrsets") -> None:
    import pandas as pd
    import pyreadstat

    empty_data = {}
    column_labels = []
    variable_value_labels = {}

    for var in schema["variables"]:
        if var["logical_type"] == "rm":
            if rm_mode == "mrsets":
                slot_count = int(var["max_responses"])
                for slot in range(1, slot_count + 1):
                    slot_name = f"{var['name']}_{slot}"
                    empty_data[slot_name] = pd.Series(dtype="float64")
                    column_labels.append(var["label_full"])
                    variable_value_labels[slot_name] = {float(code): label for code, label in var["options"].items()}
                continue

            if rm_mode == "single":
                empty_data[var["name"]] = pd.Series(dtype="float64")
                column_labels.append(var["label_full"])
                variable_value_labels[var["name"]] = {float(code): label for code, label in var["options"].items()}
                continue

            slot_count = int(var["max_responses"])
            for slot in range(1, slot_count + 1):
                slot_name = f"{var['name']}_{slot}"
                empty_data[slot_name] = pd.Series(dtype="float64")
                column_labels.append(var["label_full"])
                variable_value_labels[slot_name] = {float(code): label for code, label in var["options"].items()}
            continue

        dtype = "float64" if var["storage_type"] == "numeric" else "object"
        empty_data[var["name"]] = pd.Series(dtype=dtype)
        column_labels.append(var["label_full"])
        if var["has_options"]:
            variable_value_labels[var["name"]] = {float(code): label for code, label in var["options"].items()}

    df = pd.DataFrame(empty_data)
    pyreadstat.write_sav(
        df,
        str(output_path),
        column_labels=column_labels,
        variable_value_labels=variable_value_labels or None,
        file_label="Questionario iPesquisa V2",
    )


def write_sav_with_mrsets(schema: dict[str, Any], output_path: Path) -> None:
    collections.Iterable = collections.abc.Iterable
    collections.Mapping = collections.abc.Mapping
    collections.Sequence = collections.abc.Sequence
    from savReaderWriter import SavWriter

    var_names: list[bytes] = []
    var_types: dict[bytes, int] = {}
    var_labels: dict[bytes, bytes] = {}
    value_labels: dict[bytes, dict[float, bytes]] = {}
    mult_resp_defs: dict[bytes, dict[bytes, Any]] = {}

    def b(value: str) -> bytes:
        return value.encode("utf-8", errors="replace")

    for var in schema["variables"]:
        if var["logical_type"] == "rm":
            slot_names: list[bytes] = []
            slot_count = int(var["max_responses"])
            for slot in range(1, slot_count + 1):
                slot_name = f"{var['name']}_{slot}"
                slot_name_b = b(slot_name)
                slot_names.append(slot_name_b)
                var_names.append(slot_name_b)
                var_types[slot_name_b] = 0
                var_labels[slot_name_b] = b(var["label_full"])
                value_labels[slot_name_b] = {float(code): b(label.strip()) for code, label in var["options"].items()}

            set_name = b(f"MR_{var['name']}")
            mult_resp_defs[set_name] = {
                b"setType": b"C",
                b"label": b(var["label_full"]),
                b"varNames": slot_names,
            }
            continue

        name_b = b(var["name"])
        var_names.append(name_b)
        var_types[name_b] = 255 if var["storage_type"] == "string" else 0
        var_labels[name_b] = b(var["label_full"])
        if var["has_options"]:
            value_labels[name_b] = {float(code): b(label.strip()) for code, label in var["options"].items()}

    with SavWriter(
        str(output_path),
        var_names,
        var_types,
        varLabels=var_labels,
        valueLabels=value_labels,
        multRespDefs=mult_resp_defs or None,
        fileLabel=b"Questionario iPesquisa V2",
        overwrite=True,
        ioUtf8=1,
    ) as writer:
        pass


def command_parse(args: argparse.Namespace) -> int:
    text = Path(args.input).read_text(encoding="utf-8")
    schema = QuestionnaireParserV2().parse(text)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(schema, ensure_ascii=False, indent=2))
    return 0 if schema["validation"]["ok"] else 2


def command_build(args: argparse.Namespace) -> int:
    text = Path(args.input).read_text(encoding="utf-8")
    schema = QuestionnaireParserV2().parse(text)
    output_base = Path(args.output_base)
    schema_path = output_base.with_name(output_base.name + "_schema.json")
    sav_path = output_base.with_suffix(".sav")
    schema_path.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    if not schema["validation"]["ok"]:
        print(json.dumps(schema["validation"], ensure_ascii=False, indent=2))
        return 2
    if args.rm_mode == "mrsets":
        write_sav_with_mrsets(schema, sav_path)
    else:
        write_sav(schema, sav_path, rm_mode=args.rm_mode)
    print(str(sav_path))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SPSS questionnaire builder v2 prototype")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_cmd = subparsers.add_parser("parse")
    parse_cmd.add_argument("input")
    parse_cmd.add_argument("--json-out")
    parse_cmd.set_defaults(func=command_parse)

    build_cmd = subparsers.add_parser("build")
    build_cmd.add_argument("input")
    build_cmd.add_argument("--output-base", required=True)
    build_cmd.add_argument("--rm-mode", choices=["mrsets", "single", "slots"], default="mrsets")
    build_cmd.set_defaults(func=command_build)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

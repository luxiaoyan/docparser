from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any

from docparser.models import ExtractedField, ExtractionResult, UnifiedParseResult


class SchemaNotFound(KeyError):
    pass


class ExtractionNotFound(KeyError):
    pass


class SchemaValidationError(ValueError):
    pass


class SchemaExtractor:
    def extract(
        self,
        extraction_id: str,
        document_id: str,
        schema: dict[str, Any],
        parse_result: UnifiedParseResult,
    ) -> ExtractionResult:
        schema_id = str(schema.get("schema_id") or "")
        if not schema_id:
            raise SchemaValidationError("schema_id is required")

        fields: dict[str, ExtractedField] = {}
        warnings: list[str] = []
        for field_schema in schema.get("fields", []):
            field_name = str(field_schema.get("name") or "")
            if not field_name:
                raise SchemaValidationError("field name is required")

            extracted = self._extract_field(field_schema, parse_result)
            if extracted is None:
                if bool(field_schema.get("required", False)):
                    warnings.append(f"Missing required field: {field_name}")
                    fields[field_name] = ExtractedField(
                        value=None,
                        normalized_value=None,
                        confidence=0.0,
                        source="none",
                        status="missing",
                    )
                else:
                    fields[field_name] = ExtractedField(
                        value=None,
                        normalized_value=None,
                        confidence=0.0,
                        source="none",
                        status="empty",
                    )
                continue

            normalized_value, status = self._normalize(extracted.value, str(field_schema.get("type", "string")))
            fields[field_name] = ExtractedField(
                value=extracted.value,
                normalized_value=normalized_value,
                confidence=extracted.confidence,
                source=extracted.source,
                status=status,
                strategy=extracted.strategy,
            )

        return ExtractionResult(
            extraction_id=extraction_id,
            document_id=document_id,
            schema_id=schema_id,
            status="succeeded",
            fields=fields,
            warnings=warnings,
        )

    def _extract_field(self, field_schema: dict[str, Any], parse_result: UnifiedParseResult) -> ExtractedField | None:
        for strategy in field_schema.get("strategies", []):
            strategy_type = strategy.get("type")
            if strategy_type == "form_field":
                extracted = self._extract_form_field(strategy, parse_result)
            elif strategy_type == "regex":
                extracted = self._extract_regex(strategy, parse_result)
            elif strategy_type == "keyword":
                extracted = self._extract_keyword(strategy, parse_result)
            elif strategy_type == "table_column":
                extracted = self._extract_table_column(strategy, parse_result)
            else:
                extracted = None

            if extracted is not None:
                return extracted
        return None

    def _extract_form_field(
        self,
        strategy: dict[str, Any],
        parse_result: UnifiedParseResult,
    ) -> ExtractedField | None:
        wanted = {str(name).lower() for name in strategy.get("field_names", [])}
        if not wanted:
            return None

        for form in parse_result.content.forms:
            candidates = {
                str(form.get("name", "")).lower(),
                str(form.get("label", "")).lower(),
            }
            if candidates & wanted and form.get("value") is not None:
                return ExtractedField(
                    value=str(form["value"]),
                    normalized_value=str(form["value"]),
                    confidence=1.0,
                    source="form",
                    status="valid",
                    strategy="form_field",
                )
        return None

    def _extract_regex(
        self,
        strategy: dict[str, Any],
        parse_result: UnifiedParseResult,
    ) -> ExtractedField | None:
        pattern = strategy.get("pattern")
        if not pattern:
            return None

        text = "\n".join(
            [
                parse_result.content.markdown,
                *[block.text for block in parse_result.content.text_blocks],
            ]
        )
        match = re.search(str(pattern), text, flags=re.MULTILINE)
        if not match:
            return None

        value = match.group(1) if match.groups() else match.group(0)
        return ExtractedField(
            value=value,
            normalized_value=value,
            confidence=float(strategy.get("confidence", 0.9)),
            source="text",
            status="valid",
            strategy="regex",
        )

    def _extract_keyword(
        self,
        strategy: dict[str, Any],
        parse_result: UnifiedParseResult,
    ) -> ExtractedField | None:
        keyword = str(strategy.get("keyword", ""))
        if not keyword:
            return None

        for line in parse_result.content.markdown.splitlines():
            if keyword not in line:
                continue
            value = line.split(keyword, 1)[1].strip(" :：\t")
            if value:
                return ExtractedField(
                    value=value,
                    normalized_value=value,
                    confidence=float(strategy.get("confidence", 0.7)),
                    source="text",
                    status="valid",
                    strategy="keyword",
                )
        return None

    def _extract_table_column(
        self,
        strategy: dict[str, Any],
        parse_result: UnifiedParseResult,
    ) -> ExtractedField | None:
        wanted_headers = [str(header) for header in strategy.get("headers", [])]
        if not wanted_headers:
            return None

        for table in parse_result.content.tables:
            headers = [str(header) for header in table.get("headers", [])]
            rows = table.get("rows", [])
            if not isinstance(rows, list):
                continue

            for wanted in wanted_headers:
                if wanted not in headers:
                    continue
                column_index = headers.index(wanted)
                for row in rows:
                    if not isinstance(row, list) or column_index >= len(row):
                        continue
                    value = row[column_index]
                    if value is None or str(value).strip() == "":
                        continue
                    return ExtractedField(
                        value=str(value),
                        normalized_value=str(value),
                        confidence=float(strategy.get("confidence", 0.85)),
                        source="table",
                        status="valid",
                        strategy="table_column",
                    )
        return None

    def _normalize(self, value: Any, field_type: str) -> tuple[Any, str]:
        if value is None:
            return None, "missing"

        if field_type in {"string", "enum"}:
            return str(value).strip(), "valid"

        if field_type in {"number", "money"}:
            text = str(value).replace(",", "").replace("¥", "").replace("$", "").strip()
            try:
                normalized = Decimal(text)
            except InvalidOperation:
                return value, "invalid"
            return format(normalized, "f"), "valid"

        if field_type == "boolean":
            text = str(value).strip().lower()
            if text in {"true", "yes", "y", "1", "是"}:
                return True, "valid"
            if text in {"false", "no", "n", "0", "否"}:
                return False, "valid"
            return value, "invalid"

        return value, "valid"

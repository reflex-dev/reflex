"""Normalize actual collector payloads for repeatable relationship assertions."""

import base64
import gzip
import json
import re


def identifier(value):
    """Normalize OTLP JSON hex IDs or protobuf JSON base64 IDs.

    Args:
        value: Encoded identifier.

    Returns:
        Lowercase hex identifier, or empty text.
    """
    if not value:
        return ""
    return (
        value.lower()
        if re.fullmatch(r"[0-9a-fA-F]{16}|[0-9a-fA-F]{32}", value)
        else base64.b64decode(value).hex()
    )


def attributes(values):
    """Flatten OTLP scalar attribute values.

    Args:
        values: OTLP key/value pairs.

    Returns:
        Plain mapping retaining compound values if present.
    """
    return {row["key"]: next(iter(row["value"].values()), None) for row in values}


def read_spans(path):
    """Read complete decoded exports, tolerating only a currently partial tail.

    Args:
        path: Collector JSONL file.

    Returns:
        Normalized spans with collection time, resource and original status.
    """
    spans = []
    if not path.exists():
        return spans
    content = (
        gzip.decompress(path.read_bytes()).decode()
        if path.suffix == ".gz"
        else path.read_text()
    )
    lines = content.splitlines()
    for index, line in enumerate(lines):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            if index == len(lines) - 1:
                continue
            raise
        for resource in row["decoded"].get("resourceSpans", []):
            resource_attrs = attributes(
                resource.get("resource", {}).get("attributes", [])
            )
            for scope in resource.get("scopeSpans", []):
                for span in scope.get("spans", []):
                    kind = span.get("kind", 0)
                    if isinstance(kind, int):
                        kind = {
                            0: "UNSPECIFIED",
                            1: "INTERNAL",
                            2: "SERVER",
                            3: "CLIENT",
                            4: "PRODUCER",
                            5: "CONSUMER",
                        }[kind]
                    else:
                        kind = kind.removeprefix("SPAN_KIND_")
                    spans.append(
                        {
                            "collected": row["time"],
                            "name": span["name"],
                            "service": resource_attrs.get("service.name"),
                            "resource": resource_attrs,
                            "trace_id": identifier(span.get("traceId")),
                            "span_id": identifier(span.get("spanId")),
                            "parent_id": identifier(span.get("parentSpanId")),
                            "kind": kind,
                            "attributes": attributes(span.get("attributes", [])),
                            "status": span.get("status", {}),
                            "events": span.get("events", []),
                            "start": span.get("startTimeUnixNano"),
                            "end": span.get("endTimeUnixNano"),
                        }
                    )
    return spans

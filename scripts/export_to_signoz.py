"""Send a ReplayLens report to a self-hosted SigNoz as OpenTelemetry traces.

Usage (run from the replaylens folder):
    python scripts/export_to_signoz.py docs/your_report.json

Needs:  pip install -r scripts/requirements-otel.txt
SigNoz must be running (UI on http://localhost:8080, OTLP/HTTP on port 4318).
"""
import json
import sys

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

ENDPOINT = "http://localhost:4318/v1/traces"


def scalars(prefix, obj, out):
    """Copy simple values (text, numbers, true/false) into span attributes."""
    if not isinstance(obj, dict):
        return
    for key, value in obj.items():
        name = f"{prefix}.{key}"
        if isinstance(value, (str, int, float, bool)):
            out[name] = value[:500] if isinstance(value, str) else value
        elif isinstance(value, dict):
            scalars(name, value, out)


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python scripts/export_to_signoz.py <report.json>")

    with open(sys.argv[1], encoding="utf-8") as f:
        report = json.load(f)

    provider = TracerProvider(resource=Resource.create({"service.name": "replaylens"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=ENDPOINT)))
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer("replaylens.export")

    results = report.get("results", [])
    with tracer.start_as_current_span("replaylens.report") as root:
        attrs = {}
        scalars("summary", report.get("summary", {}), attrs)
        attrs["run.count"] = len(results)
        root.set_attributes(attrs)

        for i, item in enumerate(results):
            with tracer.start_as_current_span("replaylens.run") as span:
                a = {"run.index": i}
                scalars("run", item, a)
                span.set_attributes(a)

    provider.shutdown()  # flushes everything to SigNoz
    print(f"Sent 1 report span + {len(results)} run spans to {ENDPOINT}")


if __name__ == "__main__":
    main()

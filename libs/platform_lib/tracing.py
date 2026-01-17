import os

from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def configure_tracing(service_name: str) -> None:
    tracer_provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    exporter = JaegerExporter(
        agent_host_name=os.getenv("JAEGER_HOST", "jaeger"),
        agent_port=int(os.getenv("JAEGER_PORT", "6831")),
    )
    tracer_provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(tracer_provider)
    HTTPXClientInstrumentor().instrument()


def instrument_app(app) -> None:
    FastAPIInstrumentor.instrument_app(app)

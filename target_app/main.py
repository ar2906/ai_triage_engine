import json
from fastapi import FastAPI
from pydantic import BaseModel
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

class JsonlFileSpanExporter(SpanExporter):
    def __init__(self, file_path: str = "logs/traces.jsonl"):
        self.file_path = file_path

    def export(self, spans) -> SpanExportResult:
        with open(self.file_path, "a", encoding="utf-8") as f:
            for span in spans:
                record = {
                    "trace_id": format(span.context.trace_id, "032x"),
                    "span_id": format(span.context.span_id, "016x"),
                    "name": span.name,
                    "status": span.status.status_code.name,
                    "attributes": dict(span.attributes or {}),
                    "events": [
                        {"name": e.name, "attributes": dict(e.attributes or {})}
                        for e in span.events
                    ],
                }
                f.write(json.dumps(record) + "\n")
        return SpanExportResult.SUCCESS

provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(JsonlFileSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("orders-service")

app = FastAPI(title="Orders Microservice")
FastAPIInstrumentor.instrument_app(app)

class OrderRequest(BaseModel):
    order_id: str
    amount: float
    coupon: dict | None = None

@app.post("/orders")
def create_order(order: OrderRequest):
    with tracer.start_as_current_span("calculate_discount") as span:
        span.set_attribute("order.id", order.order_id)
        span.set_attribute("order.payload", order.model_dump_json())

        discount = 0.0
        discount = order.amount * (order.coupon["percent"] / 100.0)
        final_total = round(order.amount - discount, 2)
        return {"order_id": order.order_id, "final_total": final_total}
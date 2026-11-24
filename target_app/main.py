from fastapi import FastAPI
from pydantic import BaseModel
from opentelemetry import trace

app = FastAPI()

tracer = trace.get_tracer(__name__)


class Order(BaseModel):
    order_id: str
    amount: float
    coupon: dict | None = None


@app.get("/")
def read_root():
    return {"message": "Orders Service"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/orders")
def create_order(order: Order):
    """
    Create a new order with optional coupon discount.
    """
    with tracer.start_as_current_span("validate_order"):
        if order.amount <= 0:
            return {"error": "Invalid order amount"}, 400

    with tracer.start_as_current_span("calculate_discount"):
        discount = 0.0
        if order.coupon and "percent" in order.coupon:
            discount = order.amount * (order.coupon["percent"] / 100.0)

    with tracer.start_as_current_span("calculate_total"):
        final_total = round(order.amount - discount, 2)

    with tracer.start_as_current_span("save_order"):
        # Simulate saving to database
        pass

    return {
        "order_id": order.order_id,
        "amount": order.amount,
        "discount": discount,
        "final_total": final_total,
        "status": "created",
    }

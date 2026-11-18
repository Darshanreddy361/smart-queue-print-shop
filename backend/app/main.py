from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .database import get_connection, init_db

# Tune these values to match the actual printer and binding workflow.
PRINT_SECONDS_PER_PAGE = 2.0
BINDING_SECONDS = {"none": 0, "soft": 180, "spiral": 300}
STATUS_ORDER = ("queued", "printing", "binding", "ready", "collected", "cancelled")
ACTIVE_STATUSES = ("queued", "printing", "binding")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Smart Queue & Pickup Estimator API",
    description="Queue management and pickup-time estimation for campus print shops.",
    version="1.0.0",
    lifespan=lifespan,
)


class OrderCreate(BaseModel):
    student_name: str = Field(min_length=1, max_length=80)
    document_name: str = Field(min_length=1, max_length=120)
    pages: int = Field(ge=1, le=2000)
    binding: Literal["none", "soft", "spiral"] = "none"
    copies: int = Field(default=1, ge=1, le=20)


class StatusUpdate(BaseModel):
    status: Literal["queued", "printing", "binding", "ready", "collected", "cancelled"]


def row_to_dict(row):
    return dict(row) if row else None


def order_work_seconds(order):
    return (order["pages"] * order["copies"] * PRINT_SECONDS_PER_PAGE
            + BINDING_SECONDS.get(order["binding"], 0))


def estimate_for_order(conn, order_id):
    # FIFO estimate: remaining work for active orders ahead, plus this order.
    rows = conn.execute(
        "SELECT * FROM orders WHERE status IN ('queued','printing','binding') ORDER BY id"
    ).fetchall()
    seconds = 0
    found = False
    for row in rows:
        item = dict(row)
        seconds += order_work_seconds(item)
        if item["id"] == order_id:
            found = True
            break
    if not found:
        return 0
    return max(1, (seconds + 59) // 60)


def enrich_order(conn, row):
    item = row_to_dict(row)
    item["estimated_minutes"] = estimate_for_order(conn, item["id"])
    return item


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/orders", status_code=201)
def create_order(payload: OrderCreate):
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO orders (student_name, document_name, pages, binding, copies)
               VALUES (?, ?, ?, ?, ?)""",
            (payload.student_name.strip(), payload.document_name.strip(),
             payload.pages, payload.binding, payload.copies),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return enrich_order(conn, row)


@app.get("/orders")
def list_orders(status: str | None = None):
    with get_connection() as conn:
        if status:
            if status not in STATUS_ORDER:
                raise HTTPException(status_code=400, detail="Unknown status")
            rows = conn.execute("SELECT * FROM orders WHERE status = ? ORDER BY id", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 200").fetchall()
        return [enrich_order(conn, row) for row in rows]


@app.get("/orders/{order_id}")
def get_order(order_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Order not found")
        return enrich_order(conn, row)


@app.patch("/orders/{order_id}/status")
def update_status(order_id: int, payload: StatusUpdate):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Order not found")
        conn.execute(
            "UPDATE orders SET status = ?, updated_at = datetime('now','localtime') WHERE id = ?",
            (payload.status, order_id),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        return enrich_order(conn, updated)


@app.get("/queue/summary")
def queue_summary():
    with get_connection() as conn:
        active = conn.execute(
            "SELECT COUNT(*) AS count FROM orders WHERE status IN ('queued','printing','binding')"
        ).fetchone()["count"]
        ready = conn.execute(
            "SELECT COUNT(*) AS count FROM orders WHERE status = 'ready'"
        ).fetchone()["count"]
        waiting_seconds = sum(order_work_seconds(dict(row)) for row in conn.execute(
            "SELECT * FROM orders WHERE status IN ('queued','printing','binding')"
        ).fetchall())
        return {
            "active_orders": active,
            "ready_orders": ready,
            "estimated_queue_minutes": (waiting_seconds + 59) // 60,
        }

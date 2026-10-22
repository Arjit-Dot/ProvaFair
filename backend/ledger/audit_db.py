import os
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from sqlalchemy import create_engine, Column, String, Float, Text, Integer, DateTime, event
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import IntegrityError

def _resolve_db_url() -> str:
    if "DATABASE_URL" in os.environ:
        return os.environ["DATABASE_URL"]
    db_name = os.getenv("LEDGER_DB_NAME", "ledger.db")
    if not os.path.isabs(db_name):
        candidate = Path(__file__).resolve().parent.parent / db_name
        if candidate.exists() or Path(__file__).resolve().parent.parent.exists():
            return f"sqlite:///{candidate}"
    return f"sqlite:///{db_name}"

DB_NAME = os.getenv("LEDGER_DB_NAME", "ledger.db")
DATABASE_URL = _resolve_db_url()

engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()


event.listen(engine, "connect", _set_sqlite_pragma)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()



class Draw(Base):
    """SQLAlchemy ORM model representing a draw record in the ledger."""
    __tablename__ = "draws"

    draw_id = Column(String, primary_key=True)
    event_name = Column(String, nullable=False)
    timestamp = Column(String, nullable=False)
    chsh_score = Column(Float, nullable=False)
    status = Column(String, nullable=False)
    winners = Column(Text, nullable=False)
    receipt_hash = Column(String, nullable=False)
    service_type = Column(String, nullable=False, default="lottery")
    previous_hash = Column(String, nullable=False)
    ibm_job_id = Column(String, nullable=True, default="SIMULATED")

    def to_dict(self) -> dict:
        return {
            "draw_id": self.draw_id,
            "event_name": self.event_name,
            "timestamp": self.timestamp,
            "chsh_score": self.chsh_score,
            "status": self.status,
            "winners": json.loads(self.winners) if isinstance(self.winners, str) else self.winners,
            "receipt_hash": self.receipt_hash,
            "service_type": self.service_type,
            "previous_hash": self.previous_hash,
            "ibm_job_id": self.ibm_job_id or "SIMULATED",
        }


class IdempotencyRecord(Base):
    """SQLAlchemy ORM model storing processed idempotency keys mapped to draw_id and JSON response."""
    __tablename__ = "idempotency_records"

    key = Column(String, primary_key=True)
    draw_id = Column(String, nullable=False)
    response_payload = Column(Text, nullable=False)
    created_at = Column(String, nullable=False)


class ApiUsageLog(Base):
    """SQLAlchemy ORM model storing API request logs for rate limiting and usage tracking."""
    __tablename__ = "api_usage_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    api_key = Column(String, nullable=False)
    endpoint = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)


def init_db(engine_instance=None):
    """Creates the database and draws table if they don't exist, and ensures schema columns."""
    eng = engine_instance or engine
    Base.metadata.create_all(bind=eng)

    # Backwards compatibility migration check if table pre-existed without new columns
    with eng.connect() as conn:
        try:
            result = conn.exec_driver_sql("PRAGMA table_info(draws)")
            existing_columns = {row[1] for row in result.fetchall()}
            if existing_columns:
                if "service_type" not in existing_columns:
                    conn.exec_driver_sql("ALTER TABLE draws ADD COLUMN service_type TEXT DEFAULT 'lottery'")
                if "previous_hash" not in existing_columns:
                    conn.exec_driver_sql("ALTER TABLE draws ADD COLUMN previous_hash TEXT DEFAULT 'GENESIS'")
                if "ibm_job_id" not in existing_columns:
                    conn.exec_driver_sql("ALTER TABLE draws ADD COLUMN ibm_job_id TEXT DEFAULT 'SIMULATED'")
                conn.commit()
        except Exception:
            pass


def record_draw(
    draw_id: str,
    event_name: str,
    chsh_score: float,
    status: str,
    winners: list[int],
    service_type: str = "lottery",
    previous_hash: str | None = None,
    ibm_job_id: str | None = "SIMULATED",
) -> str:
    """
    Saves the draw data and generates a tamper-evident SHA-256 hash receipt
    using hash-chained ledger logic.
    """
    init_db()
    with SessionLocal() as session:
        # Determine previous_hash if not explicitly provided
        if previous_hash is None:
            # Query for the receipt_hash of the most recent draw
            most_recent = session.query(Draw).order_by(Draw.timestamp.desc(), Draw.draw_id.desc()).first()
            if most_recent and most_recent.receipt_hash:
                previous_hash = most_recent.receipt_hash
            else:
                previous_hash = "GENESIS"

        # Format the timestamp and winners list for storage
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
        winners_str = json.dumps(winners)

        # 1. Concatenate critical draw data including previous_hash into a single raw string
        raw_payload = f"{draw_id}:{event_name}:{ts}:{chsh_score}:{status}:{winners_str}:{previous_hash}"

        # 2. Cryptographically hash the string to create the permanent receipt
        receipt_hash = hashlib.sha256(raw_payload.encode()).hexdigest()

        # 3. Store everything in the ledger using SQLAlchemy ORM
        draw = Draw(
            draw_id=draw_id,
            event_name=event_name,
            timestamp=ts,
            chsh_score=chsh_score,
            status=status,
            winners=winners_str,
            receipt_hash=receipt_hash,
            service_type=service_type,
            previous_hash=previous_hash,
            ibm_job_id=ibm_job_id or "SIMULATED",
        )
        session.add(draw)
        session.commit()

        return receipt_hash


def get_draw(draw_id: str) -> dict | None:
    """
    Fetches a specific draw by ID for public auditing.
    """
    with SessionLocal() as session:
        draw = session.query(Draw).filter(Draw.draw_id == draw_id).first()
        if not draw:
            return None

        return {
            "draw_id": draw.draw_id,
            "event_name": draw.event_name,
            "timestamp": draw.timestamp,
            "chsh_score": draw.chsh_score,
            "status": draw.status,
            "winners": json.loads(draw.winners) if isinstance(draw.winners, str) else draw.winners,
            "receipt_hash": draw.receipt_hash,
            "service_type": draw.service_type,
            "previous_hash": draw.previous_hash,
            "ibm_job_id": draw.ibm_job_id or "SIMULATED",
        }


def get_idempotency_record(key: str) -> dict | None:
    """
    Retrieves cached JSON response for a given idempotency key if it exists.
    """
    init_db()
    with SessionLocal() as session:
        rec = session.query(IdempotencyRecord).filter(IdempotencyRecord.key == key).first()
        if not rec:
            return None
        try:
            return json.loads(rec.response_payload)
        except Exception:
            return None


def save_idempotency_record(key: str, draw_id: str, response_payload: dict | Any) -> None:
    """
    Saves processed idempotency key with corresponding draw_id and response payload.
    """
    init_db()
    payload_str = json.dumps(response_payload) if not isinstance(response_payload, str) else response_payload
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"
    with SessionLocal() as session:
        rec = IdempotencyRecord(
            key=key,
            draw_id=draw_id,
            response_payload=payload_str,
            created_at=ts,
        )
        session.merge(rec)
        session.commit()


def log_api_request(api_key: str, endpoint: str) -> None:
    """
    Logs an API request made by a specific api_key to an endpoint.
    """
    init_db()
    with SessionLocal() as session:
        log_entry = ApiUsageLog(
            api_key=api_key,
            endpoint=endpoint,
            timestamp=datetime.utcnow(),
        )
        session.add(log_entry)
        session.commit()


def count_recent_requests(api_key: str, window_seconds: int = 60) -> int:
    """
    Counts how many requests a specific api_key has made in the last `window_seconds` seconds.
    """
    init_db()
    cutoff = datetime.utcnow() - timedelta(seconds=window_seconds)
    with SessionLocal() as session:
        return session.query(ApiUsageLog).filter(
            ApiUsageLog.api_key == api_key,
            ApiUsageLog.timestamp >= cutoff,
        ).count()


def calculate_merkle_root(hashes: list[str]) -> str:
    """
    Computes the Merkle root of a list of SHA-256 hashes by pairing adjacent hashes,
    concatenating them, and hashing repeatedly until a single root remains.
    If the list is odd, duplicates the last hash for the pair.
    """
    if not hashes:
        return ""
    current = list(hashes)
    while len(current) > 1:
        if len(current) % 2 != 0:
            current.append(current[-1])
        next_level = []
        for i in range(0, len(current), 2):
            combined = current[i] + current[i + 1]
            next_level.append(hashlib.sha256(combined.encode()).hexdigest())
        current = next_level
    return current[0]


def get_ledger_merkle_root() -> str | None:
    """
    Queries all receipt_hash strings from the draws table in timestamp order,
    and passes them to calculate_merkle_root. If the database is empty, returns None.
    """
    init_db()
    with SessionLocal() as session:
        rows = session.query(Draw.receipt_hash).order_by(Draw.timestamp.asc(), Draw.draw_id.asc()).all()
        if not rows:
            return None
        hashes = [r[0] for r in rows]
        return calculate_merkle_root(hashes)


def get_ledger_draw_count() -> int:
    """
    Returns the total number of draws recorded in the ledger.
    """
    init_db()
    with SessionLocal() as session:
        return session.query(Draw).count()


if __name__ == "__main__":
    print("1. Initializing Database...")
    init_db()

    print("\n2. Recording a test draw...")
    test_id = "DRAW-TEST001"

    try:
        test_hash = record_draw(
            draw_id=test_id,
            event_name="Hackathon Test Draw",
            chsh_score=2.825,
            status="VERIFIED",
            winners=[14, 27, 52, 88],
            service_type="lottery",
        )
        print(f"   Saved! Cryptographic Receipt Hash: {test_hash}")
    except IntegrityError:
        print("   (Test draw already exists in the database, skipping insert.)")

    print("\n3. Retrieving the draw for audit...")
    audit_record = get_draw(test_id)
    if audit_record:
        print(f"   Retrieved Event: {audit_record['event_name']}")
        print(f"   Retrieved Winners: {audit_record['winners']}")
        print(f"   Retrieved Score: {audit_record['chsh_score']}")
        print(f"   Retrieved Service Type: {audit_record['service_type']}")
        print(f"   Retrieved Previous Hash: {audit_record['previous_hash']}")
        print(f"   Retrieved Receipt Hash: {audit_record['receipt_hash']}")
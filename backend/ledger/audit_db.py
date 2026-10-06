import sqlite3
import hashlib
import json
from datetime import datetime

DB_NAME = "ledger.db"

def init_db():
    """Creates the SQLite database and the draws table if they don't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS draws (
            draw_id TEXT PRIMARY KEY,
            event_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            chsh_score REAL NOT NULL,
            status TEXT NOT NULL,
            winners TEXT NOT NULL,
            receipt_hash TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def record_draw(draw_id: str, event_name: str, chsh_score: float, status: str, winners: list[int]) -> str:
    """
    Saves the draw data and generates a tamper-evident SHA-256 hash receipt.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Format the timestamp and winners list for storage
    ts = datetime.utcnow().isoformat() + "Z"
    winners_str = json.dumps(winners)
    
    # 1. Concatenate all critical draw data into a single raw string
    raw_payload = f"{draw_id}:{event_name}:{ts}:{chsh_score}:{status}:{winners_str}"
    
    # 2. Cryptographically hash the string to create the permanent receipt
    receipt_hash = hashlib.sha256(raw_payload.encode()).hexdigest()
    
    # 3. Store everything in the ledger
    cursor.execute("""
        INSERT INTO draws (draw_id, event_name, timestamp, chsh_score, status, winners, receipt_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (draw_id, event_name, ts, chsh_score, status, winners_str, receipt_hash))
    
    conn.commit()
    conn.close()
    
    return receipt_hash

def get_draw(draw_id: str) -> dict | None:
    """
    Fetches a specific draw by ID for public auditing.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT draw_id, event_name, timestamp, chsh_score, status, winners, receipt_hash FROM draws WHERE draw_id = ?", (draw_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
        
    return {
        "draw_id": row[0],
        "event_name": row[1],
        "timestamp": row[2],
        "chsh_score": row[3],
        "status": row[4],
        "winners": json.loads(row[5]),
        "receipt_hash": row[6]
    }

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
            winners=[14, 27, 52, 88]
        )
        print(f"   Saved! Cryptographic Receipt Hash: {test_hash}")
    except sqlite3.IntegrityError:
        print("   (Test draw already exists in the database, skipping insert.)")
    
    print("\n3. Retrieving the draw for audit...")
    audit_record = get_draw(test_id)
    if audit_record:
        print(f"   Retrieved Event: {audit_record['event_name']}")
        print(f"   Retrieved Winners: {audit_record['winners']}")
        print(f"   Retrieved Score: {audit_record['chsh_score']}")
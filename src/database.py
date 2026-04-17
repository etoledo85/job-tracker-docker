import os
import sqlite3
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, List

BASE_DIR = Path(__file__).parent.parent
_data_dir = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
DB_PATH = _data_dir / "jobs.db"

VALID_STATUSES = ["new", "reviewing", "applied", "interview", "rejected", "offer", "discarded"]


@dataclass
class Job:
    title: str
    company: str
    location: str
    url: str
    source: str
    description: str = ""
    salary: str = ""
    date_posted: str = ""
    id: Optional[int] = None
    date_found: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "new"
    cover_letter_path: str = ""
    notes: str = ""
    remote: bool = False


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            url TEXT UNIQUE NOT NULL,
            source TEXT,
            description TEXT,
            salary TEXT,
            date_posted TEXT,
            date_found TEXT,
            status TEXT DEFAULT 'new',
            cover_letter_path TEXT,
            notes TEXT,
            remote INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def upsert_job(job: Job) -> tuple[bool, int]:
    """Insert a job if URL not seen before. Returns (is_new, id)."""
    conn = get_conn()
    try:
        cursor = conn.execute(
            "SELECT id FROM jobs WHERE url = ?", (job.url,)
        )
        row = cursor.fetchone()
        if row:
            return False, row["id"]

        cursor = conn.execute(
            """INSERT INTO jobs
               (title, company, location, url, source, description, salary,
                date_posted, date_found, status, remote)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (job.title, job.company, job.location, job.url, job.source,
             job.description, job.salary, job.date_posted,
             job.date_found, job.status, int(job.remote))
        )
        conn.commit()
        return True, cursor.lastrowid
    finally:
        conn.close()


def get_jobs(status: Optional[str] = None, limit: int = 50) -> List[sqlite3.Row]:
    conn = get_conn()
    if status:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY date_found DESC LIMIT ?",
            (status, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY date_found DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return rows


def get_job(job_id: int) -> Optional[sqlite3.Row]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return row


def update_job(job_id: int, **kwargs):
    if not kwargs:
        return
    fields = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [job_id]
    conn = get_conn()
    conn.execute(f"UPDATE jobs SET {fields} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_stats() -> dict:
    conn = get_conn()
    rows = conn.execute(
        "SELECT status, COUNT(*) as count FROM jobs GROUP BY status"
    ).fetchall()
    conn.close()
    return {row["status"]: row["count"] for row in rows}

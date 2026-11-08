"""作業看板 API（FastAPI + PostgreSQL）"""
import os
import socket
from datetime import datetime

import psycopg
from fastapi import FastAPI, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

DATABASE_URL = os.environ["DATABASE_URL"]
app = FastAPI(title="hw6 作業看板 API", root_path="")


def conn():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


class AssignmentIn(BaseModel):
    course: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=200)
    due: datetime


class DonePatch(BaseModel):
    done: bool


@app.get("/api/health")
def health():
    """回傳 API 所在的容器名稱與資料庫版本，用來展示微服務彼此連得到"""
    with conn() as c:
        version = c.execute("SELECT version() AS v").fetchone()["v"]
        count = c.execute("SELECT COUNT(*) AS n FROM assignments").fetchone()["n"]
    return {"api_container": socket.gethostname(), "postgres": version.split(",")[0], "rows": count}


@app.get("/api/assignments")
def list_assignments():
    with conn() as c:
        return c.execute(
            """SELECT id, course, title, due, done, created_at,
                      (due < NOW() AND NOT done) AS overdue
               FROM assignments ORDER BY done, due"""
        ).fetchall()


@app.post("/api/assignments", status_code=201)
def create_assignment(a: AssignmentIn):
    with conn() as c:
        return c.execute(
            "INSERT INTO assignments (course, title, due) VALUES (%s, %s, %s) RETURNING *",
            (a.course.strip(), a.title.strip(), a.due.replace(tzinfo=None)),
        ).fetchone()


@app.patch("/api/assignments/{aid}")
def set_done(aid: int, p: DonePatch):
    with conn() as c:
        row = c.execute("UPDATE assignments SET done=%s WHERE id=%s RETURNING *", (p.done, aid)).fetchone()
    if not row:
        raise HTTPException(404, "找不到作業")
    return row


@app.delete("/api/assignments/{aid}")
def delete_assignment(aid: int):
    with conn() as c:
        n = c.execute("DELETE FROM assignments WHERE id=%s", (aid,)).rowcount
    if not n:
        raise HTTPException(404, "找不到作業")
    return {"ok": True}


@app.get("/api/stats")
def stats():
    with conn() as c:
        return c.execute(
            """SELECT course, COUNT(*) AS total, COUNT(*) FILTER (WHERE done) AS done
               FROM assignments GROUP BY course ORDER BY total DESC"""
        ).fetchall()

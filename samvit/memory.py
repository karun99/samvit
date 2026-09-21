"""Memory graph — SQLite with WAL, append-only audit, term index, typed edges."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS claim (
    claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'user',
    trust REAL NOT NULL DEFAULT 1.0 CHECK (trust >= 0.0 AND trust <= 1.0),
    ts TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'core'
);
CREATE INDEX IF NOT EXISTS idx_claim_ts ON claim(ts);

CREATE TABLE IF NOT EXISTS edge (
    src INTEGER NOT NULL REFERENCES claim(claim_id),
    rel TEXT NOT NULL,
    dst INTEGER NOT NULL REFERENCES claim(claim_id),
    PRIMARY KEY (src, rel, dst)
);

CREATE TABLE IF NOT EXISTS term (
    term TEXT NOT NULL,
    claim_id INTEGER NOT NULL REFERENCES claim(claim_id),
    PRIMARY KEY (term, claim_id)
);
CREATE INDEX IF NOT EXISTS idx_term_name ON term(term);

CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    action TEXT NOT NULL,
    subject TEXT NOT NULL,
    detail TEXT NOT NULL,
    prev_hash TEXT NOT NULL DEFAULT ''
);

CREATE TRIGGER IF NOT EXISTS trg_audit_no_update
BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;
CREATE TRIGGER IF NOT EXISTS trg_audit_no_delete
BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;

CREATE TABLE IF NOT EXISTS persona_signal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    axis TEXT NOT NULL,
    value REAL NOT NULL,
    ts TEXT NOT NULL,
    profile TEXT NOT NULL DEFAULT 'global'
);
CREATE TABLE IF NOT EXISTS persona_anchor (
    axis TEXT PRIMARY KEY,
    value REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_TOKEN_RE = re.compile(r"[a-z0-9']+", re.IGNORECASE)
_STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "was", "with", "had",
    "his", "her", "that", "this", "were", "have", "has", "had", "your",
    "from", "they", "them", "will", "would", "there", "their", "what",
    "when", "where", "who", "how", "about", "into", "then", "than",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _audit_hash(at: str, action: str, subject: str, detail: str, prev: str) -> str:
    """SHA-256 over the row fields plus the previous row's hash — audit hash chain (FR-11.5)."""
    canon = "|".join([at, action, subject, detail, prev])
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text) if t.lower() not in _STOPWORDS]


class Memory:
    def __init__(self, path: str):
        self.path = path
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------- audit
    def audit(self, action: str, subject: str, detail: str = "") -> None:
        """Append-only audit row, hash-chained to its predecessor (FR-5.9/FR-11.5)."""
        with self._conn:
            # migrate older DBs: add prev_hash column if it is missing.
            cols = {r[1] for r in self._conn.execute("PRAGMA table_info(audit)")}
            if "prev_hash" not in cols:
                self._conn.execute(
                    "ALTER TABLE audit ADD COLUMN prev_hash TEXT NOT NULL DEFAULT ''")
                self._conn.execute("DROP TRIGGER IF EXISTS trg_audit_no_update")
                self._conn.execute("DROP TRIGGER IF EXISTS trg_audit_no_delete")
                # backfill: rebuild the chain over every existing row.
                rows = self._conn.execute(
                    "SELECT id, at, action, subject, detail, prev_hash FROM audit"
                    " ORDER BY id ASC").fetchall()
                prev = "genesis"
                for r in rows:
                    h = _audit_hash(r["at"], r["action"], r["subject"], r["detail"], prev)
                    self._conn.execute(
                        "UPDATE audit SET prev_hash = ? WHERE id = ?", (h, r["id"]))
                    prev = h
                self._conn.execute(
                    "CREATE TRIGGER IF NOT EXISTS trg_audit_no_update BEFORE UPDATE ON audit"
                    " BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;")
                self._conn.execute(
                    "CREATE TRIGGER IF NOT EXISTS trg_audit_no_delete BEFORE DELETE ON audit"
                    " BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;")
            last = self._conn.execute(
                "SELECT prev_hash FROM audit ORDER BY id DESC LIMIT 1").fetchone()
            prev = last["prev_hash"] if last else "genesis"
            now = _now()
            h = _audit_hash(now, action, subject, detail, prev)
            self._conn.execute(
                "INSERT INTO audit(at, action, subject, detail, prev_hash) "
                "VALUES (?, ?, ?, ?, ?)", (now, action, subject, detail, h))
            self._maybe_rotate()

    def _maybe_rotate(self) -> None:
        """FR-11.6: bounded-budget device — archive and trim over-cap audit rows."""
        cap = getattr(self, "max_audit_rows", 10000)
        if cap <= 0:
            return
        row = self._conn.execute(
            "SELECT COUNT(*) AS c FROM audit").fetchone()
        if row["c"] <= cap:
            return
        # archive only the rows that are safe to drop (keep the chain tail intact).
        drop = self._conn.execute(
            "SELECT id, at, action, subject, detail, prev_hash FROM audit"
            " WHERE id NOT IN (SELECT id FROM audit ORDER BY id DESC LIMIT ?)"
            " ORDER BY id ASC", (cap,)).fetchall()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        arc = os.path.join(os.path.dirname(os.path.abspath(self.path)),
                           f"audit_archive_{stamp}.jsonl")
        with open(arc, "a", encoding="utf-8") as fh:
            for r in drop:
                fh.write(json.dumps(dict(r)) + "\n")
        with self._conn:
            # append-only triggers guard the live table; drop+recreate around rotation.
            self._conn.execute("DROP TRIGGER IF EXISTS trg_audit_no_delete")
            self._conn.execute("DROP TRIGGER IF EXISTS trg_audit_no_update")
            for r in drop:
                self._conn.execute("DELETE FROM audit WHERE id = ?", (r["id"],))
            # rebind the new tail so the chain stays unbroken (while triggers are down).
            tail = self._conn.execute(
                "SELECT id, at, action, subject, detail, prev_hash FROM audit"
                " ORDER BY id ASC").fetchall()
            prev = "genesis"
            for r in tail:
                h = _audit_hash(r["at"], r["action"], r["subject"], r["detail"], prev)
                if r["prev_hash"] != h:
                    self._conn.execute(
                        "UPDATE audit SET prev_hash = ? WHERE id = ?", (h, r["id"]))
                prev = h
            self._conn.execute(
                "CREATE TRIGGER IF NOT EXISTS trg_audit_no_update BEFORE UPDATE ON audit"
                " BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;")
            self._conn.execute(
                "CREATE TRIGGER IF NOT EXISTS trg_audit_no_delete BEFORE DELETE ON audit"
                " BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END;")

    def verify_audit(self) -> List[dict]:
        """Recompute the hash chain; return every row that breaks it (FR-11.5)."""
        bad: List[dict] = []
        prev = "genesis"
        for r in self._conn.execute(
                "SELECT id, at, action, subject, detail, prev_hash FROM audit"
                " ORDER BY id ASC").fetchall():
            expect = _audit_hash(r["at"], r["action"], r["subject"], r["detail"], prev)
            if r["prev_hash"] != expect:
                bad.append({"id": r["id"], "expected": expect,
                            "found": r["prev_hash"], "prev_ok": prev != "genesis"})
                prev = r["prev_hash"]
            else:
                prev = expect
        return bad

    def query_audit(self, limit: int = 50, action: Optional[str] = None) -> List[dict]:
        sql = "SELECT id, at, action, subject, detail, prev_hash FROM audit"
        if action:
            sql += " WHERE action = ?"
        sql += " ORDER BY id DESC LIMIT ?"
        params: List[object] = []
        if action:
            params.append(action)
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------- claims
    def store_claim(self, text: str, source: str = "user", trust: float = 1.0,
                    kind: str = "core") -> int:
        text = text.strip()
        cur = self._conn.execute(
            "INSERT INTO claim(text, source, trust, ts, kind) VALUES (?, ?, ?, ?, ?)",
            (text, source, trust, _now(), kind),
        )
        cid = cur.lastrowid
        seen = set()
        for term in set(_tokenize(text)):
            if term not in seen:
                seen.add(term)
                self._conn.execute(
                    "INSERT OR IGNORE INTO term(term, claim_id) VALUES (?, ?)", (term, cid)
                )
        self.audit("claim_store", str(cid), text[:200])
        self._conn.commit()
        return cid

    def store_many(self, claims: List[dict]) -> List[int]:
        return [self.store_claim(**c) for c in claims]

    def count_claims(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM claim").fetchone()
        return int(row["n"])

    def recent(self, limit: int = 10) -> List[dict]:
        rows = self._conn.execute(
            "SELECT * FROM claim ORDER BY claim_id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_claim(self, claim_id: int) -> Optional[dict]:
        row = self._conn.execute(
            "SELECT * FROM claim WHERE claim_id = ?", (claim_id,)
        ).fetchone()
        return dict(row) if row else None

    def all_tokens_by_claim(self) -> Dict[int, set]:
        rows = self._conn.execute("SELECT term, claim_id FROM term").fetchall()
        out: Dict[int, set] = {}
        for r in rows:
            out.setdefault(r["claim_id"], set()).add(r["term"])
        return out

    # ------------------------------------------------------------- recall
    def recall(self, query: str, min_trust: float = 0.0, limit: int = 5) -> List[dict]:
        q_terms = set(_tokenize(query))
        if not q_terms:
            return []
        tok = self.all_tokens_by_claim()
        claims = {}
        for row in self._conn.execute(
            "SELECT * FROM claim WHERE trust >= ?", (min_trust,)
        ).fetchall():
            claims[row["claim_id"]] = dict(row)
        scored = []
        for cid, cl in claims.items():
            overlap = len(q_terms & tok.get(cid, set()))
            if overlap:
                scored.append((overlap, cl))
        scored.sort(key=lambda pair: (-pair[0], -pair[1]["trust"]))
        return [cl for (_, cl) in scored[:limit]]

    # ------------------------------------------------------------- edges
    def add_edge(self, src: int, rel: str, dst: int) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO edge(src, rel, dst) VALUES (?, ?, ?)",
                (src, rel, dst),
            )
        self.audit("edge_add", f"{src} -{rel}-> {dst}", "")

    def edges_of(self, claim_id: int) -> List[dict]:
        rows = self._conn.execute(
            "SELECT * FROM edge WHERE src = ?", (claim_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------- erase
    def erase_all(self) -> int:
        counts = {}
        for table in ("edge", "term", "claim", "persona_signal", "persona_anchor"):
            row = self._conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
            counts[table] = int(row["n"])
            self._conn.execute(f"DELETE FROM {table}")
        self.audit("erase_all", "brain", json.dumps(counts))
        self._conn.commit()
        return sum(counts.values())

    def export_json(self, path: str) -> int:
        claims = []
        rows = self._conn.execute("SELECT * FROM claim").fetchall()
        for r in rows:
            d = dict(r)
            d["edges"] = self.edges_of(d["claim_id"])
            claims.append(d)
        payload = {"exported_at": _now(), "claims": claims}
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        self.audit("export", path, f"{len(claims)} claims")
        return len(claims)

    # ------------------------------------------------------------- profile
    def get_setting(self, key: str, default: str = "") -> str:
        row = self._conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
                (key, value),
            )
        self.audit("setting_set", key, value)

    def compact(self) -> None:
        """Delete ephemeral claims older than 90 days (FR data retention)."""
        cutoff = datetime.now(timezone.utc).timestamp() - 90 * 86400
        rows = self._conn.execute(
            "SELECT claim_id FROM claim WHERE kind = 'ephemeral'"
        ).fetchall()
        removed = 0
        for r in rows:
            cl = self.get_claim(r["claim_id"])
            try:
                ts = datetime.fromisoformat(cl["ts"]).timestamp()
            except (ValueError, TypeError):
                continue
            if ts < cutoff:
                self._conn.execute("DELETE FROM term WHERE claim_id = ?", (r["claim_id"],))
                self._conn.execute("DELETE FROM edge WHERE src = ? OR dst = ?", (r["claim_id"], r["claim_id"]))
                self._conn.execute("DELETE FROM claim WHERE claim_id = ?", (r["claim_id"],))
                removed += 1
        if removed:
            self.audit("compact", "ephemeral", f"{removed} claims removed")
            self._conn.commit()
        return removed
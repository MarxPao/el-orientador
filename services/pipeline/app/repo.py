"""Persistence behind a small interface: in-memory for tests, PostgreSQL for real use."""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from typing import Protocol

from . import search as _search


class EmailTaken(Exception):
    pass


class DocumentExists(Exception):
    """Same DOI already in the project."""


class EdgeExists(Exception):
    """The concept pair already has an edge with that relation."""


EDGE_FIELDS = {"status", "relation", "user_note"}


class Repo(Protocol):
    def create_user(self, email: str, name: str | None, password_hash: str) -> dict: ...
    def get_user_by_email(self, email: str) -> dict | None: ...
    def get_user(self, user_id: str) -> dict | None: ...
    def create_project(self, owner_id: str, data: dict) -> dict: ...
    def list_projects(self, owner_id: str) -> list[dict]: ...
    def get_project(self, owner_id: str, project_id: str) -> dict | None: ...
    def get_project_by_id(self, project_id: str) -> dict | None: ...
    def create_document(self, project_id: str, data: dict) -> dict: ...
    def list_documents(self, project_id: str) -> list[dict]: ...
    def get_document(self, document_id: str) -> dict | None: ...
    def update_document(self, document_id: str, **fields) -> None: ...
    def save_pages(self, document_id: str, pages: list[str], sources: list[str] | None = None) -> None: ...
    def get_pages(self, document_id: str) -> list[str]: ...
    def add_claims(self, document_id: str, claims: list[dict], model: str | None, prompt_version: str | None) -> int: ...
    def list_claims(self, document_id: str) -> list[dict]: ...
    def list_project_claims(self, project_id: str) -> list[dict]: ...
    def list_concepts(self, project_id: str) -> list[dict]: ...
    def list_edges(self, project_id: str) -> list[dict]: ...
    def add_edges(self, project_id: str, edges: list[dict]) -> list[dict]: ...
    def get_edge_evidence(self, project_id: str, edge_id: str) -> list[dict] | None: ...
    def update_edge(self, project_id: str, edge_id: str, **fields) -> dict | None: ...
    def list_gaps(self, project_id: str) -> list[dict]: ...
    def add_gaps(self, project_id: str, gaps: list[dict]) -> list[dict]: ...
    def get_gap(self, project_id: str, gap_id: str) -> dict | None: ...
    def update_gap(self, project_id: str, gap_id: str, **fields) -> dict | None: ...
    def get_progress_nodes(self, project_id: str) -> list[dict]: ...
    def save_progress_nodes(self, project_id: str, nodes: list[dict]) -> list[dict]: ...
    def get_progress_node(self, project_id: str, node_key: str) -> dict | None: ...
    def update_progress_node(self, project_id: str, node_key: str, **fields) -> dict | None: ...
    def save_gate_attempt(self, progress_node_id: str, transcript: list[dict], rubric_scores: dict | None,
                          outcome: str) -> dict: ...
    def list_gate_attempts(self, progress_node_id: str) -> list[dict]: ...
    def log_ai_usage(self, project_id: str, action: str, target_ref: str | None, model: str | None,
                     prompt_version: str | None) -> None: ...
    def list_ai_usage(self, project_id: str) -> list[dict]: ...
    def list_sections(self, project_id: str) -> list[dict]: ...
    def create_section(self, project_id: str, title: str, parent_id: str | None, position: int,
                       content: dict | None = None) -> dict: ...
    def get_section(self, project_id: str, section_id: str) -> dict | None: ...
    def update_section(self, project_id: str, section_id: str, **fields) -> dict | None: ...
    def delete_section(self, project_id: str, section_id: str) -> bool: ...
    def set_section_concepts(self, section_id: str, concept_ids: list[str]) -> None: ...
    def get_section_concepts(self, section_id: str) -> list[str]: ...
    def invite_advisor(self, project_id: str, advisor_email: str, can_comment: bool = True) -> dict: ...
    def list_advisors(self, project_id: str) -> list[dict]: ...
    def remove_advisor(self, project_id: str, advisor_email: str) -> bool: ...
    def list_advising_projects(self, advisor_email: str) -> list[dict]: ...
    def is_advisor(self, project_id: str, email: str) -> bool: ...
    def create_advisor_report(self, project_id: str, payload: dict, period_start: date | None = None,
                              period_end: date | None = None) -> dict: ...
    def list_advisor_reports(self, project_id: str) -> list[dict]: ...
    def get_advisor_report(self, project_id: str, report_id: str) -> dict | None: ...
    def create_section_comment(self, section_id: str, author_email: str, author_name: str | None,
                               content: str) -> dict: ...
    def list_section_comments(self, section_id: str) -> list[dict]: ...
    def update_section_comment(self, comment_id: str, **fields) -> dict | None: ...
    def delete_section_comment(self, comment_id: str) -> bool: ...
    def get_section_comment(self, section_id: str, comment_id: str) -> dict | None: ...
    def delete_document(self, project_id: str, document_id: str) -> dict | None: ...
    def list_section_versions(self, project_id: str, section_id: str) -> list[dict]: ...
    def get_section_version(self, project_id: str, section_id: str, version_id: str) -> dict | None: ...
    def add_node_feedback(self, project_id: str, node_key: str, advisor_email: str, advisor_name: str | None,
                          content: str) -> dict: ...
    def list_node_feedback(self, project_id: str, node_key: str) -> list[dict]: ...
    def add_provenance_event(self, project_id: str, section_id: str, kind: str, source: str, words: int,
                             text: str | None, meta: dict | None, created_by: str | None) -> dict: ...
    def list_provenance_events(self, project_id: str, section_id: str | None = None) -> list[dict]: ...
    def declare_provenance_event(self, project_id: str, event_id: str, declared: str | None) -> dict | None: ...
    def replace_chunks(self, document_id: str, chunks: list[dict]) -> int: ...
    def chunks_to_embed(self, document_id: str, model: str, limit: int) -> list[dict]: ...
    def save_embeddings(self, items: list[tuple[str, list[float]]], model: str) -> None: ...
    def chunk_stats(self, project_id: str, model: str | None) -> dict: ...
    def search_keyword(self, project_id: str, query: str, limit: int) -> list[dict]: ...
    def search_vector(self, project_id: str, vector: list[float], model: str, limit: int) -> list[dict]: ...
    def add_error_event(self, source: str, error_type: str, message: str, stack: str | None, route: str | None,
                        request_id: str | None, user_id: str | None) -> dict: ...
    def list_error_events(self, limit: int = 100) -> list[dict]: ...
    def purge_error_events(self, older_than_days: int) -> int: ...
    def get_beta_metrics(self) -> dict: ...


VERSION_MIN_INTERVAL_SECONDS = 300  # autosaves inside this window share one restore point
VERSION_KEEP = 50                   # restore points kept per section


def _count_words(content) -> int:
    """Words in a TipTap JSON document (or plain string)."""
    if isinstance(content, str):
        return len(content.split())
    n = 0
    if isinstance(content, dict):
        if content.get("type") == "text":
            n += len(str(content.get("text", "")).split())
        for child in content.get("content") or []:
            n += _count_words(child)
    return n


def _has_text(content) -> bool:
    return _count_words(content) > 0


def _split_version_kwargs(fields: dict) -> tuple[dict, str | None, bool]:
    """`version_by` and `force_version` steer the restore-point snapshot; they are not section columns."""
    fields = dict(fields)
    by = fields.pop("version_by", None)
    force = bool(fields.pop("force_version", False))
    return fields, by, force


class UnverifiedClaim(ValueError):
    """Raised when someone tries to persist a claim whose quote was not verified (AGENTS.md rule 1)."""


class InMemoryRepo:
    def __init__(self) -> None:
        self.users: dict[str, dict] = {}
        self.projects: dict[str, dict] = {}
        self.documents: dict[str, dict] = {}
        self.pages: dict[str, list[str]] = {}
        self.page_sources: dict[str, list[str]] = {}
        self.concepts: dict[tuple[str, str], str] = {}
        self.concept_labels: dict[str, str] = {}
        self.edges: list[dict] = []
        self.gaps: list[dict] = []
        self.progress_nodes: dict[tuple[str, str], dict] = {}
        self.gate_attempts: list[dict] = []
        self.claims: list[dict] = []
        self.sections: list[dict] = []
        self.section_concepts: dict[str, set[str]] = {}
        self.advisors: list[dict] = []
        self.advisor_reports: list[dict] = []
        self.section_comments: list[dict] = []
        self.section_versions: list[dict] = []
        self.node_feedback: list[dict] = []
        self.chunks: list[dict] = []
        self.provenance: list[dict] = []
        self.error_events: list[dict] = []
        self.ai_usage: list[dict] = []

    def get_document(self, document_id):
        return self.documents.get(document_id)

    def update_document(self, document_id, **fields):
        self.documents[document_id].update(fields)

    def save_pages(self, document_id, pages, sources=None):
        self.pages[document_id] = list(pages)
        self.page_sources[document_id] = list(sources) if sources else ["native"] * len(pages)

    def get_pages(self, document_id):
        return list(self.pages.get(document_id, []))

    def add_claims(self, document_id, claims, model, prompt_version):
        if not all(c.get("quote_verified") for c in claims):
            raise UnverifiedClaim("Só claims com citação verificada podem ser salvos.")
        project_id = self.documents[document_id]["project_id"]
        for c in claims:
            key = (project_id, c["concept"].strip().casefold())
            concept_id = self.concepts.setdefault(key, str(uuid.uuid4()))
            self.concept_labels.setdefault(concept_id, c["concept"].strip())
            self.claims.append({"id": str(uuid.uuid4()), "document_id": document_id, "concept_id": concept_id,
                                "concept": c["concept"], "statement": c["statement"], "quote": c["quote"],
                                "page_no": c["page_verified"], "char_start": c.get("char_start"),
                                "char_end": c.get("char_end"), "quote_verified": True,
                                "verify_method": c["verify_method"], "scope": c.get("scope") or {},
                                "certainty": c.get("certainty", "desconhecido"),
                                "prompt_version": prompt_version, "model": model})
        return len(claims)

    def list_claims(self, document_id):
        return [c for c in self.claims if c["document_id"] == document_id]

    def list_project_claims(self, project_id):
        doc_ids = {d["id"] for d in self.documents.values() if d["project_id"] == project_id}
        return [c for c in self.claims if c["document_id"] in doc_ids]

    def list_concepts(self, project_id):
        out = []
        for (pid, _), cid in self.concepts.items():
            if pid == project_id:
                n = sum(1 for c in self.list_project_claims(project_id) if c["concept_id"] == cid)
                out.append({"id": cid, "label": self.concept_labels[cid], "n_claims": n})
        return out

    def get_edge_evidence(self, project_id, edge_id):
        edge = next((e for e in self.edges if e["id"] == edge_id and e["project_id"] == project_id), None)
        if not edge:
            return None
        out = []
        for ev in edge["evidence"]:
            c = next(c for c in self.claims if c["id"] == ev["claim_id"])
            out.append({"side": ev["side"], "claim_id": c["id"], "document_id": c["document_id"],
                        "concept": c["concept"], "statement": c["statement"], "quote": c["quote"],
                        "page_no": c["page_no"], "char_start": c.get("char_start"), "char_end": c.get("char_end")})
        return out

    def update_edge(self, project_id, edge_id, **fields):
        if not fields or not set(fields) <= EDGE_FIELDS:
            raise ValueError(f"Campos não permitidos: {set(fields) - EDGE_FIELDS}")
        edge = next((e for e in self.edges if e["id"] == edge_id and e["project_id"] == project_id), None)
        if not edge:
            return None
        new_relation = fields.get("relation", edge["relation"])
        if any(x is not edge and x["project_id"] == project_id and x["source_concept"] == edge["source_concept"]
               and x["target_concept"] == edge["target_concept"] and x["relation"] == new_relation for x in self.edges):
            raise EdgeExists(new_relation)
        edge.update(fields)
        edge["decided_at"] = "now"
        return edge

    def list_edges(self, project_id):
        return [e for e in self.edges if e["project_id"] == project_id]

    def add_edges(self, project_id, edges):
        created = []
        for e in edges:
            key = (project_id, e["source_concept"], e["target_concept"], e["relation"])
            if any((x["project_id"], x["source_concept"], x["target_concept"], x["relation"]) == key for x in self.edges):
                continue
            row = {"id": str(uuid.uuid4()), "project_id": project_id, **e}
            self.edges.append(row)
            created.append(row)
        return created

    def list_gaps(self, project_id):
        return [g for g in self.gaps if g["project_id"] == project_id]

    def add_gaps(self, project_id, gaps):
        created = []
        for g in gaps:
            pair = frozenset((g["concept_a"], g["concept_b"]))
            if any(x["project_id"] == project_id and frozenset((x["concept_a"], x["concept_b"])) == pair for x in self.gaps):
                continue
            row = {"id": str(uuid.uuid4()), "project_id": project_id, **g}
            self.gaps.append(row)
            created.append(row)
        return created

    def get_gap(self, project_id, gap_id):
        return next((g for g in self.gaps if g["id"] == gap_id and g["project_id"] == project_id), None)

    def update_gap(self, project_id, gap_id, **fields):
        gap = self.get_gap(project_id, gap_id)
        if gap:
            gap.update(fields)
        return gap

    def get_progress_nodes(self, project_id):
        return [n for (pid, _), n in self.progress_nodes.items() if pid == project_id]

    def save_progress_nodes(self, project_id, nodes):
        saved = []
        for n in nodes:
            key = (project_id, n["node_key"])
            existing = self.progress_nodes.get(key)
            if existing:
                existing.update(n)
                saved.append(existing)
            else:
                row = {"id": str(uuid.uuid4()), "project_id": project_id, **n}
                self.progress_nodes[key] = row
                saved.append(row)
        return saved

    def get_progress_node(self, project_id, node_key):
        return self.progress_nodes.get((project_id, node_key))

    def update_progress_node(self, project_id, node_key, **fields):
        node = self.get_progress_node(project_id, node_key)
        if node:
            node.update(fields)
        return node

    def save_gate_attempt(self, progress_node_id, transcript, rubric_scores, outcome):
        attempt = {
            "id": str(uuid.uuid4()),
            "progress_node_id": progress_node_id,
            "transcript": transcript,
            "rubric_scores": rubric_scores,
            "outcome": outcome,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.gate_attempts.append(attempt)
        return attempt

    def list_gate_attempts(self, progress_node_id):
        return [a for a in self.gate_attempts if a["progress_node_id"] == progress_node_id]

    def log_ai_usage(self, project_id, action, target_ref, model, prompt_version):
        self.ai_usage.append({"project_id": project_id, "action": action, "target_ref": target_ref,
                              "model": model, "prompt_version": prompt_version,
                              "created_at": datetime.now(timezone.utc).isoformat()})

    def list_ai_usage(self, project_id):
        return [a for a in self.ai_usage if a["project_id"] == project_id]

    def list_sections(self, project_id):
        secs = [s for s in self.sections if s["project_id"] == project_id]
        secs.sort(key=lambda s: s.get("position", 0))
        out = []
        for s in secs:
            cids = list(self.section_concepts.get(s["id"], set()))
            out.append({**s, "concept_ids": cids})
        return out

    def create_section(self, project_id, title, parent_id, position, content=None):
        now = datetime.now(timezone.utc).isoformat()
        sec = {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "parent_id": parent_id,
            "title": title,
            "position": position,
            "content": content or {},
            "concept_ids": [],
            "updated_at": now,
        }
        self.sections.append(sec)
        return sec

    def get_section(self, project_id, section_id):
        sec = next((s for s in self.sections if s["id"] == section_id and s["project_id"] == project_id), None)
        if not sec:
            return None
        cids = list(self.section_concepts.get(sec["id"], set()))
        return {**sec, "concept_ids": cids}

    def update_section(self, project_id, section_id, **fields):
        fields, by, force = _split_version_kwargs(fields)
        sec = next((s for s in self.sections if s["id"] == section_id and s["project_id"] == project_id), None)
        if not sec:
            return None
        allowed = {"title", "parent_id", "position", "content"}
        if "content" in fields and fields["content"] != sec.get("content") and _has_text(sec.get("content")):
            self._snapshot(sec, by, force)
        for k, v in fields.items():
            if k in allowed:
                sec[k] = v
        sec["updated_at"] = datetime.now(timezone.utc).isoformat()
        cids = list(self.section_concepts.get(sec["id"], set()))
        return {**sec, "concept_ids": cids}

    def _snapshot(self, sec, by, force):
        """Save the content that is about to be replaced. Autosaves within the interval share one point."""
        mine = [v for v in self.section_versions if v["section_id"] == sec["id"]]
        now = datetime.now(timezone.utc)
        if mine and not force:
            last = datetime.fromisoformat(mine[-1]["created_at"])
            if (now - last).total_seconds() < VERSION_MIN_INTERVAL_SECONDS:
                return
        if mine and mine[-1]["content_snapshot"] == sec.get("content"):
            return
        self.section_versions.append({
            "id": str(uuid.uuid4()), "section_id": sec["id"], "content_snapshot": json.loads(json.dumps(sec.get("content") or {})),
            "word_count": _count_words(sec.get("content")), "created_at": now.isoformat(), "created_by": by,
        })
        extra = [v for v in self.section_versions if v["section_id"] == sec["id"]][:-VERSION_KEEP]
        if extra:
            drop = {v["id"] for v in extra}
            self.section_versions = [v for v in self.section_versions if v["id"] not in drop]

    def list_section_versions(self, project_id, section_id):
        if not any(s["id"] == section_id and s["project_id"] == project_id for s in self.sections):
            return []
        return [dict(v) for v in reversed([v for v in self.section_versions if v["section_id"] == section_id])]

    def get_section_version(self, project_id, section_id, version_id):
        if not any(s["id"] == section_id and s["project_id"] == project_id for s in self.sections):
            return None
        v = next((v for v in self.section_versions if v["id"] == version_id and v["section_id"] == section_id), None)
        return dict(v) if v else None

    def add_node_feedback(self, project_id, node_key, advisor_email, advisor_name, content):
        f = {"id": str(uuid.uuid4()), "project_id": project_id, "node_key": node_key,
             "advisor_email": advisor_email.strip().lower(), "advisor_name": advisor_name, "content": content,
             "created_at": datetime.now(timezone.utc).isoformat()}
        self.node_feedback.append(f)
        return dict(f)

    def list_node_feedback(self, project_id, node_key):
        return [dict(f) for f in self.node_feedback if f["project_id"] == project_id and f["node_key"] == node_key]

    # ------------------------------------------------------------------ provenance ledger
    def add_provenance_event(self, project_id, section_id, kind, source, words, text, meta, created_by):
        if not any(x["id"] == section_id and x["project_id"] == project_id for x in self.sections):
            raise ValueError("section not in project")
        e = {"id": str(uuid.uuid4()), "project_id": project_id, "section_id": section_id, "kind": kind,
             "source": source, "words": words, "text": text, "meta": dict(meta or {}), "declared": None,
             "created_by": created_by, "created_at": datetime.now(timezone.utc).isoformat()}
        self.provenance.append(e)
        return dict(e)

    def list_provenance_events(self, project_id, section_id=None):
        return [dict(e) for e in self.provenance
                if e["project_id"] == project_id and (section_id is None or e["section_id"] == section_id)]

    def declare_provenance_event(self, project_id, event_id, declared):
        e = next((e for e in self.provenance if e["id"] == event_id and e["project_id"] == project_id
                  and e["kind"] == "paste"), None)
        if not e:
            return None
        e["declared"] = declared
        return dict(e)

    # ------------------------------------------------------------------ local error log
    def add_error_event(self, source, error_type, message, stack, route, request_id, user_id):
        from datetime import datetime, timezone

        e = {"id": str(uuid.uuid4()), "source": source, "error_type": error_type, "message": message, "stack": stack,
             "route": route, "request_id": request_id, "user_id": user_id,
             "created_at": datetime.now(timezone.utc).isoformat()}
        self.error_events.append(e)
        return dict(e)

    def list_error_events(self, limit=100):
        return [dict(e) for e in reversed(self.error_events)][:limit]

    def purge_error_events(self, older_than_days):
        from datetime import datetime, timedelta, timezone

        cut = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
        keep = [e for e in self.error_events if e["created_at"] >= cut]
        n = len(self.error_events) - len(keep)
        self.error_events = keep
        return n

    # ------------------------------------------------------------------ passage index
    def replace_chunks(self, document_id, chunks):
        project_id = self.documents[document_id]["project_id"]
        self.chunks = [c for c in self.chunks if c["document_id"] != document_id]
        for c in chunks:
            self.chunks.append({"id": str(uuid.uuid4()), "document_id": document_id, "project_id": project_id,
                                "chunk_no": c["chunk_no"], "page_no": c["page_no"], "text": c["text"],
                                "search_text": c["search_text"], "embedding": None, "embedding_model": None})
        return len(chunks)

    def chunks_to_embed(self, document_id, model, limit):
        return [{"id": c["id"], "text": c["text"]} for c in self.chunks
                if c["document_id"] == document_id and c["embedding_model"] != model][:limit]

    def save_embeddings(self, items, model):
        by_id = {c["id"]: c for c in self.chunks}
        for cid, vec in items:
            if cid in by_id:
                by_id[cid]["embedding"], by_id[cid]["embedding_model"] = list(vec), model

    def chunk_stats(self, project_id, model):
        mine = [c for c in self.chunks if c["project_id"] == project_id]
        return {"chunks": len(mine), "embedded": sum(1 for c in mine if model and c["embedding_model"] == model)}

    @staticmethod
    def _hit(c, score):
        return {"id": c["id"], "document_id": c["document_id"], "page_no": c["page_no"], "text": c["text"],
                "score": score}

    def search_keyword(self, project_id, query, limit):
        mine = [c for c in self.chunks if c["project_id"] == project_id]
        return [self._hit(c, s) for c, s in _search.bm25_rank(query, mine)[:limit]]

    def search_vector(self, project_id, vector, model, limit):
        scored = [(c, _search.cosine(vector, c["embedding"])) for c in self.chunks
                  if c["project_id"] == project_id and c["embedding_model"] == model and c["embedding"]]
        scored.sort(key=lambda x: -x[1])
        return [self._hit(c, s) for c, s in scored[:limit]]

    def get_section_comment(self, section_id, comment_id):
        c = next((c for c in self.section_comments if c["id"] == comment_id and c["section_id"] == section_id), None)
        return dict(c) if c else None

    def delete_document(self, project_id, document_id):
        """Remove a document and everything derived from it. Returns the removed row (for the stored file path)."""
        doc = self.documents.get(document_id)
        if not doc or doc["project_id"] != project_id:
            return None
        gone = {c["id"] for c in self.claims if c["document_id"] == document_id}
        self.claims = [c for c in self.claims if c["document_id"] != document_id]
        for e in self.edges:
            e["evidence"] = [ev for ev in e.get("evidence", []) if ev["claim_id"] not in gone]
        self.pages.pop(document_id, None)
        self.page_sources.pop(document_id, None)
        self.chunks = [c for c in self.chunks if c["document_id"] != document_id]
        del self.documents[document_id]
        return doc

    def delete_section(self, project_id, section_id):
        to_del = {section_id}
        # delete children recursively
        found = True
        while found:
            found = False
            for s in self.sections:
                if s["project_id"] == project_id and s.get("parent_id") in to_del and s["id"] not in to_del:
                    to_del.add(s["id"])
                    found = True
        self.sections = [s for s in self.sections if s["id"] not in to_del]
        self.provenance = [e for e in self.provenance if e["section_id"] not in to_del]
        self.section_versions = [v for v in self.section_versions if v["section_id"] not in to_del]
        for sid in to_del:
            self.section_concepts.pop(sid, None)
        return True

    def set_section_concepts(self, section_id, concept_ids):
        self.section_concepts[section_id] = set(concept_ids)

    def get_section_concepts(self, section_id):
        return list(self.section_concepts.get(section_id, set()))

    def invite_advisor(self, project_id, advisor_email, can_comment=True):
        email = advisor_email.strip().lower()
        existing = next((a for a in self.advisors if a["project_id"] == project_id and a["advisor_email"] == email), None)
        if existing:
            existing["can_comment"] = can_comment
            return existing
        adv = {
            "project_id": project_id,
            "advisor_email": email,
            "can_comment": can_comment,
            "invited_at": datetime.now(timezone.utc).isoformat(),
        }
        self.advisors.append(adv)
        return adv

    def list_advisors(self, project_id):
        return [a for a in self.advisors if a["project_id"] == project_id]

    def remove_advisor(self, project_id, advisor_email):
        email = advisor_email.strip().lower()
        self.advisors = [a for a in self.advisors if not (a["project_id"] == project_id and a["advisor_email"] == email)]
        return True

    def list_advising_projects(self, advisor_email):
        email = advisor_email.strip().lower()
        pids = {a["project_id"] for a in self.advisors if a["advisor_email"] == email}
        return [p for p in self.projects.values() if p["id"] in pids]

    def is_advisor(self, project_id, email):
        em = email.strip().lower()
        return any(a["project_id"] == project_id and a["advisor_email"] == em for a in self.advisors)

    def create_advisor_report(self, project_id, payload, period_start=None, period_end=None):
        rep = {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "period_start": period_start.isoformat() if hasattr(period_start, "isoformat") else period_start,
            "period_end": period_end.isoformat() if hasattr(period_end, "isoformat") else period_end,
            "payload": payload,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.advisor_reports.append(rep)
        return rep

    def list_advisor_reports(self, project_id):
        return [r for r in self.advisor_reports if r["project_id"] == project_id]

    def get_advisor_report(self, project_id, report_id):
        return next((r for r in self.advisor_reports if r["id"] == report_id and r["project_id"] == project_id), None)

    def create_section_comment(self, section_id, author_email, author_name, content):
        c = {
            "id": str(uuid.uuid4()),
            "section_id": section_id,
            "author_email": author_email.strip().lower(),
            "author_name": author_name,
            "content": content,
            "resolved": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.section_comments.append(c)
        return c

    def list_section_comments(self, section_id):
        return [c for c in self.section_comments if c["section_id"] == section_id]

    def update_section_comment(self, comment_id, **fields):
        c = next((c for c in self.section_comments if c["id"] == comment_id), None)
        if not c:
            return None
        allowed = {"resolved", "content"}
        for k, v in fields.items():
            if k in allowed:
                c[k] = v
        return c

    def delete_section_comment(self, comment_id):
        self.section_comments = [c for c in self.section_comments if c["id"] != comment_id]
        return True

    def create_document(self, project_id, data):
        if data.get("doi") and any(
            d["project_id"] == project_id and d["doi"] == data["doi"] for d in self.documents.values()
        ):
            raise DocumentExists(data["doi"])
        d = {"id": str(uuid.uuid4()), "project_id": project_id, **data}
        self.documents[d["id"]] = d
        return d

    def list_documents(self, project_id):
        return [d for d in self.documents.values() if d["project_id"] == project_id]

    def create_user(self, email, name, password_hash):
        email = email.lower()
        if self.get_user_by_email(email):
            raise EmailTaken(email)
        u = {"id": str(uuid.uuid4()), "email": email, "name": name, "password_hash": password_hash}
        self.users[u["id"]] = u
        return u

    def get_user_by_email(self, email):
        return next((u for u in self.users.values() if u["email"] == email.lower()), None)

    def get_user(self, user_id):
        return self.users.get(user_id)

    def create_project(self, owner_id, data):
        p = {"id": str(uuid.uuid4()), "owner_id": owner_id, **data}
        self.projects[p["id"]] = p
        return p

    def list_projects(self, owner_id):
        return [p for p in self.projects.values() if p["owner_id"] == owner_id]

    def get_project(self, owner_id, project_id):
        p = self.projects.get(project_id)
        return p if p and p["owner_id"] == owner_id else None

    def get_project_by_id(self, project_id):
        return self.projects.get(project_id)

    def get_beta_metrics(self) -> dict:
        from collections import Counter
        total_students = len(self.users)
        total_projects = len(self.projects)
        by_work = Counter(p.get("work", "outro") for p in self.projects.values())

        doc_count_by_project = Counter(d["project_id"] for d in self.documents.values())
        activated_projects = sum(1 for count in doc_count_by_project.values() if count >= 5)
        activation_rate = round(activated_projects / total_projects, 3) if total_projects else 0.0

        decisions = [e for e in self.edges if e.get("status") in ("confirmed", "rejected")]
        confirmed = sum(1 for e in decisions if e.get("status") == "confirmed")
        rejected = sum(1 for e in decisions if e.get("status") == "rejected")
        total_decisions = len(decisions)
        link_acceptance_rate = round(confirmed / total_decisions, 3) if total_decisions else 0.0

        total_attempts = len(self.gate_attempts)
        passed_attempts = sum(1 for a in self.gate_attempts if a.get("outcome") == "liberar")
        skipped_attempts = sum(1 for a in self.gate_attempts if a.get("outcome") == "pular")

        total_sections = len(self.sections)
        total_advisor_invites = len(self.advisors)
        total_advisor_comments = len(self.section_comments)
        total_reports_generated = len(self.advisor_reports)

        ai_by_action = Counter(l.get("action", "outro") for l in self.ai_usage)

        return {
            "students_registered": total_students,
            "projects_total": total_projects,
            "projects_by_work": dict(by_work),
            "activation": {
                "threshold_sources": 5,
                "activated_projects": activated_projects,
                "activation_rate": activation_rate,
            },
            "knowledge_map": {
                "total_edges": len(self.edges),
                "total_decisions": total_decisions,
                "confirmed": confirmed,
                "rejected": rejected,
                "acceptance_rate": link_acceptance_rate,
                "target_acceptance_rate": 0.50,
            },
            "socratic_gate": {
                "total_attempts": total_attempts,
                "passed": passed_attempts,
                "skipped_with_warning": skipped_attempts,
            },
            "manuscript_and_collaboration": {
                "total_sections": total_sections,
                "advisor_invites": total_advisor_invites,
                "advisor_comments": total_advisor_comments,
                "advisor_reports_generated": total_reports_generated,
            },
            "ai_usage": dict(ai_by_action),
            "pricing_validation": {
                "hypothesis_a": "Passe por projeto (R$ 89 a R$ 149)",
                "hypothesis_b": "Assinatura mensal (R$ 25 a R$ 50)",
                "cohort_target": "10 a 20 alunos",
            },
        }


_PROJECT_COLS = "id, owner_id, title, work, institution, citation_style, deadline, weekly_hours, research_problem"


def _project_row(row: tuple) -> dict:
    keys = _PROJECT_COLS.replace(" ", "").split(",")
    d = dict(zip(keys, row))
    d["id"], d["owner_id"] = str(d["id"]), str(d["owner_id"])
    if isinstance(d["deadline"], date):
        d["deadline"] = d["deadline"].isoformat()
    return d


class PostgresRepo:
    """Needs `db/schema.sql` + `db/migrations/*.sql` applied. Reads DATABASE_URL.

    NOT exercised by the automated tests (no Postgres in the dev sandbox); see tests/test_postgres_repo.py,
    which runs only when TEST_DATABASE_URL is set.
    """

    def __init__(self, dsn: str) -> None:
        self.dsn = dsn

    def _conn(self):
        import psycopg  # lazy: only needed with a real database

        return psycopg.connect(self.dsn)

    def create_user(self, email, name, password_hash):
        import psycopg.errors

        with self._conn() as c:
            try:
                row = c.execute(
                    "INSERT INTO users (email, name, password_hash) VALUES (%s, %s, %s) "
                    "RETURNING id, email, name, password_hash",
                    (email.lower(), name, password_hash),
                ).fetchone()
            except psycopg.errors.UniqueViolation:
                raise EmailTaken(email) from None
        return {"id": str(row[0]), "email": row[1], "name": row[2], "password_hash": row[3]}

    def _user(self, where: str, arg: str):
        with self._conn() as c:
            row = c.execute(f"SELECT id, email, name, password_hash FROM users WHERE {where}", (arg,)).fetchone()
        return None if not row else {"id": str(row[0]), "email": row[1], "name": row[2], "password_hash": row[3]}

    def get_user_by_email(self, email):
        return self._user("email = %s", email.lower())

    def get_user(self, user_id):
        return self._user("id = %s::uuid", user_id)

    def create_project(self, owner_id, data):
        with self._conn() as c:
            row = c.execute(
                f"INSERT INTO projects (owner_id, title, work, institution, citation_style, deadline, weekly_hours, "
                f"research_problem) VALUES (%s::uuid, %s, %s::work_type, %s, %s, %s, %s, %s) RETURNING {_PROJECT_COLS}",
                (owner_id, data["title"], data["work"], data.get("institution"), data["citation_style"],
                 data.get("deadline"), data.get("weekly_hours"), data.get("research_problem")),
            ).fetchone()
        return _project_row(row)

    def list_projects(self, owner_id):
        with self._conn() as c:
            rows = c.execute(
                f"SELECT {_PROJECT_COLS} FROM projects WHERE owner_id = %s::uuid ORDER BY created_at DESC", (owner_id,)
            ).fetchall()
        return [_project_row(r) for r in rows]

    def get_project(self, owner_id, project_id):
        try:
            uuid.UUID(project_id)
        except ValueError:
            return None
        with self._conn() as c:
            row = c.execute(
                f"SELECT {_PROJECT_COLS} FROM projects WHERE id = %s::uuid AND owner_id = %s::uuid",
                (project_id, owner_id),
            ).fetchone()
        return _project_row(row) if row else None

    def get_project_by_id(self, project_id):
        try:
            uuid.UUID(project_id)
        except ValueError:
            return None
        with self._conn() as c:
            row = c.execute(
                f"SELECT {_PROJECT_COLS} FROM projects WHERE id = %s::uuid",
                (project_id,),
            ).fetchone()
        return _project_row(row) if row else None

    _DOC_COLS = (
        "id, project_id, doi, title, authors, year, venue, metadata_source, retracted, storage_path, analysis, "
        "status, parse_quality, stage, progress, summary"
    )

    @staticmethod
    def _doc_row(row) -> dict:
        keys = PostgresRepo._DOC_COLS.replace(" ", "").split(",")
        d = dict(zip(keys, row))
        d["id"], d["project_id"] = str(d["id"]), str(d["project_id"])
        return d

    def create_document(self, project_id, data):
        import psycopg.errors
        from psycopg.types.json import Jsonb

        with self._conn() as c:
            try:
                row = c.execute(
                    f"INSERT INTO documents (project_id, doi, title, authors, year, venue, metadata_source, retracted, "
                    f"storage_path, analysis, status) VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, "
                    f"%s::analysis_depth, %s) RETURNING {self._DOC_COLS}",
                    (project_id, data.get("doi"), data["title"], Jsonb(data.get("authors", [])), data.get("year"),
                     data.get("venue"), data.get("metadata_source"), data.get("retracted", False),
                     data.get("storage_path"), data.get("analysis", "full_text"), data.get("status", "pending")),
                ).fetchone()
            except psycopg.errors.UniqueViolation:
                raise DocumentExists(data.get("doi")) from None
        return self._doc_row(row)

    def list_documents(self, project_id):
        with self._conn() as c:
            rows = c.execute(
                f"SELECT {self._DOC_COLS} FROM documents WHERE project_id = %s::uuid ORDER BY created_at DESC",
                (project_id,),
            ).fetchall()
        return [self._doc_row(r) for r in rows]

    def get_document(self, document_id):
        try:
            uuid.UUID(document_id)
        except ValueError:
            return None
        with self._conn() as c:
            row = c.execute(f"SELECT {self._DOC_COLS} FROM documents WHERE id = %s::uuid", (document_id,)).fetchone()
        return self._doc_row(row) if row else None

    def update_document(self, document_id, **fields):
        from psycopg.types.json import Jsonb

        allowed = {"status", "parse_quality", "analysis", "stage", "progress", "summary", "title", "authors", "year",
                   "metadata_source"}
        if not fields or not set(fields) <= allowed:
            raise ValueError(f"Campos não permitidos: {set(fields) - allowed}")
        sets = ", ".join(f"{k} = %s" for k in fields)
        values = [Jsonb(v) if k in ("progress", "summary", "authors") and v is not None else v for k, v in fields.items()]
        with self._conn() as c:
            c.execute(f"UPDATE documents SET {sets} WHERE id = %s::uuid", (*values, document_id))

    def save_pages(self, document_id, pages, sources=None):
        sources = sources or ["native"] * len(pages)
        with self._conn() as c:
            c.execute("DELETE FROM document_pages WHERE document_id = %s::uuid", (document_id,))
            with c.cursor() as cur:
                cur.executemany(
                    "INSERT INTO document_pages (document_id, page_no, text, source) "
                    "VALUES (%s::uuid, %s, %s, %s)",
                    [(document_id, i, t.replace("\x00", ""), src) for i, (t, src) in enumerate(zip(pages, sources), start=1)],
                )

    def get_pages(self, document_id):
        with self._conn() as c:
            rows = c.execute(
                "SELECT text FROM document_pages WHERE document_id = %s::uuid ORDER BY page_no", (document_id,)
            ).fetchall()
        return [r[0] for r in rows]

    def add_claims(self, document_id, claims, model, prompt_version):
        from psycopg.types.json import Jsonb

        if not all(c.get("quote_verified") for c in claims):
            raise UnverifiedClaim("Só claims com citação verificada podem ser salvos.")
        with self._conn() as c:
            project_id = c.execute(
                "SELECT project_id FROM documents WHERE id = %s::uuid", (document_id,)
            ).fetchone()[0]
            for cl in claims:
                label = cl["concept"].strip()
                row = c.execute(
                    "SELECT id FROM concepts WHERE project_id = %s AND lower(label) = lower(%s) AND merged_into IS NULL",
                    (project_id, label),
                ).fetchone()
                concept_id = row[0] if row else c.execute(
                    "INSERT INTO concepts (project_id, label) VALUES (%s, %s) RETURNING id", (project_id, label)
                ).fetchone()[0]
                c.execute(
                    "INSERT INTO claims (document_id, concept_id, statement, quote, page_no, char_start, char_end, "
                    "quote_verified, verify_method, scope, certainty, prompt_version, model) "
                    "VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, true, %s, %s, %s::certainty_level, %s, %s)",
                    (document_id, concept_id, cl["statement"], cl["quote"], cl["page_verified"], cl.get("char_start"),
                     cl.get("char_end"), cl["verify_method"], Jsonb(cl.get("scope") or {}),
                     cl.get("certainty", "desconhecido"), prompt_version, model),
                )
        return len(claims)

    def list_claims(self, document_id):
        with self._conn() as c:
            rows = c.execute(
                "SELECT cl.id, cl.document_id, cl.concept_id, co.label, cl.statement, cl.quote, cl.page_no, "
                "cl.verify_method, cl.scope, cl.certainty FROM claims cl LEFT JOIN concepts co ON co.id = cl.concept_id "
                "WHERE cl.document_id = %s::uuid ORDER BY cl.created_at", (document_id,),
            ).fetchall()
        keys = ["id", "document_id", "concept_id", "concept", "statement", "quote", "page_no", "verify_method",
                "scope", "certainty"]
        return [{**dict(zip(keys, r)), "id": str(r[0]), "document_id": str(r[1]),
                 "concept_id": str(r[2]) if r[2] else None, "quote_verified": True} for r in rows]

    def log_ai_usage(self, project_id, action, target_ref, model, prompt_version):
        with self._conn() as c:
            c.execute(
                "INSERT INTO ai_usage_log (project_id, action, target_ref, model, prompt_version) "
                "VALUES (%s::uuid, %s, %s, %s, %s)", (project_id, action, target_ref, model, prompt_version),
            )

    def list_project_claims(self, project_id):
        with self._conn() as c:
            rows = c.execute(
                "SELECT cl.id, cl.document_id, cl.concept_id, co.label, cl.statement, cl.quote, cl.page_no "
                "FROM claims cl JOIN documents d ON d.id = cl.document_id "
                "LEFT JOIN concepts co ON co.id = cl.concept_id "
                "WHERE d.project_id = %s::uuid AND cl.concept_id IS NOT NULL", (project_id,),
            ).fetchall()
        return [{"id": str(r[0]), "document_id": str(r[1]), "concept_id": str(r[2]), "concept": r[3],
                 "statement": r[4], "quote": r[5], "page_no": r[6], "quote_verified": True} for r in rows]

    def list_concepts(self, project_id):
        with self._conn() as c:
            rows = c.execute(
                "SELECT co.id, co.label, count(cl.id) FROM concepts co LEFT JOIN claims cl ON cl.concept_id = co.id "
                "WHERE co.project_id = %s::uuid AND co.merged_into IS NULL GROUP BY co.id, co.label "
                "ORDER BY co.label", (project_id,),
            ).fetchall()
        return [{"id": str(r[0]), "label": r[1], "n_claims": r[2]} for r in rows]

    def list_edges(self, project_id):
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, source_concept, target_concept, relation, status, confidence, rationale, "
                "display_by_default FROM edges WHERE project_id = %s::uuid", (project_id,),
            ).fetchall()
        keys = ["id", "source_concept", "target_concept", "relation", "status", "confidence", "rationale",
                "display_by_default"]
        return [{**dict(zip(keys, r)), "id": str(r[0]), "source_concept": str(r[1]), "target_concept": str(r[2]),
                 "relation": str(r[3]), "status": str(r[4])} for r in rows]

    def add_edges(self, project_id, edges):
        created = []
        with self._conn() as c:
            for e in edges:
                row = c.execute(
                    "INSERT INTO edges (project_id, source_concept, target_concept, relation, status, confidence, "
                    "rationale, display_by_default) VALUES (%s::uuid, %s::uuid, %s::uuid, %s::relation_type, "
                    "%s::edge_status, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING id",
                    (project_id, e["source_concept"], e["target_concept"], e["relation"], e["status"],
                     e["confidence"], e["rationale"], e["display_by_default"]),
                ).fetchone()
                if not row:
                    continue
                for ev in e["evidence"]:
                    c.execute("INSERT INTO edge_evidence (edge_id, claim_id, side) VALUES (%s, %s::uuid, %s)",
                              (row[0], ev["claim_id"], ev["side"]))
                created.append({"id": str(row[0]), "project_id": project_id, **e})
        return created

    def get_edge_evidence(self, project_id, edge_id):
        try:
            uuid.UUID(edge_id)
        except ValueError:
            return None
        with self._conn() as c:
            if not c.execute("SELECT 1 FROM edges WHERE id = %s::uuid AND project_id = %s::uuid",
                             (edge_id, project_id)).fetchone():
                return None
            rows = c.execute(
                "SELECT ev.side, cl.id, cl.document_id, co.label, cl.statement, cl.quote, cl.page_no, "
                "cl.char_start, cl.char_end FROM edge_evidence ev JOIN claims cl ON cl.id = ev.claim_id "
                "LEFT JOIN concepts co ON co.id = cl.concept_id WHERE ev.edge_id = %s::uuid", (edge_id,),
            ).fetchall()
        keys = ["side", "claim_id", "document_id", "concept", "statement", "quote", "page_no", "char_start", "char_end"]
        return [{**dict(zip(keys, r)), "claim_id": str(r[1]), "document_id": str(r[2])} for r in rows]

    def update_edge(self, project_id, edge_id, **fields):
        import psycopg.errors

        if not fields or not set(fields) <= EDGE_FIELDS:
            raise ValueError(f"Campos não permitidos: {set(fields) - EDGE_FIELDS}")
        try:
            uuid.UUID(edge_id)
        except ValueError:
            return None
        casts = {"status": "%s::edge_status", "relation": "%s::relation_type", "user_note": "%s"}
        sets = ", ".join(f"{k} = {casts[k]}" for k in fields) + ", decided_at = now()"
        with self._conn() as c:
            try:
                row = c.execute(
                    f"UPDATE edges SET {sets} WHERE id = %s::uuid AND project_id = %s::uuid "
                    "RETURNING id, source_concept, target_concept, relation, status, confidence, rationale, "
                    "display_by_default, user_note",
                    (*fields.values(), edge_id, project_id),
                ).fetchone()
            except psycopg.errors.UniqueViolation:
                raise EdgeExists(fields.get("relation")) from None
        if not row:
            return None
        return {"id": str(row[0]), "project_id": project_id, "source_concept": str(row[1]),
                "target_concept": str(row[2]), "relation": str(row[3]), "status": str(row[4]),
                "confidence": row[5], "rationale": row[6], "display_by_default": row[7], "user_note": row[8]}

    def list_gaps(self, project_id):
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, project_id, concept_a, concept_b, searches, found_links, note, status, created_at "
                "FROM gaps WHERE project_id = %s::uuid ORDER BY created_at DESC", (project_id,),
            ).fetchall()
        keys = ["id", "project_id", "concept_a", "concept_b", "searches", "found_links", "note", "status", "created_at"]
        return [{**dict(zip(keys, r)), "id": str(r[0]), "project_id": str(r[1]), "concept_a": str(r[2]),
                 "concept_b": str(r[3]), "created_at": r[8].isoformat() if hasattr(r[8], "isoformat") else str(r[8])}
                for r in rows]

    def add_gaps(self, project_id, gaps):
        from psycopg.types.json import Jsonb

        created = []
        with self._conn() as c:
            for g in gaps:
                row = c.execute(
                    "INSERT INTO gaps (project_id, concept_a, concept_b, searches, found_links, note, status) "
                    "VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s) RETURNING id, created_at",
                    (project_id, g["concept_a"], g["concept_b"], Jsonb(g["searches"]), Jsonb(g["found_links"]),
                     g.get("note"), g.get("status", "open")),
                ).fetchone()
                created.append({"id": str(row[0]), "project_id": project_id, **g,
                                "created_at": row[1].isoformat() if hasattr(row[1], "isoformat") else str(row[1])})
        return created

    def get_gap(self, project_id, gap_id):
        try:
            uuid.UUID(gap_id)
        except ValueError:
            return None
        with self._conn() as c:
            row = c.execute(
                "SELECT id, project_id, concept_a, concept_b, searches, found_links, note, status, created_at "
                "FROM gaps WHERE id = %s::uuid AND project_id = %s::uuid", (gap_id, project_id),
            ).fetchone()
        if not row:
            return None
        keys = ["id", "project_id", "concept_a", "concept_b", "searches", "found_links", "note", "status", "created_at"]
        return {**dict(zip(keys, row)), "id": str(row[0]), "project_id": str(row[1]), "concept_a": str(row[2]),
                "concept_b": str(row[3]),
                "created_at": row[8].isoformat() if hasattr(row[8], "isoformat") else str(row[8])}

    def update_gap(self, project_id, gap_id, **fields):
        allowed = {"status", "note"}
        if not fields or not set(fields) <= allowed:
            raise ValueError(f"Campos não permitidos: {set(fields) - allowed}")
        try:
            uuid.UUID(gap_id)
        except ValueError:
            return None
        sets = ", ".join(f"{k} = %s" for k in fields)
        with self._conn() as c:
            row = c.execute(
                f"UPDATE gaps SET {sets} WHERE id = %s::uuid AND project_id = %s::uuid "
                "RETURNING id, project_id, concept_a, concept_b, searches, found_links, note, status, created_at",
                (*fields.values(), gap_id, project_id),
            ).fetchone()
        if not row:
            return None
        keys = ["id", "project_id", "concept_a", "concept_b", "searches", "found_links", "note", "status", "created_at"]
        return {**dict(zip(keys, row)), "id": str(row[0]), "project_id": str(row[1]), "concept_a": str(row[2]),
                "concept_b": str(row[3]),
                "created_at": row[8].isoformat() if hasattr(row[8], "isoformat") else str(row[8])}

    def get_progress_nodes(self, project_id):
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, project_id, template_key, node_key, status, queued, skipped_reason, updated_at "
                "FROM progress_nodes WHERE project_id = %s::uuid ORDER BY node_key", (project_id,)
            ).fetchall()
        keys = ["id", "project_id", "template_key", "node_key", "status", "queued", "skipped_reason", "updated_at"]
        return [{**dict(zip(keys, r)), "id": str(r[0]), "project_id": str(r[1]), "status": str(r[4]),
                 "updated_at": r[7].isoformat() if hasattr(r[7], "isoformat") else str(r[7])} for r in rows]

    @staticmethod
    def _template_rows(keys: set[str]) -> list[tuple[str, int, str]]:
        """(key, version, definition-json) for each template the nodes refer to, read from app/templates/*.json."""
        from .tree import TEMPLATES_DIR

        found: dict[str, tuple[int, str]] = {}
        for f in TEMPLATES_DIR.glob("*.json"):
            t = json.loads(f.read_text(encoding="utf-8"))
            if t.get("key") in keys:
                found[t["key"]] = (int(t.get("version", 1)), json.dumps(t))
        return [(k, *found.get(k, (1, "{}"))) for k in sorted(keys)]

    def save_progress_nodes(self, project_id, nodes):
        saved = []
        with self._conn() as c:
            # progress_nodes.template_key is a foreign key and nothing else seeds progress_templates:
            # without this a fresh database fails on the first project's tree.
            for key, version, definition in self._template_rows({n["template_key"] for n in nodes}):
                c.execute(
                    "INSERT INTO progress_templates (key, version, definition) VALUES (%s, %s, %s::jsonb) "
                    "ON CONFLICT (key) DO NOTHING",
                    (key, version, definition),
                )
            for n in nodes:
                row = c.execute(
                    "INSERT INTO progress_nodes (project_id, template_key, node_key, status, queued, skipped_reason) "
                    "VALUES (%s::uuid, %s, %s, %s::node_status, %s, %s) "
                    "ON CONFLICT (project_id, node_key) DO UPDATE SET status = EXCLUDED.status, "
                    "queued = EXCLUDED.queued, skipped_reason = EXCLUDED.skipped_reason, updated_at = now() "
                    "RETURNING id, updated_at",
                    (project_id, n["template_key"], n["node_key"], n["status"], n.get("queued", False),
                     n.get("skipped_reason")),
                ).fetchone()
                saved.append({"id": str(row[0]), "project_id": project_id, **n,
                              "updated_at": row[1].isoformat() if hasattr(row[1], "isoformat") else str(row[1])})
        return saved

    def get_progress_node(self, project_id, node_key):
        with self._conn() as c:
            row = c.execute(
                "SELECT id, project_id, template_key, node_key, status, queued, skipped_reason, updated_at "
                "FROM progress_nodes WHERE project_id = %s::uuid AND node_key = %s", (project_id, node_key)
            ).fetchone()
        if not row:
            return None
        keys = ["id", "project_id", "template_key", "node_key", "status", "queued", "skipped_reason", "updated_at"]
        return {**dict(zip(keys, row)), "id": str(row[0]), "project_id": str(row[1]), "status": str(row[4]),
                "updated_at": row[7].isoformat() if hasattr(row[7], "isoformat") else str(row[7])}

    def update_progress_node(self, project_id, node_key, **fields):
        allowed = {"status", "queued", "skipped_reason"}
        if not fields or not set(fields) <= allowed:
            raise ValueError(f"Campos não permitidos: {set(fields) - allowed}")
        casts = {"status": "%s::node_status", "queued": "%s", "skipped_reason": "%s"}
        sets = ", ".join(f"{k} = {casts[k]}" for k in fields) + ", updated_at = now()"
        with self._conn() as c:
            row = c.execute(
                f"UPDATE progress_nodes SET {sets} WHERE project_id = %s::uuid AND node_key = %s "
                "RETURNING id, project_id, template_key, node_key, status, queued, skipped_reason, updated_at",
                (*fields.values(), project_id, node_key)
            ).fetchone()
        if not row:
            return None
        keys = ["id", "project_id", "template_key", "node_key", "status", "queued", "skipped_reason", "updated_at"]
        return {**dict(zip(keys, row)), "id": str(row[0]), "project_id": str(row[1]), "status": str(row[4]),
                "updated_at": row[7].isoformat() if hasattr(row[7], "isoformat") else str(row[7])}

    def save_gate_attempt(self, progress_node_id, transcript, rubric_scores, outcome):
        with self._conn() as c:
            row = c.execute(
                "INSERT INTO gate_attempts (progress_node_id, transcript, rubric_scores, outcome) "
                "VALUES (%s::uuid, %s::jsonb, %s::jsonb, %s) "
                "RETURNING id, progress_node_id, transcript, rubric_scores, outcome, created_at",
                (progress_node_id, json.dumps(transcript), json.dumps(rubric_scores) if rubric_scores else None, outcome)
            ).fetchone()
        keys = ["id", "progress_node_id", "transcript", "rubric_scores", "outcome", "created_at"]
        return {**dict(zip(keys, row)), "id": str(row[0]), "progress_node_id": str(row[1]),
                "created_at": row[5].isoformat() if hasattr(row[5], "isoformat") else str(row[5])}

    def list_gate_attempts(self, progress_node_id):
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, progress_node_id, transcript, rubric_scores, outcome, created_at "
                "FROM gate_attempts WHERE progress_node_id = %s::uuid ORDER BY created_at ASC",
                (progress_node_id,)
            ).fetchall()
        keys = ["id", "progress_node_id", "transcript", "rubric_scores", "outcome", "created_at"]
        return [{**dict(zip(keys, r)), "id": str(r[0]), "progress_node_id": str(r[1]),
                 "created_at": r[5].isoformat() if hasattr(r[5], "isoformat") else str(r[5])} for r in rows]

    def list_ai_usage(self, project_id):
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, project_id, action, target_ref, model, prompt_version, created_at "
                "FROM ai_usage_log WHERE project_id = %s::uuid ORDER BY created_at ASC",
                (project_id,)
            ).fetchall()
        keys = ["id", "project_id", "action", "target_ref", "model", "prompt_version", "created_at"]
        return [{**dict(zip(keys, r)), "id": str(r[0]), "project_id": str(r[1]),
                 "created_at": r[6].isoformat() if hasattr(r[6], "isoformat") else str(r[6])} for r in rows]

    def list_sections(self, project_id):
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, project_id, parent_id, title, position, content, updated_at "
                "FROM sections WHERE project_id = %s::uuid ORDER BY position ASC, updated_at ASC",
                (project_id,)
            ).fetchall()
            sections = []
            for r in rows:
                sid = str(r[0])
                crows = c.execute("SELECT concept_id FROM section_concepts WHERE section_id = %s::uuid", (sid,)).fetchall()
                sections.append({
                    "id": sid,
                    "project_id": str(r[1]),
                    "parent_id": str(r[2]) if r[2] else None,
                    "title": r[3],
                    "position": r[4],
                    "content": r[5] or {},
                    "concept_ids": [str(cr[0]) for cr in crows],
                    "updated_at": r[6].isoformat() if hasattr(r[6], "isoformat") else str(r[6]),
                })
        return sections

    def create_section(self, project_id, title, parent_id, position, content=None):
        with self._conn() as c:
            row = c.execute(
                "INSERT INTO sections (project_id, parent_id, title, position, content) "
                "VALUES (%s::uuid, %s::uuid, %s, %s, %s::jsonb) "
                "RETURNING id, project_id, parent_id, title, position, content, updated_at",
                (project_id, parent_id, title, position, json.dumps(content or {}))
            ).fetchone()
        return {
            "id": str(row[0]),
            "project_id": str(row[1]),
            "parent_id": str(row[2]) if row[2] else None,
            "title": row[3],
            "position": row[4],
            "content": row[5] or {},
            "concept_ids": [],
            "updated_at": row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6]),
        }

    def get_section(self, project_id, section_id):
        with self._conn() as c:
            row = c.execute(
                "SELECT id, project_id, parent_id, title, position, content, updated_at "
                "FROM sections WHERE id = %s::uuid AND project_id = %s::uuid",
                (section_id, project_id)
            ).fetchone()
            if not row:
                return None
            crows = c.execute("SELECT concept_id FROM section_concepts WHERE section_id = %s::uuid", (section_id,)).fetchall()
        return {
            "id": str(row[0]),
            "project_id": str(row[1]),
            "parent_id": str(row[2]) if row[2] else None,
            "title": row[3],
            "position": row[4],
            "content": row[5] or {},
            "concept_ids": [str(cr[0]) for cr in crows],
            "updated_at": row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6]),
        }

    def update_section(self, project_id, section_id, **fields):
        fields, by, force = _split_version_kwargs(fields)
        allowed = {"title", "parent_id", "position", "content"}
        if not fields or not set(fields) <= allowed:
            raise ValueError(f"Campos não permitidos: {set(fields) - allowed}")
        casts = {"title": "%s", "parent_id": "%s::uuid", "position": "%s", "content": "%s::jsonb"}
        sets = ", ".join(f"{k} = {casts[k]}" for k in fields) + ", updated_at = now()"
        vals = [json.dumps(v) if k == "content" else v for k, v in fields.items()]
        with self._conn() as c:
            if "content" in fields:
                self._snapshot(c, project_id, section_id, fields["content"], by, force)
            row = c.execute(
                f"UPDATE sections SET {sets} WHERE id = %s::uuid AND project_id = %s::uuid "
                "RETURNING id, project_id, parent_id, title, position, content, updated_at",
                (*vals, section_id, project_id)
            ).fetchone()
            if not row:
                return None
            crows = c.execute("SELECT concept_id FROM section_concepts WHERE section_id = %s::uuid", (section_id,)).fetchall()
        return {
            "id": str(row[0]),
            "project_id": str(row[1]),
            "parent_id": str(row[2]) if row[2] else None,
            "title": row[3],
            "position": row[4],
            "content": row[5] or {},
            "concept_ids": [str(cr[0]) for cr in crows],
            "updated_at": row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6]),
        }

    def delete_section(self, project_id, section_id):
        with self._conn() as c:
            c.execute("DELETE FROM sections WHERE id = %s::uuid AND project_id = %s::uuid", (section_id, project_id))
        return True

    def set_section_concepts(self, section_id, concept_ids):
        with self._conn() as c:
            c.execute("DELETE FROM section_concepts WHERE section_id = %s::uuid", (section_id,))
            for cid in concept_ids:
                c.execute(
                    "INSERT INTO section_concepts (section_id, concept_id) VALUES (%s::uuid, %s::uuid) ON CONFLICT DO NOTHING",
                    (section_id, cid)
                )

    def get_section_concepts(self, section_id):
        with self._conn() as c:
            crows = c.execute("SELECT concept_id FROM section_concepts WHERE section_id = %s::uuid", (section_id,)).fetchall()
        return [str(cr[0]) for cr in crows]

    def invite_advisor(self, project_id, advisor_email, can_comment=True):
        email = advisor_email.strip().lower()
        with self._conn() as c:
            row = c.execute(
                "INSERT INTO advisor_members (project_id, advisor_email, can_comment) "
                "VALUES (%s::uuid, %s, %s) "
                "ON CONFLICT (project_id, advisor_email) DO UPDATE SET can_comment = EXCLUDED.can_comment "
                "RETURNING project_id, advisor_email, can_comment, invited_at",
                (project_id, email, can_comment)
            ).fetchone()
        return {
            "project_id": str(row[0]),
            "advisor_email": str(row[1]),
            "can_comment": bool(row[2]),
            "invited_at": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
        }

    def list_advisors(self, project_id):
        with self._conn() as c:
            rows = c.execute(
                "SELECT project_id, advisor_email, can_comment, invited_at "
                "FROM advisor_members WHERE project_id = %s::uuid ORDER BY invited_at ASC",
                (project_id,)
            ).fetchall()
        return [{
            "project_id": str(r[0]),
            "advisor_email": str(r[1]),
            "can_comment": bool(r[2]),
            "invited_at": r[3].isoformat() if hasattr(r[3], "isoformat") else str(r[3]),
        } for r in rows]

    def remove_advisor(self, project_id, advisor_email):
        email = advisor_email.strip().lower()
        with self._conn() as c:
            c.execute("DELETE FROM advisor_members WHERE project_id = %s::uuid AND advisor_email = %s", (project_id, email))
        return True

    def list_advising_projects(self, advisor_email):
        email = advisor_email.strip().lower()
        with self._conn() as c:
            rows = c.execute(
                "SELECT p.id, p.owner_id, p.title, p.work, p.institution, p.citation_style, p.deadline, p.weekly_hours, p.created_at "
                "FROM projects p JOIN advisor_members am ON p.id = am.project_id WHERE am.advisor_email = %s ORDER BY p.created_at DESC",
                (email,)
            ).fetchall()
        keys = ["id", "owner_id", "title", "work", "institution", "citation_style", "deadline", "weekly_hours", "created_at"]
        return [{**dict(zip(keys, r)), "id": str(r[0]), "owner_id": str(r[1]),
                 "deadline": r[6].isoformat() if r[6] else None,
                 "created_at": r[8].isoformat() if hasattr(r[8], "isoformat") else str(r[8])} for r in rows]

    def is_advisor(self, project_id, email):
        em = email.strip().lower()
        with self._conn() as c:
            row = c.execute(
                "SELECT 1 FROM advisor_members WHERE project_id = %s::uuid AND advisor_email = %s",
                (project_id, em)
            ).fetchone()
        return bool(row)

    def create_advisor_report(self, project_id, payload, period_start=None, period_end=None):
        with self._conn() as c:
            row = c.execute(
                "INSERT INTO advisor_reports (project_id, period_start, period_end, payload) "
                "VALUES (%s::uuid, %s, %s, %s::jsonb) "
                "RETURNING id, project_id, period_start, period_end, payload, created_at",
                (project_id, period_start, period_end, json.dumps(payload))
            ).fetchone()
        return {
            "id": str(row[0]),
            "project_id": str(row[1]),
            "period_start": row[2].isoformat() if row[2] else None,
            "period_end": row[3].isoformat() if row[3] else None,
            "payload": row[4] or {},
            "created_at": row[5].isoformat() if hasattr(row[5], "isoformat") else str(row[5]),
        }

    def list_advisor_reports(self, project_id):
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, project_id, period_start, period_end, payload, created_at "
                "FROM advisor_reports WHERE project_id = %s::uuid ORDER BY created_at DESC",
                (project_id,)
            ).fetchall()
        return [{
            "id": str(r[0]),
            "project_id": str(r[1]),
            "period_start": r[2].isoformat() if r[2] else None,
            "period_end": r[3].isoformat() if r[3] else None,
            "payload": r[4] or {},
            "created_at": r[5].isoformat() if hasattr(r[5], "isoformat") else str(r[5]),
        } for r in rows]

    def get_advisor_report(self, project_id, report_id):
        with self._conn() as c:
            row = c.execute(
                "SELECT id, project_id, period_start, period_end, payload, created_at "
                "FROM advisor_reports WHERE id = %s::uuid AND project_id = %s::uuid",
                (report_id, project_id)
            ).fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "project_id": str(row[1]),
            "period_start": row[2].isoformat() if row[2] else None,
            "period_end": row[3].isoformat() if row[3] else None,
            "payload": row[4] or {},
            "created_at": row[5].isoformat() if hasattr(row[5], "isoformat") else str(row[5]),
        }

    def create_section_comment(self, section_id, author_email, author_name, content):
        email = author_email.strip().lower()
        with self._conn() as c:
            row = c.execute(
                "INSERT INTO section_comments (section_id, author_email, author_name, content) "
                "VALUES (%s::uuid, %s, %s, %s) "
                "RETURNING id, section_id, author_email, author_name, content, resolved, created_at",
                (section_id, email, author_name, content)
            ).fetchone()
        return {
            "id": str(row[0]),
            "section_id": str(row[1]),
            "author_email": str(row[2]),
            "author_name": row[3],
            "content": str(row[4]),
            "resolved": bool(row[5]),
            "created_at": row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6]),
        }

    def list_section_comments(self, section_id):
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, section_id, author_email, author_name, content, resolved, created_at "
                "FROM section_comments WHERE section_id = %s::uuid ORDER BY created_at ASC",
                (section_id,)
            ).fetchall()
        return [{
            "id": str(r[0]),
            "section_id": str(r[1]),
            "author_email": str(r[2]),
            "author_name": r[3],
            "content": str(r[4]),
            "resolved": bool(r[5]),
            "created_at": r[6].isoformat() if hasattr(r[6], "isoformat") else str(r[6]),
        } for r in rows]

    def update_section_comment(self, comment_id, **fields):
        allowed = {"resolved", "content"}
        if not fields or not set(fields) <= allowed:
            raise ValueError(f"Campos não permitidos: {set(fields) - allowed}")
        casts = {"resolved": "%s", "content": "%s"}
        sets = ", ".join(f"{k} = {casts[k]}" for k in fields)
        with self._conn() as c:
            row = c.execute(
                f"UPDATE section_comments SET {sets} WHERE id = %s::uuid "
                "RETURNING id, section_id, author_email, author_name, content, resolved, created_at",
                (*fields.values(), comment_id)
            ).fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "section_id": str(row[1]),
            "author_email": str(row[2]),
            "author_name": row[3],
            "content": str(row[4]),
            "resolved": bool(row[5]),
            "created_at": row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6]),
        }

    def delete_section_comment(self, comment_id):
        with self._conn() as c:
            c.execute("DELETE FROM section_comments WHERE id = %s::uuid", (comment_id,))
        return True

    def _snapshot(self, c, project_id, section_id, new_content, by, force) -> None:
        """Save the content about to be replaced (same rules as InMemoryRepo._snapshot), in the caller's transaction."""
        cur = c.execute(
            "SELECT content FROM sections WHERE id = %s::uuid AND project_id = %s::uuid FOR UPDATE",
            (section_id, project_id),
        ).fetchone()
        if not cur:
            return
        old = cur[0] or {}
        if old == new_content or not _has_text(old):
            return
        last = c.execute(
            "SELECT content_snapshot, (now() - created_at) < make_interval(secs => %s) FROM section_versions "
            "WHERE section_id = %s::uuid ORDER BY created_at DESC, id DESC LIMIT 1",
            (VERSION_MIN_INTERVAL_SECONDS, section_id),
        ).fetchone()
        if last and ((last[1] and not force) or last[0] == old):
            return
        c.execute(
            "INSERT INTO section_versions (section_id, content_snapshot, word_count, created_by) "
            "VALUES (%s::uuid, %s::jsonb, %s, %s)",
            (section_id, json.dumps(old), _count_words(old), by),
        )
        c.execute(
            "DELETE FROM section_versions WHERE section_id = %s::uuid AND id NOT IN ("
            "SELECT id FROM section_versions WHERE section_id = %s::uuid ORDER BY created_at DESC, id DESC LIMIT %s)",
            (section_id, section_id, VERSION_KEEP),
        )

    @staticmethod
    def _version_row(r) -> dict:
        return {
            "id": str(r[0]), "section_id": str(r[1]), "content_snapshot": r[2] or {}, "word_count": r[3],
            "created_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]), "created_by": r[5],
        }

    def list_section_versions(self, project_id, section_id):
        with self._conn() as c:
            rows = c.execute(
                "SELECT v.id, v.section_id, v.content_snapshot, v.word_count, v.created_at, v.created_by "
                "FROM section_versions v JOIN sections s ON s.id = v.section_id "
                "WHERE v.section_id = %s::uuid AND s.project_id = %s::uuid ORDER BY v.created_at DESC, v.id DESC",
                (section_id, project_id),
            ).fetchall()
        return [self._version_row(r) for r in rows]

    def get_section_version(self, project_id, section_id, version_id):
        try:
            uuid.UUID(version_id)
        except ValueError:
            return None
        with self._conn() as c:
            r = c.execute(
                "SELECT v.id, v.section_id, v.content_snapshot, v.word_count, v.created_at, v.created_by "
                "FROM section_versions v JOIN sections s ON s.id = v.section_id "
                "WHERE v.id = %s::uuid AND v.section_id = %s::uuid AND s.project_id = %s::uuid",
                (version_id, section_id, project_id),
            ).fetchone()
        return self._version_row(r) if r else None

    def add_node_feedback(self, project_id, node_key, advisor_email, advisor_name, content):
        with self._conn() as c:
            r = c.execute(
                "INSERT INTO node_feedback (project_id, node_key, advisor_email, advisor_name, content) "
                "VALUES (%s::uuid, %s, %s, %s, %s) "
                "RETURNING id, project_id, node_key, advisor_email, advisor_name, content, created_at",
                (project_id, node_key, advisor_email.strip().lower(), advisor_name, content),
            ).fetchone()
        return self._feedback_row(r)

    @staticmethod
    def _feedback_row(r) -> dict:
        return {
            "id": str(r[0]), "project_id": str(r[1]), "node_key": r[2], "advisor_email": r[3],
            "advisor_name": r[4], "content": r[5],
            "created_at": r[6].isoformat() if hasattr(r[6], "isoformat") else str(r[6]),
        }

    def list_node_feedback(self, project_id, node_key):
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, project_id, node_key, advisor_email, advisor_name, content, created_at "
                "FROM node_feedback WHERE project_id = %s::uuid AND node_key = %s ORDER BY created_at ASC, id",
                (project_id, node_key),
            ).fetchall()
        return [self._feedback_row(r) for r in rows]

    # ------------------------------------------------------------------ provenance ledger
    @staticmethod
    def _prov_row(r) -> dict:
        return {"id": str(r[0]), "project_id": str(r[1]), "section_id": str(r[2]), "kind": r[3], "source": r[4],
                "words": r[5], "text": r[6], "meta": r[7] or {}, "declared": r[8], "created_by": r[9],
                "created_at": r[10].isoformat() if hasattr(r[10], "isoformat") else str(r[10])}

    _PROV_COLS = "id, project_id, section_id, kind, source, words, text, meta, declared, created_by, created_at"

    def add_provenance_event(self, project_id, section_id, kind, source, words, text, meta, created_by):
        from psycopg.types.json import Jsonb

        with self._conn() as c:
            ok = c.execute("SELECT 1 FROM sections WHERE id = %s::uuid AND project_id = %s::uuid",
                           (section_id, project_id)).fetchone()
            if not ok:
                raise ValueError("section not in project")
            r = c.execute(
                f"INSERT INTO provenance_events (project_id, section_id, kind, source, words, text, meta, created_by) "
                f"VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s) RETURNING {self._PROV_COLS}",
                (project_id, section_id, kind, source, words, text.replace("\x00", "") if text else text,
                 Jsonb(meta or {}), created_by),
            ).fetchone()
        return self._prov_row(r)

    def list_provenance_events(self, project_id, section_id=None):
        with self._conn() as c:
            if section_id is None:
                rows = c.execute(f"SELECT {self._PROV_COLS} FROM provenance_events WHERE project_id = %s::uuid "
                                 "ORDER BY created_at, id", (project_id,)).fetchall()
            else:
                rows = c.execute(f"SELECT {self._PROV_COLS} FROM provenance_events WHERE project_id = %s::uuid "
                                 "AND section_id = %s::uuid ORDER BY created_at, id", (project_id, section_id)).fetchall()
        return [self._prov_row(r) for r in rows]

    def declare_provenance_event(self, project_id, event_id, declared):
        try:
            uuid.UUID(event_id)
        except ValueError:
            return None
        with self._conn() as c:
            r = c.execute(
                f"UPDATE provenance_events SET declared = %s WHERE id = %s::uuid AND project_id = %s::uuid "
                f"AND kind = 'paste' RETURNING {self._PROV_COLS}", (declared, event_id, project_id),
            ).fetchone()
        return self._prov_row(r) if r else None

    # ------------------------------------------------------------------ local error log
    def add_error_event(self, source, error_type, message, stack, route, request_id, user_id):
        with self._conn() as c:
            r = c.execute(
                "INSERT INTO error_events (source, error_type, message, stack, route, request_id, user_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "RETURNING id, source, error_type, message, stack, route, request_id, user_id, created_at",
                (source, error_type, message, stack, route, request_id, user_id),
            ).fetchone()
        return self._err_row(r)

    @staticmethod
    def _err_row(r) -> dict:
        keys = ["id", "source", "error_type", "message", "stack", "route", "request_id", "user_id", "created_at"]
        d = dict(zip(keys, r))
        d["id"] = str(d["id"])
        d["created_at"] = d["created_at"].isoformat()
        return d

    def list_error_events(self, limit=100):
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, source, error_type, message, stack, route, request_id, user_id, created_at "
                "FROM error_events ORDER BY created_at DESC LIMIT %s", (limit,)
            ).fetchall()
        return [self._err_row(r) for r in rows]

    def purge_error_events(self, older_than_days):
        with self._conn() as c:
            cur = c.execute("DELETE FROM error_events WHERE created_at < now() - make_interval(days => %s)",
                            (older_than_days,))
            return cur.rowcount

    # ------------------------------------------------------------------ passage index
    def replace_chunks(self, document_id, chunks):
        with self._conn() as c:
            row = c.execute("SELECT project_id FROM documents WHERE id = %s::uuid", (document_id,)).fetchone()
            if not row:
                return 0
            c.execute("DELETE FROM chunks WHERE document_id = %s::uuid", (document_id,))
            with c.cursor() as cur:
                cur.executemany(
                    "INSERT INTO chunks (document_id, project_id, chunk_no, page_no, text, search_text) "
                    "VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s)",
                    [(document_id, row[0], k["chunk_no"], k["page_no"], k["text"].replace("\x00", ""),
                      k["search_text"].replace("\x00", "")) for k in chunks],
                )
        return len(chunks)

    def chunks_to_embed(self, document_id, model, limit):
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, text FROM chunks WHERE document_id = %s::uuid AND embedding_model IS DISTINCT FROM %s "
                "ORDER BY chunk_no LIMIT %s", (document_id, model, limit),
            ).fetchall()
        return [{"id": str(r[0]), "text": r[1]} for r in rows]

    def save_embeddings(self, items, model):
        if not items:
            return
        with self._conn() as c:
            with c.cursor() as cur:
                cur.executemany(
                    "UPDATE chunks SET embedding = %s::real[], embedding_model = %s WHERE id = %s::uuid",
                    [(list(vec), model, cid) for cid, vec in items],
                )

    def chunk_stats(self, project_id, model):
        with self._conn() as c:
            n, e = c.execute(
                "SELECT count(*), count(*) FILTER (WHERE embedding_model = %s) FROM chunks WHERE project_id = %s::uuid",
                (model, project_id),
            ).fetchone()
        return {"chunks": n, "embedded": e}

    def _chunk_hits(self, c, scored: list[tuple[str, float]]) -> list[dict]:
        if not scored:
            return []
        rows = c.execute(
            "SELECT id, document_id, page_no, text FROM chunks WHERE id = ANY(%s::uuid[])", ([i for i, _ in scored],)
        ).fetchall()
        by_id = {str(r[0]): r for r in rows}
        return [{"id": i, "document_id": str(by_id[i][1]), "page_no": by_id[i][2], "text": by_id[i][3], "score": s}
                for i, s in scored if i in by_id]

    def search_keyword(self, project_id, query, limit):
        q = _search.tsquery(query)
        if not q:
            return []
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, ts_rank_cd(tsv, to_tsquery('simple', %s)) AS r FROM chunks "
                "WHERE project_id = %s::uuid AND tsv @@ to_tsquery('simple', %s) ORDER BY r DESC, id LIMIT %s",
                (q, project_id, q, limit),
            ).fetchall()
            return self._chunk_hits(c, [(str(r[0]), float(r[1])) for r in rows])

    def search_vector(self, project_id, vector, model, limit):
        import heapq

        with self._conn() as c:
            best = heapq.nlargest(
                limit,
                ((_search.cosine(vector, emb), str(cid)) for cid, emb in c.execute(
                    "SELECT id, embedding FROM chunks WHERE project_id = %s::uuid AND embedding_model = %s "
                    "AND embedding IS NOT NULL", (project_id, model))),
            )
            return self._chunk_hits(c, [(cid, s) for s, cid in best])

    def get_section_comment(self, section_id, comment_id):
        try:
            uuid.UUID(comment_id)
        except ValueError:
            return None
        with self._conn() as c:
            r = c.execute(
                "SELECT id, section_id, author_email, author_name, content, resolved, created_at "
                "FROM section_comments WHERE id = %s::uuid AND section_id = %s::uuid",
                (comment_id, section_id),
            ).fetchone()
        if not r:
            return None
        return {
            "id": str(r[0]), "section_id": str(r[1]), "author_email": str(r[2]), "author_name": r[3],
            "content": str(r[4]), "resolved": bool(r[5]),
            "created_at": r[6].isoformat() if hasattr(r[6], "isoformat") else str(r[6]),
        }

    def delete_document(self, project_id, document_id):
        """Delete a document (claims, pages, jobs and edge evidence cascade). Returns the removed row."""
        doc = self.get_document(document_id)
        if not doc or doc["project_id"] != project_id:
            return None
        with self._conn() as c:
            c.execute("DELETE FROM documents WHERE id = %s::uuid AND project_id = %s::uuid", (document_id, project_id))
        return doc

    def get_beta_metrics(self) -> dict:
        with self._conn() as c:
            users_count = c.execute("SELECT count(*) FROM users").fetchone()[0]
            projects_count = c.execute("SELECT count(*) FROM projects").fetchone()[0]
            work_rows = c.execute("SELECT work, count(*) FROM projects GROUP BY work").fetchall()
            by_work = {row[0]: row[1] for row in work_rows}

            act_rows = c.execute(
                "SELECT count(*) FROM (SELECT project_id FROM documents GROUP BY project_id HAVING count(*) >= 5) as s"
            ).fetchone()[0]
            activation_rate = round(act_rows / projects_count, 3) if projects_count else 0.0

            edges_count = c.execute("SELECT count(*) FROM edges").fetchone()[0]
            conf = c.execute("SELECT count(*) FROM edges WHERE status = 'confirmed'").fetchone()[0]
            rej = c.execute("SELECT count(*) FROM edges WHERE status = 'rejected'").fetchone()[0]
            tot_dec = conf + rej
            acc_rate = round(conf / tot_dec, 3) if tot_dec else 0.0

            gate_total = c.execute("SELECT count(*) FROM gate_attempts").fetchone()[0]
            gate_lib = c.execute("SELECT count(*) FROM gate_attempts WHERE outcome = 'liberar'").fetchone()[0]
            gate_pul = c.execute("SELECT count(*) FROM gate_attempts WHERE outcome = 'pular'").fetchone()[0]

            sec_count = c.execute("SELECT count(*) FROM sections").fetchone()[0]
            adv_count = c.execute("SELECT count(*) FROM advisor_members").fetchone()[0]
            comm_count = c.execute("SELECT count(*) FROM section_comments").fetchone()[0]
            rep_count = c.execute("SELECT count(*) FROM advisor_reports").fetchone()[0]

            ai_rows = c.execute("SELECT action, count(*) FROM ai_usage_log GROUP BY action").fetchall()
            ai_by_action = {row[0]: row[1] for row in ai_rows}

        return {
            "students_registered": users_count,
            "projects_total": projects_count,
            "projects_by_work": by_work,
            "activation": {
                "threshold_sources": 5,
                "activated_projects": act_rows,
                "activation_rate": activation_rate,
            },
            "knowledge_map": {
                "total_edges": edges_count,
                "total_decisions": tot_dec,
                "confirmed": conf,
                "rejected": rej,
                "acceptance_rate": acc_rate,
                "target_acceptance_rate": 0.50,
            },
            "socratic_gate": {
                "total_attempts": gate_total,
                "passed": gate_lib,
                "skipped_with_warning": gate_pul,
            },
            "manuscript_and_collaboration": {
                "total_sections": sec_count,
                "advisor_invites": adv_count,
                "advisor_comments": comm_count,
                "advisor_reports_generated": rep_count,
            },
            "ai_usage": ai_by_action,
            "pricing_validation": {
                "hypothesis_a": "Passe por projeto (R$ 89 a R$ 149)",
                "hypothesis_b": "Assinatura mensal (R$ 25 a R$ 50)",
                "cohort_target": "10 a 20 alunos",
            },
        }

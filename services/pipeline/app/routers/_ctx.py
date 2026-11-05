"""Contexto de dependências compartilhadas entre os roteadores.

Cada roteador recebe um objeto AppCtx com as dependências injetadas pela factory
em main.py. Isso preserva o comportamento de closure do arquivo original sem
exigir variáveis globais.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..repo import Repo
from ..jobs import JobQueue
from ..security import decode_token


@dataclass
class AppCtx:
    repo: Repo
    storage_dir: Path
    job_queue: JobQueue
    client: object  # LLMClient | None
    fetch_json: Callable
    bearer: HTTPBearer = field(default_factory=lambda: HTTPBearer(auto_error=False))

    # ── helpers que todos os roteadores usam ──────────────────────────

    def current_user(
        self,
        request: Request,
        cred: HTTPAuthorizationCredentials | None = None,
    ) -> dict:
        token = (
            cred.credentials
            if (cred and cred.credentials)
            else request.cookies.get("orientador_token")
        )
        user_id = decode_token(token) if token else None
        user = self.repo.get_user(user_id) if user_id else None
        if not user:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Sessão inválida ou expirada. Entre novamente.",
            )
        return user

    def owned_project(self, user: dict, project_id: str) -> dict:
        project = self.repo.get_project(user["id"], project_id)
        if not project:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado.")
        return project

    def accessible_project(self, user: dict, project_id: str) -> dict:
        project = self.repo.get_project(user["id"], project_id)
        if project:
            return project
        if self.repo.is_advisor(project_id, user.get("email", "")):
            adv_project = self.repo.get_project_by_id(project_id)
            if adv_project:
                return adv_project
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projeto não encontrado.")

    @staticmethod
    def public(user: dict) -> dict:
        return {"id": user["id"], "email": user["email"], "name": user["name"]}

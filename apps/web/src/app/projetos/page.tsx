"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ApiError, api, clearToken, getToken, Project, WORK_LABELS } from "@/lib/api";

const input = "w-full rounded border border-ink/30 bg-white px-3 py-2 text-sm";

export default function ProjetosPage() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [advisingProjects, setAdvisingProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const leave = useCallback(() => {
    clearToken();
    router.replace("/entrar");
  }, [router]);

  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/entrar");
      return;
    }
    let cancelled = false;
    api<Project[]>("/projects")
      .then((list) => {
        if (!cancelled) setProjects(list);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) return leave();
        setError(err instanceof Error ? err.message : "Algo deu errado.");
      });

    api<Project[]>("/advising-projects")
      .then((list) => {
        if (!cancelled) setAdvisingProjects(list);
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [reloadKey, leave, router]);
  async function onCreate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    const hours = f.get("weekly_hours");
    setBusy(true);
    setError(null);
    try {
      await api<Project>("/projects", {
        method: "POST",
        body: {
          title: f.get("title"),
          work: f.get("work"),
          institution: f.get("institution") || null,
          citation_style: f.get("citation_style"),
          deadline: f.get("deadline") || null,
          weekly_hours: hours ? Number(hours) : null,
        },
      });
      form.reset();
      setReloadKey((k) => k + 1);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return leave();
      setError(err instanceof Error ? err.message : "Algo deu errado.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-3xl px-6 py-10">
      <header className="flex items-baseline justify-between">
        <h1 className="font-serif-academic text-3xl">Seus projetos</h1>
        <button onClick={leave} className="text-sm text-available underline">
          Sair
        </button>
      </header>

      <section className="mt-8" aria-label="Projetos existentes">
        {projects === null && !error && <p className="text-sm">Carregando…</p>}
        {projects?.length === 0 && (
          <p className="text-sm text-ink/70">Você ainda não tem projetos. Crie o primeiro abaixo.</p>
        )}
        <ul className="space-y-3">
          {projects?.map((p) => (
            <li key={p.id} className="rounded border border-ink/20 bg-white p-4">
              <p className="font-medium">{p.title}</p>
              <p className="mt-1 text-sm text-ink/70">
                {WORK_LABELS[p.work] ?? p.work}
                {p.institution ? ` · ${p.institution}` : ""} · {p.citation_style.toUpperCase()}
                {p.deadline ? ` · prazo ${p.deadline.split("-").reverse().join("/")}` : ""}
                {p.weekly_hours ? ` · ${p.weekly_hours} h/semana` : ""}
              </p>
              <div className="mt-3 flex items-center gap-4 text-sm">
                <Link href={`/projetos/${p.id}/arvore`} className="font-medium text-available underline">
                  Árvore de progresso
                </Link>
                <Link href={`/projetos/${p.id}/mapa`} className="text-ink/70 underline">
                  Mapa de conhecimento
                </Link>
                <Link href={`/projetos/${p.id}/editor`} className="text-ink/70 underline">
                  Editor do manuscrito
                </Link>
                <Link href={`/projetos/${p.id}/relatorio`} className="text-ink/70 underline">
                  Relatório
                </Link>
              </div>
            </li>
          ))}
        </ul>
      </section>

      {advisingProjects.length > 0 && (
        <section className="mt-8" aria-label="Projetos sob orientação">
          <h2 className="font-serif-academic text-xl font-semibold text-ink">
            Projetos sob sua Orientação ({advisingProjects.length})
          </h2>
          <ul className="mt-3 space-y-3">
            {advisingProjects.map((p) => (
              <li key={p.id} className="rounded border border-available/30 bg-available/5 p-4">
                <div className="flex items-center justify-between">
                  <p className="font-medium text-ink">{p.title}</p>
                  <span className="rounded bg-available/10 px-2 py-0.5 text-xs text-available font-semibold">
                    Orientando
                  </span>
                </div>
                <p className="mt-1 text-sm text-ink/70">
                  {WORK_LABELS[p.work] ?? p.work}
                  {p.institution ? ` · ${p.institution}` : ""} · {p.citation_style.toUpperCase()}
                  {p.deadline ? ` · prazo ${p.deadline.split("-").reverse().join("/")}` : ""}
                </p>
                <div className="mt-3 flex items-center gap-4 text-sm">
                  <Link href={`/projetos/${p.id}/arvore`} className="font-medium text-available underline">
                    Árvore
                  </Link>
                  <Link href={`/projetos/${p.id}/mapa`} className="text-ink/70 underline">
                    Mapa
                  </Link>
                  <Link href={`/projetos/${p.id}/editor`} className="text-ink/70 underline">
                    Editor & Comentários
                  </Link>
                  <Link href={`/projetos/${p.id}/relatorio`} className="text-ink/70 underline">
                    Relatório de Progresso
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="mt-10" aria-label="Novo projeto">
        <h2 className="text-lg font-medium">Novo projeto</h2>
        <form onSubmit={onCreate} className="mt-4 grid gap-4 sm:grid-cols-2">
          <label className="block text-sm sm:col-span-2">
            Título do trabalho
            <input name="title" required minLength={3} maxLength={200} className={input} />
          </label>
          <label className="block text-sm">
            Tipo de trabalho
            <select name="work" required defaultValue="tcc" className={input}>
              {Object.entries(WORK_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            Instituição
            <input name="institution" maxLength={200} className={input} />
          </label>
          <label className="block text-sm">
            Norma de citação
            <select name="citation_style" defaultValue="abnt" className={input}>
              <option value="abnt">ABNT</option>
              <option value="apa">APA</option>
              <option value="vancouver">Vancouver</option>
            </select>
          </label>
          <label className="block text-sm">
            Prazo de entrega
            <input name="deadline" type="date" className={input} />
          </label>
          <label className="block text-sm">
            Horas por semana
            <input name="weekly_hours" type="number" min={1} max={100} className={input} />
          </label>
          {error && (
            <p role="alert" className="text-sm text-danger sm:col-span-2">
              {error}
            </p>
          )}
          <div className="sm:col-span-2">
            <button
              disabled={busy}
              className="rounded bg-available px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {busy ? "Criando…" : "Criar projeto"}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}

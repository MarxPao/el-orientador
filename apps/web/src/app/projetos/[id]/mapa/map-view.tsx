"use client";

import "@xyflow/react/dist/style.css";

import { Background, Controls, MarkerType, ReactFlow, type Edge, type Node } from "@xyflow/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  api,
  Evidence,
  GAP_STATUS_LABELS,
  Gap,
  getToken,
  MapData,
  MapLink,
  openPdfAtPage,
  RELATION_LABELS,
  STATUS_LABELS,
} from "@/lib/api";

type Status = MapLink["status"];

// Color is never the only cue: stroke style (solid / dashed / dotted) and a text label are always present.
const STATUS_STYLE: Record<Status, { stroke: string; dash?: string }> = {
  confirmed: { stroke: "#5F6E2F" },
  suggested: { stroke: "#4B2A7B", dash: "6 4" },
  rejected: { stroke: "#6F665D", dash: "2 4" },
};

export default function MapView({ id }: { id: string }) {
  const router = useRouter();
  const [data, setData] = useState<MapData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);
  const [shown, setShown] = useState<Record<Status, boolean>>({ confirmed: true, suggested: true, rejected: false });
  const [showLowConfidence, setShowLowConfidence] = useState(false);
  const [showGaps, setShowGaps] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedGapId, setSelectedGapId] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<Evidence[] | null>(null);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);
  const [deciding, setDeciding] = useState(false);
  const [decidingGap, setDecidingGap] = useState(false);

  async function selectLink(linkId: string) {
    setSelectedId(linkId);
    setSelectedGapId(null);
    setEvidence(null);
    setEvidenceError(null);
    try {
      setEvidence(await api<Evidence[]>(`/projects/${id}/edges/${linkId}/evidence`));
    } catch (err) {
      setEvidenceError(err instanceof Error ? err.message : "Algo deu errado.");
    }
  }

  function selectGap(gapId: string) {
    setSelectedGapId(gapId === selectedGapId ? null : gapId);
    setSelectedId(null);
  }

  async function onOpenPdf(documentId: string, page: number) {
    setEvidenceError(null);
    try {
      await openPdfAtPage(id, documentId, page);
    } catch (err) {
      setEvidenceError(err instanceof Error ? err.message : "Não foi possível abrir o PDF.");
    }
  }

  async function decide(linkId: string, body: { action: "confirm" | "reject" | "edit"; relation?: string; note?: string }) {
    setDeciding(true);
    setEvidenceError(null);
    try {
      await api<MapLink>(`/projects/${id}/edges/${linkId}`, { method: "PATCH", body });
      setNotice(
        body.action === "reject"
          ? "Ligação rejeitada. Ela não será sugerida novamente."
          : "Ligação confirmada.",
      );
      setReloadKey((k) => k + 1);
    } catch (err) {
      setEvidenceError(err instanceof Error ? err.message : "Algo deu errado.");
    } finally {
      setDeciding(false);
    }
  }

  async function decideGap(gapId: string, status: Gap["status"], note?: string) {
    setDecidingGap(true);
    setError(null);
    try {
      await api<Gap>(`/projects/${id}/gaps/${gapId}`, { method: "PATCH", body: { status, note } });
      setNotice(
        status === "adopted_as_problem"
          ? "Lacuna adotada como problema de pesquisa."
          : status === "dismissed"
          ? "Lacuna descartada."
          : "Lacuna reaberta.",
      );
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Algo deu errado.");
    } finally {
      setDecidingGap(false);
    }
  }

  useEffect(() => {
    if (!getToken()) {
      router.replace("/entrar");
      return;
    }
    let cancelled = false;
    api<MapData>(`/projects/${id}/map`)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) return router.replace("/entrar");
        setError(err instanceof Error ? err.message : "Algo deu errado.");
      });
    return () => {
      cancelled = true;
    };
  }, [id, reloadKey, router]);

  const visibleLinks = useMemo(
    () => (data?.edges ?? []).filter((e) => shown[e.status] && (showLowConfidence || e.display_by_default)),
    [data, shown, showLowConfidence],
  );
  const hiddenLowConfidence = (data?.edges ?? []).filter((e) => !e.display_by_default && shown[e.status]).length;
  const labelOf = useMemo(() => new Map((data?.nodes ?? []).map((n) => [n.id, n.label])), [data]);

  const visibleGaps = useMemo(
    () => (data?.gaps ?? []).filter((g) => g.status !== "dismissed"),
    [data],
  );

  const { nodes, edges } = useMemo(() => {
    const list = data?.nodes ?? [];
    const radius = Math.max(160, list.length * 45);
    const posMap = new Map<string, { x: number; y: number }>();

    const conceptNodes: Node[] = list.map((n, i) => {
      const angle = (2 * Math.PI * i) / Math.max(list.length, 1);
      const pos = { x: radius * Math.cos(angle), y: radius * Math.sin(angle) };
      posMap.set(n.id, pos);
      return {
        id: n.id,
        position: pos,
        data: { label: `${n.label} (${n.n_claims})` },
        style: { border: "1px solid #241E1A", borderRadius: 6, background: "#fff", padding: 8, fontSize: 13, width: 170 },
      };
    });

    const gapNodes: Node[] = [];
    const gapEdges: Edge[] = [];

    if (showGaps) {
      visibleGaps.forEach((g) => {
        const posA = posMap.get(g.concept_a) || { x: 0, y: 0 };
        const posB = posMap.get(g.concept_b) || { x: 0, y: 0 };
        const midPos = { x: (posA.x + posB.x) / 2, y: (posA.y + posB.y) / 2 };
        const gapNodeId = `gap-${g.id}`;

        gapNodes.push({
          id: gapNodeId,
          position: midPos,
          data: { label: `[Lacuna] ${labelOf.get(g.concept_a)} ↔ ${labelOf.get(g.concept_b)}` },
          style: {
            border: "2px dotted #4B2A7B",
            borderRadius: 6,
            background: "#FFFFFF",
            padding: 6,
            fontSize: 11,
            color: "#4B2A7B",
            width: 155,
            cursor: "pointer",
          },
        });

        gapEdges.push(
          {
            id: `edge-${gapNodeId}-a`,
            source: g.concept_a,
            target: gapNodeId,
            style: { stroke: "#4B2A7B", strokeWidth: 1.5, strokeDasharray: "2 4" },
          },
          {
            id: `edge-${gapNodeId}-b`,
            source: gapNodeId,
            target: g.concept_b,
            style: { stroke: "#4B2A7B", strokeWidth: 1.5, strokeDasharray: "2 4" },
          },
        );
      });
    }

    const relationEdges: Edge[] = visibleLinks.map((e) => {
      const s = STATUS_STYLE[e.status];
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        label: `${RELATION_LABELS[e.relation] ?? e.relation} · ${STATUS_LABELS[e.status].toLowerCase()}`,
        markerEnd: { type: MarkerType.ArrowClosed, color: s.stroke },
        style: { stroke: s.stroke, strokeWidth: 2, strokeDasharray: s.dash },
        labelStyle: { fontSize: 11, fill: "#241E1A" },
        labelBgStyle: { fill: "#F6EEDC" },
      };
    });

    return {
      nodes: [...conceptNodes, ...gapNodes],
      edges: [...relationEdges, ...gapEdges],
    };
  }, [data, visibleLinks, visibleGaps, showGaps, labelOf]);

  async function onSuggest() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const r = await api<{ created: number }>(`/projects/${id}/map/suggest`, { method: "POST" });
      setNotice(
        r.created === 0
          ? "Nenhuma ligação nova encontrada nas evidências disponíveis."
          : `${r.created} ligação(ões) sugerida(s). Revise cada uma antes de confirmar.`,
      );
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Algo deu errado.");
    } finally {
      setBusy(false);
    }
  }

  async function onDetectGaps() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const r = await api<{ created: number }>(`/projects/${id}/gaps/detect`, { method: "POST" });
      setNotice(
        r.created === 0
          ? "Nenhuma nova lacuna identificada para os conceitos atuais."
          : `${r.created} lacuna(s) identificada(s) após buscas externas nas bases.`,
      );
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Algo deu errado.");
    } finally {
      setBusy(false);
    }
  }

  const empty = data !== null && data.nodes.length === 0;

  return (
    <main className="mx-auto w-full max-w-5xl px-6 py-8">
      <header className="flex flex-wrap items-baseline justify-between gap-4">
        <h1 className="font-serif-academic text-3xl">Mapa de conhecimento</h1>
        <div className="flex items-center gap-4 text-sm">
          <Link href={`/projetos/${id}/arvore`} className="text-available underline">
            Abrir árvore de progresso
          </Link>
          <Link href={`/projetos/${id}/editor`} className="text-available underline">
            Abrir editor
          </Link>
          <Link href="/projetos" className="text-ink/70 underline">
            Voltar aos projetos
          </Link>
        </div>
      </header>

      {error && (
        <p role="alert" className="mt-4 text-sm text-danger">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="mt-4 text-sm font-medium">
          {notice}
        </p>
      )}
      {data === null && !error && <p className="mt-6 text-sm">Carregando…</p>}
      {empty && (
        <p className="mt-6 text-sm text-ink/70">
          Ainda não há conceitos neste projeto. Envie PDFs para a biblioteca ou busque artigos por DOI para gerar o mapa.
        </p>
      )}

      {data && !empty && (
        <>
          <section aria-label="Filtros e Ações" className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
            {(Object.keys(STATUS_LABELS) as Status[]).map((s) => (
              <label key={s} className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={shown[s]}
                  onChange={(e) => setShown({ ...shown, [s]: e.target.checked })}
                />
                {STATUS_LABELS[s]}
              </label>
            ))}
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={showLowConfidence} onChange={(e) => setShowLowConfidence(e.target.checked)} />
              Baixa confiança{hiddenLowConfidence > 0 ? ` (${hiddenLowConfidence} ocultas)` : ""}
            </label>
            <label className="flex items-center gap-2 text-gap font-medium">
              <input type="checkbox" checked={showGaps} onChange={(e) => setShowGaps(e.target.checked)} />
              Lacunas ({visibleGaps.length})
            </label>
            <div className="ml-auto flex items-center gap-2">
              <button
                onClick={onDetectGaps}
                disabled={busy}
                className="rounded border border-gap bg-white px-3 py-2 font-medium text-gap disabled:opacity-60"
              >
                {busy ? "Buscando…" : "Buscar lacunas"}
              </button>
              <button
                onClick={onSuggest}
                disabled={busy}
                className="rounded bg-available px-3 py-2 font-medium text-white disabled:opacity-60"
              >
                {busy ? "Analisando…" : "Sugerir ligações"}
              </button>
            </div>
          </section>

          <section aria-label="Grafo de conceitos" className="mt-4 hidden h-[30rem] rounded border border-ink/20 bg-white md:block">
            <ReactFlow
              nodes={nodes}
              edges={edges}
              fitView
              nodesConnectable={false}
              onEdgeClick={(_, edge) => {
                if (!edge.id.startsWith("edge-gap-")) {
                  void selectLink(edge.id);
                }
              }}
              onNodeClick={(_, node) => {
                if (node.id.startsWith("gap-")) {
                  selectGap(node.id.replace("gap-", ""));
                }
              }}
              proOptions={{ hideAttribution: true }}
            >
              <Background />
              <Controls showInteractive={false} />
            </ReactFlow>
          </section>

          {/* Gaps Section */}
          {(data.gaps ?? []).length > 0 && (
            <section aria-label="Lacunas de pesquisa" className="mt-8">
              <h2 className="text-lg font-medium text-gap">
                Lacunas de pesquisa (potenciais temas de investigação)
              </h2>
              <ul className="mt-3 space-y-3 text-sm">
                {(data.gaps ?? []).map((g) => (
                  <li key={g.id} className="rounded border border-gap/30 bg-white p-4">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <p className="font-medium text-ink">
                        {labelOf.get(g.concept_a) ?? g.concept_a} <span className="text-gap">↔</span>{" "}
                        {labelOf.get(g.concept_b) ?? g.concept_b}
                      </p>
                      <span className="text-xs uppercase tracking-wide text-ink/60">
                        {GAP_STATUS_LABELS[g.status]}
                      </span>
                    </div>
                    {g.note && <p className="mt-2 text-ink/80">{g.note}</p>}
                    <button
                      onClick={() => selectGap(g.id)}
                      aria-expanded={selectedGapId === g.id}
                      className="mt-2 text-available underline"
                    >
                      {selectedGapId === g.id ? "Ocultar buscas feitas" : "Ver buscas externas feitas"}
                    </button>
                    {selectedGapId === g.id && (
                      <GapPanel
                        gap={g}
                        deciding={decidingGap}
                        onDecide={(status, note) => void decideGap(g.id, status, note)}
                      />
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Links Section */}
          <section aria-label="Lista de ligações" className="mt-8">
            <h2 className="text-lg font-medium">Ligações</h2>
            {visibleLinks.length === 0 ? (
              <p className="mt-2 text-sm text-ink/70">Nenhuma ligação para os filtros escolhidos.</p>
            ) : (
              <ul className="mt-2 space-y-2 text-sm">
                {visibleLinks.map((e) => (
                  <li key={e.id} className="rounded border border-ink/20 bg-white p-3">
                    <p>
                      <strong>{labelOf.get(e.source)}</strong> {RELATION_LABELS[e.relation] ?? e.relation}{" "}
                      <strong>{labelOf.get(e.target)}</strong>
                    </p>
                    <p className="mt-1 text-ink/70">
                      {STATUS_LABELS[e.status]}
                      {e.confidence != null ? ` · confiança ${Math.round(e.confidence * 100)}%` : ""}
                      {!e.display_by_default ? " · baixa confiança" : ""}
                    </p>
                    <button
                      onClick={() => void selectLink(e.id)}
                      aria-expanded={selectedId === e.id}
                      className="mt-2 text-available underline"
                    >
                      Ver evidência
                    </button>
                    {selectedId === e.id && (
                      <EvidencePanel
                        link={e}
                        evidence={evidence}
                        error={evidenceError}
                        deciding={deciding}
                        onOpenPdf={onOpenPdf}
                        onDecide={(body) => void decide(e.id, body)}
                      />
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </main>
  );
}

function GapPanel({
  gap,
  deciding,
  onDecide,
}: {
  gap: Gap;
  deciding: boolean;
  onDecide: (status: Gap["status"], note?: string) => void;
}) {
  const [note, setNote] = useState(gap.note ?? "");
  const btn = "rounded border border-ink/30 bg-white px-3 py-1 disabled:opacity-60 text-sm";
  return (
    <div className="mt-3 space-y-3 border-t border-ink/20 pt-3" aria-live="polite">
      <div className="space-y-2">
        <p className="text-xs uppercase tracking-wide text-ink/60">Buscas externas realizadas</p>
        <ul className="space-y-2">
          {gap.searches.map((s, idx) => (
            <li key={idx} className="rounded border border-ink/10 bg-paper p-2.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-semibold uppercase tracking-wider text-ink/70">
                  {s.source === "openalex" ? "OpenAlex" : "Semantic Scholar"}
                </span>
                <span className={s.status === "ok" ? "text-done font-medium" : "text-gap font-medium"}>
                  {s.status === "ok" ? `${s.total ?? 0} resultado(s)` : "Falha na busca"}
                </span>
              </div>
              <p className="mt-1 font-mono text-ink/80">Busca: {s.query}</p>
              {s.results && s.results.length > 0 && (
                <ul className="mt-2 list-disc pl-4 space-y-1">
                  {s.results.map((r, rIdx) => (
                    <li key={rIdx}>
                      <span>{r.title}</span> {r.year && <span className="text-ink/60">({r.year})</span>}
                      {r.doi && (
                        <a
                          href={`https://doi.org/${r.doi}`}
                          target="_blank"
                          rel="noreferrer"
                          className="ml-1 text-available underline"
                        >
                          DOI
                        </a>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div className="space-y-2 border-t border-ink/10 pt-3">
        <p className="text-xs uppercase tracking-wide text-ink/60">Decisão sobre a lacuna</p>
        <label className="block">
          <span className="sr-only">Anotação pessoal</span>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={500}
            placeholder="Anotação pessoal sobre a lacuna (opcional)"
            className="w-full rounded border border-ink/30 bg-white px-2 py-1 text-xs"
          />
        </label>
        <div className="flex flex-wrap items-center gap-2">
          {gap.status !== "adopted_as_problem" && (
            <button
              disabled={deciding}
              onClick={() => onDecide("adopted_as_problem", note)}
              className={`${btn} bg-done text-white border-done`}
            >
              Adotar como problema de pesquisa
            </button>
          )}
          {gap.status !== "dismissed" && (
            <button
              disabled={deciding}
              onClick={() => onDecide("dismissed", note)}
              className={btn}
            >
              Descartar lacuna
            </button>
          )}
          {gap.status !== "open" && (
            <button
              disabled={deciding}
              onClick={() => onDecide("open", note)}
              className={btn}
            >
              Reabrir como aberta
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function EvidencePanel({
  link,
  evidence,
  error,
  deciding,
  onOpenPdf,
  onDecide,
}: {
  link: MapLink;
  evidence: Evidence[] | null;
  error: string | null;
  deciding: boolean;
  onOpenPdf: (documentId: string, page: number) => void;
  onDecide: (body: { action: "confirm" | "reject" | "edit"; relation?: string; note?: string }) => void;
}) {
  const [relation, setRelation] = useState(link.relation);
  const [note, setNote] = useState("");
  const btn = "rounded border border-ink/30 bg-white px-3 py-1 disabled:opacity-60";
  return (
    <div className="mt-3 space-y-3 border-t border-ink/20 pt-3" aria-live="polite">
      {link.rationale && link.status === "suggested" && (
        <p className="text-ink/80">Justificativa da IA (sugestão, não confirmada): {link.rationale}</p>
      )}
      {error && (
        <p role="alert" className="text-danger">
          {error}
        </p>
      )}
      {evidence === null && !error && <p>Carregando evidência…</p>}
      {evidence?.map((ev) => (
        <figure key={ev.side} className="rounded border border-ink/20 bg-paper p-3">
          <figcaption className="text-xs uppercase tracking-wide text-ink/60">
            {ev.side === "source" ? "Evidência de origem" : "Evidência de destino"} · {ev.concept}
          </figcaption>
          <blockquote className="font-serif-academic mt-2 leading-relaxed">
            <span className="text-ink/60">{ev.context_before}</span>
            <mark className="bg-available/20 px-0.5 text-ink">{ev.quote}</mark>
            <span className="text-ink/60">{ev.context_after}</span>
          </blockquote>
          <p className="mt-2 text-ink/70">
            {ev.document_title ?? "Documento"} · página {ev.page}
          </p>
          {ev.has_pdf ? (
            <button onClick={() => onOpenPdf(ev.document_id, ev.page)} className="mt-1 text-available underline">
              Abrir PDF na página {ev.page}
            </button>
          ) : (
            <p className="mt-1 text-ink/60">Documento sem PDF anexado (apenas metadados).</p>
          )}
        </figure>
      ))}
      <div className="space-y-3 border-t border-ink/10 pt-3">
        <p className="text-xs uppercase tracking-wide text-ink/60">Sua decisão</p>
        <div className="flex flex-wrap items-center gap-2">
          <button disabled={deciding || link.status === "confirmed"} onClick={() => onDecide({ action: "confirm" })} className={btn}>
            Confirmar
          </button>
          <label className="flex items-center gap-2">
            <span className="sr-only">Tipo de relação</span>
            <select value={relation} onChange={(e) => setRelation(e.target.value)} className="rounded border border-ink/30 bg-white px-2 py-1">
              {Object.entries(RELATION_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <button
            disabled={deciding || relation === link.relation}
            onClick={() => onDecide({ action: "edit", relation })}
            className={btn}
          >
            Editar tipo
          </button>
        </div>
        {link.status !== "rejected" && (
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex-1">
              <span className="sr-only">Motivo da rejeição (opcional)</span>
              <input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                maxLength={500}
                placeholder="Motivo da rejeição (opcional)"
                className="w-full rounded border border-ink/30 bg-white px-2 py-1"
              />
            </label>
            <button disabled={deciding} onClick={() => onDecide({ action: "reject", note: note || undefined })} className={btn}>
              Rejeitar
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  api,
  GAP_STATUS_LABELS,
  Gap,
  SectionComment,
  SharedProjectData,
  WORK_LABELS,
} from "@/lib/api";
import { Logo } from "@/components/logo";
import {
  AdvisorBubble,
  AlertBanner,
  Button,
  StatusBadge,
  StudentCard,
} from "@/components/ui";

function extractParagraphsFromTiptap(content: Record<string, unknown> | undefined): string[] {
  if (!content || typeof content !== "object") return [];
  const out: string[] = [];
  function walk(node: unknown): string {
    if (!node || typeof node !== "object") return "";
    const n = node as { type?: string; text?: string; content?: unknown[] };
    if (typeof n.text === "string") return n.text;
    if (Array.isArray(n.content)) {
      return n.content.map(walk).join("");
    }
    return "";
  }
  const topContent = (content as { content?: unknown[] }).content;
  if (Array.isArray(topContent)) {
    for (const block of topContent) {
      const text = walk(block).trim();
      if (text) out.push(text);
    }
  }
  return out;
}

function parseAnchoredComment(raw: string): { anchor: string | null; body: string } {
  const match = raw.match(/^\[Trecho em revisão:\s*"([^"]+)"\]\n?([\s\S]*)$/);
  if (!match) return { anchor: null, body: raw };
  return { anchor: match[1], body: match[2] };
}

export default function AdvisorShareView({ token }: { token: string }) {
  const [data, setData] = useState<SharedProjectData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null);
  const [advisorName, setAdvisorName] = useState("Profa. Dra. Helena Costa");
  const [advisorEmail, setAdvisorEmail] = useState("helena.costa@ufjf.br");
  const [anchorQuote, setAnchorQuote] = useState<string | null>(null);
  const [commentText, setCommentText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api<SharedProjectData>(`/shared/${token}`)
      .then((res) => {
        if (cancelled) return;
        setData(res);
        if (res.sections.length > 0) {
          setSelectedSectionId(res.sections[0].id);
        }
      })
      .catch((err) => {
        if (cancelled) return;
        setError(
          err instanceof Error
            ? err.message
            : "Não foi possível carregar o link de revisão do orientador."
        );
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  const labelOf = useMemo(
    () => new Map((data?.concepts ?? []).map((c) => [c.id, c.label])),
    [data]
  );

  const activeSection = useMemo(
    () => (data?.sections ?? []).find((s) => s.id === selectedSectionId) ?? null,
    [data, selectedSectionId]
  );

  const activeParagraphs = useMemo(
    () => extractParagraphsFromTiptap(activeSection?.content),
    [activeSection]
  );

  async function handleSubmitComment(e: React.FormEvent) {
    e.preventDefault();
    if (!activeSection || !commentText.trim() || !advisorName.trim() || !advisorEmail.trim()) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const created = await api<SectionComment>(`/shared/${token}/comments`, {
        method: "POST",
        body: {
          section_id: activeSection.id,
          author_name: advisorName.trim(),
          author_email: advisorEmail.trim(),
          anchor_quote: anchorQuote,
          content: commentText.trim(),
        },
      });
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          sections: prev.sections.map((s) =>
            s.id === activeSection.id
              ? { ...s, comments: [...s.comments, created] }
              : s
          ),
        };
      });
      setCommentText("");
      setAnchorQuote(null);
      setNotice("Parecer registrado diretamente na seção do orientando.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao registrar parecer.");
    } finally {
      setSubmitting(false);
    }
  }

  const payload = data?.report_payload;

  return (
    <div className="min-h-screen flex flex-col bg-paper text-ink">
      {/* Cabeçalho fixo de 68 px no padrão do Manual v2 */}
      <header className="sticky top-0 z-30 h-[68px] w-full border-b border-borda bg-paper/95 backdrop-blur">
        <div className="mx-auto flex h-full max-w-[1440px] items-center justify-between px-6 sm:px-10">
          <Logo variant="padrao" withSignature={false} className="w-[190px]" />
          <div className="flex items-center gap-3">
            <span className="rounded-[8px] border border-purple bg-skipped-bg px-3 py-1 text-[13px] font-bold uppercase tracking-wider text-purple">
              Revisão do Orientador Humano
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1440px] flex-1 px-6 py-8 sm:px-10 space-y-6">
        {error && <AlertBanner variant="error">{error}</AlertBanner>}
        {notice && <AlertBanner variant="notice">{notice}</AlertBanner>}

        {!data && !error && (
          <p className="py-10 text-[15px] text-locked">
            Carregando relatório e manuscrito para revisão do orientador…
          </p>
        )}

        {data && payload && (
          <>
            {/* Cabeçalho do Projeto Compartilhado */}
            <div className="flex flex-wrap items-baseline justify-between gap-4 border-b border-borda pb-5">
              <div>
                <span className="text-[13px] font-bold uppercase tracking-wider text-locked">
                  Painel de Supervisão Acadêmica · {WORK_LABELS[data.project.work] ?? data.project.work}
                </span>
                <h1 className="mt-1 font-display text-3xl sm:text-[36px] text-ink">
                  {data.project.title}
                </h1>
                <p className="mt-1 text-[15px] text-locked">
                  {data.project.institution ?? "Instituição não informada"} · Norma{" "}
                  {data.project.citation_style.toUpperCase()} · Prazo{" "}
                  {data.project.deadline ?? "a definir"}
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-2.5">
                <StatusBadge
                  status="done"
                  label={`${payload.progress_tree.completed_count} Concluídas`}
                />
                {payload.progress_tree.skipped_count > 0 && (
                  <StatusBadge
                    status="skipped"
                    label={`${payload.progress_tree.skipped_count} Puladas`}
                  />
                )}
                <StatusBadge
                  status="locked"
                  label={`${payload.progress_tree.pending_count} Pendentes`}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 items-start">
              {/* Coluna Esquerda (7 cols): Auditoria de 1 Página + Manuscrito com Seleção de Trecho */}
              <div className="lg:col-span-7 space-y-6">
                {/* Auditoria de Etapas Puladas e Evidências */}
                <section className="rounded-[16px] border border-borda bg-superficie p-6 space-y-5">
                  <h2 className="font-display text-2xl text-ink border-b border-borda pb-3">
                    1. Resumo de progresso e evidências verificadas
                  </h2>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div className="rounded-[12px] border border-borda bg-paper/40 p-3.5">
                      <span className="text-[13px] font-bold uppercase tracking-wider text-locked">
                        Fontes lidas
                      </span>
                      <p className="mt-1 font-display text-2xl text-ink">
                        {payload.knowledge_map.documents_count}
                      </p>
                    </div>
                    <div className="rounded-[12px] border border-borda bg-paper/40 p-3.5">
                      <span className="text-[13px] font-bold uppercase tracking-wider text-locked">
                        Citações verificadas
                      </span>
                      <p className="mt-1 font-display text-2xl text-done">
                        {payload.knowledge_map.verified_claims_count}
                      </p>
                    </div>
                    <div className="rounded-[12px] border border-borda bg-paper/40 p-3.5">
                      <span className="text-[13px] font-bold uppercase tracking-wider text-locked">
                        Ligações confirmadas
                      </span>
                      <p className="mt-1 font-display text-2xl text-done">
                        {payload.knowledge_map.confirmed_relations_count}
                      </p>
                    </div>
                    <div className="rounded-[12px] border border-borda bg-paper/40 p-3.5">
                      <span className="text-[13px] font-bold uppercase tracking-wider text-locked">
                        Interações com IA
                      </span>
                      <p className="mt-1 font-display text-2xl text-purple">
                        {payload.ai_usage_audit.total_ai_interactions}
                      </p>
                    </div>
                  </div>

                  {payload.progress_tree.skipped_with_warning.length > 0 && (
                    <div className="rounded-[12px] border border-purple/40 bg-skipped-bg p-4 space-y-2">
                      <span className="text-[13px] font-bold uppercase tracking-wider text-purple">
                        Atenção: Etapas puladas pelo orientando com justificativa
                      </span>
                      <ul className="space-y-2 text-[15px]">
                        {payload.progress_tree.skipped_with_warning.map((sk) => (
                          <li key={sk.key} className="text-ink">
                            <strong>{sk.title}:</strong> “{sk.skipped_reason}”
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {payload.knowledge_map.gaps.length > 0 && (
                    <div className="space-y-2">
                      <span className="text-[13px] font-bold uppercase tracking-wider text-locked">
                        Lacunas bibliográficas identificadas ({payload.knowledge_map.gaps.length})
                      </span>
                      <ul className="space-y-2 text-[15px]">
                        {payload.knowledge_map.gaps.map((g, i) => (
                          <li
                            key={i}
                            className="rounded-[10px] border-2 border-dotted border-purple bg-paper/40 p-3"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="font-bold text-ink">
                                {labelOf.get(g.concept_a) ?? g.concept_a}{" "}
                                <span className="text-purple">↔</span>{" "}
                                {labelOf.get(g.concept_b) ?? g.concept_b}
                              </span>
                              <span className="text-[13px] font-bold uppercase tracking-wider text-purple">
                                {GAP_STATUS_LABELS[g.status as Gap["status"]] ?? g.status}
                              </span>
                            </div>
                            {g.note && <p className="mt-1 text-[14px] text-locked">{g.note}</p>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </section>

                {/* Leitura das Seções do Manuscrito com Grifo de Trecho em Revisão */}
                <section className="rounded-[16px] border border-borda bg-superficie p-6 space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-borda pb-3">
                    <div>
                      <h2 className="font-display text-2xl text-ink">
                        2. Manuscrito do aluno (clique em um parágrafo para grifar)
                      </h2>
                      <p className="text-[14px] text-locked">
                        Selecione a seção abaixo e clique em qualquer trecho para ancorar sua pergunta em laranja.
                      </p>
                    </div>
                  </div>

                  {/* Seletor de Seções */}
                  <div className="flex flex-wrap gap-2">
                    {data.sections.map((sec) => {
                      const active = sec.id === selectedSectionId;
                      return (
                        <button
                          key={sec.id}
                          type="button"
                          onClick={() => {
                            setSelectedSectionId(sec.id);
                            setAnchorQuote(null);
                          }}
                          className={`min-h-[42px] rounded-[10px] px-3.5 text-[15px] font-bold transition cursor-pointer border ${
                            active
                              ? "border-2 border-purple bg-purple text-paper"
                              : "border-borda bg-paper/50 text-ink hover:bg-paper"
                          }`}
                        >
                          {sec.title} ({sec.comments.length})
                        </button>
                      );
                    })}
                  </div>

                  {/* Conteúdo da Seção Ativa */}
                  {activeSection && (
                    <div className="rounded-[12px] border border-borda bg-paper/40 p-5 space-y-4">
                      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-borda pb-2.5 text-[14px]">
                        <span className="font-bold text-ink">{activeSection.title}</span>
                        <span className="text-locked">
                          {activeSection.concept_ids.length} conceito(s) vinculado(s)
                        </span>
                      </div>

                      {activeParagraphs.length === 0 ? (
                        <p className="font-serif-academic text-[18px] italic text-locked py-4">
                          O aluno ainda não redigiu parágrafos nesta seção. Você pode deixar uma orientação estrutural ao lado.
                        </p>
                      ) : (
                        <div className="space-y-3">
                          {activeParagraphs.map((para, idx) => {
                            const isAnchored = anchorQuote === para;
                            return (
                              <div
                                key={idx}
                                onClick={() =>
                                  setAnchorQuote(isAnchored ? null : para.slice(0, 240))
                                }
                                title="Clique para marcar este trecho em revisão"
                                className="group cursor-pointer rounded-[8px] p-2 transition hover:bg-superficie"
                              >
                                <p className="font-serif-academic text-[19px] leading-[1.6] text-ink">
                                  {isAnchored ? (
                                    <mark className="mark-orange">{para}</mark>
                                  ) : (
                                    para
                                  )}
                                </p>
                                <span className="mt-1 inline-block text-[13px] font-bold text-purple opacity-0 group-hover:opacity-100">
                                  {isAnchored
                                    ? "✓ Trecho marcado para pergunta"
                                    : "+ Grifar este trecho para comentar"}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}
                </section>
              </div>

              {/* Coluna Direita (5 cols): Parecer e Perguntas Socráticas do Orientador */}
              <aside className="lg:col-span-5 rounded-[16px] border border-borda bg-superficie p-6 space-y-5 sticky top-[88px]">
                <div className="border-b border-borda pb-3">
                  <span className="text-[13px] font-bold uppercase tracking-wider text-purple">
                    Diálogo Orientador ↔ Orientando
                  </span>
                  <h2 className="mt-1 font-display text-2xl text-ink">
                    Parecer em {activeSection?.title ?? "Seção"}
                  </h2>
                </div>

                {/* Lista de Comentários da Seção */}
                <div className="space-y-3 max-h-[340px] overflow-y-auto pr-1">
                  {!activeSection || activeSection.comments.length === 0 ? (
                    <p className="text-[15px] text-locked">
                      Nenhuma pergunta registrada nesta seção ainda.
                    </p>
                  ) : (
                    activeSection.comments.map((c) => {
                      const parsed = parseAnchoredComment(c.content);
                      const isStudent = c.author_email.includes("demo") || c.author_email.includes("estudante");
                      const label = isStudent
                        ? `Orientando · ${c.author_name || c.author_email}`
                        : `Orientador · ${c.author_name || c.author_email}`;

                      return (
                        <div key={c.id} className="space-y-1">
                          {parsed.anchor && (
                            <div className="rounded-t-[10px] border border-b-0 border-borda bg-paper px-3 py-2 text-[14px]">
                              <span className="block text-[12px] font-bold uppercase tracking-wider text-locked">
                                Trecho grifado:
                              </span>
                              <mark className="mark-orange font-serif-academic text-[15px]">
                                “{parsed.anchor}”
                              </mark>
                            </div>
                          )}
                          {isStudent ? (
                            <StudentCard label={label}>
                              <p className="whitespace-pre-wrap">{parsed.body}</p>
                            </StudentCard>
                          ) : (
                            <AdvisorBubble label={label}>
                              <p className="whitespace-pre-wrap">{parsed.body}</p>
                            </AdvisorBubble>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>

                {/* Formulário para o Orientador Humano registrar pergunta/parecer */}
                <form onSubmit={handleSubmitComment} className="border-t border-borda pt-4 space-y-3.5">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <label className="block text-[14px] font-medium text-ink">
                      Seu nome
                      <input
                        type="text"
                        required
                        value={advisorName}
                        onChange={(e) => setAdvisorName(e.target.value)}
                        className="mt-1 w-full h-[42px] rounded-[10px] border border-borda bg-paper/40 px-3 text-[15px] text-ink"
                      />
                    </label>
                    <label className="block text-[14px] font-medium text-ink">
                      Seu e-mail institucional
                      <input
                        type="email"
                        required
                        value={advisorEmail}
                        onChange={(e) => setAdvisorEmail(e.target.value)}
                        className="mt-1 w-full h-[42px] rounded-[10px] border border-borda bg-paper/40 px-3 text-[15px] text-ink"
                      />
                    </label>
                  </div>

                  {anchorQuote && (
                    <div className="flex items-start justify-between gap-2 rounded-[10px] border border-borda bg-paper p-3 text-[14px]">
                      <div>
                        <span className="block text-[12px] font-bold uppercase tracking-wider text-locked">
                          Trecho do manuscrito selecionado:
                        </span>
                        <mark className="mark-orange font-serif-academic text-[15px]">
                          “{anchorQuote}”
                        </mark>
                      </div>
                      <button
                        type="button"
                        onClick={() => setAnchorQuote(null)}
                        className="font-bold text-locked hover:text-ink cursor-pointer"
                      >
                        ✕
                      </button>
                    </div>
                  )}

                  <label className="block text-[15px] font-medium text-ink">
                    Pergunta socrática ou recomendação ao orientando
                    <textarea
                      rows={3}
                      required
                      value={commentText}
                      onChange={(e) => setCommentText(e.target.value)}
                      placeholder="Ex.: Qual autor do seu referencial sustenta esta hipótese?"
                      className="mt-1.5 w-full resize-none rounded-[10px] border border-borda bg-paper/40 p-3 text-[15px] text-ink focus:border-purple"
                    />
                  </label>

                  {/* Único botão principal roxo da tela */}
                  <Button
                    type="submit"
                    variant="primary"
                    disabled={submitting || !commentText.trim()}
                    className="w-full"
                  >
                    {submitting ? "Registrando parecer…" : "Registrar parecer na seção"}
                  </Button>
                </form>
              </aside>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

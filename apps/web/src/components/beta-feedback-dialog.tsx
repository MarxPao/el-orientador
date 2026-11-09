"use client";

import React, { useState } from "react";
import { submitBetaFeedback } from "@/lib/api";
import { CheckIcon, AlertIcon } from "./ui";

export function BetaFeedbackDialog({ projectId }: { projectId?: string }) {
  const [open, setOpen] = useState(false);
  const [overallRating, setOverallRating] = useState(5);
  const [socraticHelpful, setSocraticHelpful] = useState(5);
  const [evidenceTrust, setEvidenceTrust] = useState(5);
  const [reliefLevel, setReliefLevel] = useState(5);
  const [pricingPref, setPricingPref] = useState("passe_projeto");
  const [brandImpression, setBrandImpression] = useState("Sóbrio, rigoroso e sem alucinações");
  const [comments, setComments] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await submitBetaFeedback({
        project_id: projectId,
        overall_rating: overallRating,
        socratic_gate_helpful: socraticHelpful,
        evidence_trust: evidenceTrust,
        relief_level: reliefLevel,
        pricing_preference: pricingPref,
        brand_impression: brandImpression.trim() || "Sóbrio",
        comments: comments.trim() || undefined,
      });
      setSubmitted(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Falha ao enviar feedback.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => {
          setOpen(true);
          setSubmitted(false);
          setError(null);
        }}
        className="inline-flex min-h-[44px] items-center gap-1.5 rounded-[8px] border border-purple/30 bg-purple/5 px-3 py-1.5 text-[13px] font-medium text-purple hover:bg-purple/10 transition cursor-pointer"
        aria-label="Abrir formulário de feedback do piloto acadêmico"
      >
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          className="h-4 w-4 shrink-0"
          aria-hidden="true"
        >
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
        <span>Feedback do Beta</span>
      </button>

      {open && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="feedback-dialog-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4 backdrop-blur-xs"
        >
          <div className="relative max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-[12px] border border-borda bg-paper p-6 shadow-xl sm:p-8">
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="absolute top-4 right-4 flex h-9 w-9 items-center justify-center rounded-[6px] text-locked hover:bg-borda/50 hover:text-ink cursor-pointer"
              aria-label="Fechar"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>

            <div className="mb-6 space-y-1">
              <span className="text-[11px] font-bold uppercase tracking-wider text-purple">
                Coorte do Piloto Acadêmico (T6.5)
              </span>
              <h2 id="feedback-dialog-title" className="font-serif text-2xl font-bold text-ink">
                Avaliação da Experiência
              </h2>
              <p className="text-[14px] text-locked">
                Sua resposta calibrará os modelos de orientação e o preço de sustentabilidade do projeto.
              </p>
            </div>

            {submitted ? (
              <div className="space-y-4 py-4 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-done/20 text-done">
                  <CheckIcon className="h-6 w-6" />
                </div>
                <h3 className="font-serif text-lg font-bold text-ink">Parecer registrado com sucesso</h3>
                <p className="text-[14px] text-locked">
                  Agradecemos imensamente sua colaboração para o desenvolvimento de uma orientação acadêmica rigorosa e fundamentada.
                </p>
                <div className="pt-2">
                  <button
                    type="button"
                    onClick={() => setOpen(false)}
                    className="inline-flex min-h-[44px] items-center justify-center rounded-[8px] bg-purple px-5 text-[14px] font-bold text-paper transition hover:bg-purple/90 cursor-pointer"
                  >
                    Concluir
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-5">
                {error && (
                  <div className="flex items-start gap-2 rounded-[8px] border border-orange/40 bg-orange/10 p-3 text-[13px] text-ink">
                    <AlertIcon className="h-4 w-4 shrink-0 text-orange" />
                    <span>{error}</span>
                  </div>
                )}

                {/* Rating 1: Geral */}
                <div className="space-y-1.5">
                  <label className="block text-[13px] font-bold text-ink">
                    1. Avaliação geral da orientação recebida (1 a 5)
                  </label>
                  <div className="flex gap-2">
                    {[1, 2, 3, 4, 5].map((val) => (
                      <button
                        key={val}
                        type="button"
                        onClick={() => setOverallRating(val)}
                        className={`flex h-10 w-10 items-center justify-center rounded-[8px] border text-[14px] font-bold transition cursor-pointer ${
                          overallRating === val
                            ? "border-purple bg-purple text-paper"
                            : "border-borda bg-superficie text-ink hover:bg-borda/30"
                        }`}
                      >
                        {val}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Rating 2: Gate Socrático */}
                <div className="space-y-1.5">
                  <label className="block text-[13px] font-bold text-ink">
                    2. O questionamento socrático ajudou a amadurecer a pesquisa?
                  </label>
                  <div className="flex gap-2">
                    {[1, 2, 3, 4, 5].map((val) => (
                      <button
                        key={val}
                        type="button"
                        onClick={() => setSocraticHelpful(val)}
                        className={`flex h-10 w-10 items-center justify-center rounded-[8px] border text-[14px] font-bold transition cursor-pointer ${
                          socraticHelpful === val
                            ? "border-purple bg-purple text-paper"
                            : "border-borda bg-superficie text-ink hover:bg-borda/30"
                        }`}
                      >
                        {val}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Rating 3: Confiança na verificação literal */}
                <div className="space-y-1.5">
                  <label className="block text-[13px] font-bold text-ink">
                    3. Confiança nas citações literais verificadas (Regra 1)
                  </label>
                  <div className="flex gap-2">
                    {[1, 2, 3, 4, 5].map((val) => (
                      <button
                        key={val}
                        type="button"
                        onClick={() => setEvidenceTrust(val)}
                        className={`flex h-10 w-10 items-center justify-center rounded-[8px] border text-[14px] font-bold transition cursor-pointer ${
                          evidenceTrust === val
                            ? "border-purple bg-purple text-paper"
                            : "border-borda bg-superficie text-ink hover:bg-borda/30"
                        }`}
                      >
                        {val}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Rating 4: Alívio de ansiedade com prazos */}
                <div className="space-y-1.5">
                  <label className="block text-[13px] font-bold text-ink">
                    4. Nível de clareza e alívio com prazos e etapas
                  </label>
                  <div className="flex gap-2">
                    {[1, 2, 3, 4, 5].map((val) => (
                      <button
                        key={val}
                        type="button"
                        onClick={() => setReliefLevel(val)}
                        className={`flex h-10 w-10 items-center justify-center rounded-[8px] border text-[14px] font-bold transition cursor-pointer ${
                          reliefLevel === val
                            ? "border-purple bg-purple text-paper"
                            : "border-borda bg-superficie text-ink hover:bg-borda/30"
                        }`}
                      >
                        {val}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Pricing Model preference */}
                <div className="space-y-2">
                  <label className="block text-[13px] font-bold text-ink">
                    5. Modelo de sustentabilidade preferido para o serviço
                  </label>
                  <div className="space-y-2 text-[13px]">
                    <label className="flex items-start gap-2.5 rounded-[8px] border border-borda bg-superficie p-2.5 cursor-pointer hover:bg-borda/20">
                      <input
                        type="radio"
                        name="pricing"
                        value="passe_projeto"
                        checked={pricingPref === "passe_projeto"}
                        onChange={(e) => setPricingPref(e.target.value)}
                        className="mt-0.5 accent-purple"
                      />
                      <div>
                        <strong className="block font-medium text-ink">
                          Passe por Projeto (R$ 89 a R$ 149)
                        </strong>
                        <span className="text-locked text-[12px]">
                          Pagamento único válido por todo o ciclo do trabalho até a entrega final.
                        </span>
                      </div>
                    </label>

                    <label className="flex items-start gap-2.5 rounded-[8px] border border-borda bg-superficie p-2.5 cursor-pointer hover:bg-borda/20">
                      <input
                        type="radio"
                        name="pricing"
                        value="mensal"
                        checked={pricingPref === "mensal"}
                        onChange={(e) => setPricingPref(e.target.value)}
                        className="mt-0.5 accent-purple"
                      />
                      <div>
                        <strong className="block font-medium text-ink">
                          Assinatura Mensal (R$ 29 a R$ 49/mês)
                        </strong>
                        <span className="text-locked text-[12px]">
                          Pagamento recorrente somente nos meses em que estiver redigindo.
                        </span>
                      </div>
                    </label>
                  </div>
                </div>

                {/* Brand impression */}
                <div className="space-y-1.5">
                  <label htmlFor="brand-impression-input" className="block text-[13px] font-bold text-ink">
                    6. O que achou do tom sóbrio e da identidade (&quot;El Orientador&quot;)?
                  </label>
                  <input
                    id="brand-impression-input"
                    type="text"
                    value={brandImpression}
                    onChange={(e) => setBrandImpression(e.target.value)}
                    required
                    className="w-full rounded-[8px] border border-borda bg-superficie px-3 py-2 text-[13px] text-ink focus:border-purple focus:outline-hidden"
                  />
                </div>

                {/* Comments */}
                <div className="space-y-1.5">
                  <label htmlFor="beta-comments-input" className="block text-[13px] font-bold text-ink">
                    7. Sugestões, lacunas encontradas ou comentários
                  </label>
                  <textarea
                    id="beta-comments-input"
                    rows={3}
                    value={comments}
                    onChange={(e) => setComments(e.target.value)}
                    placeholder="Conte o que mais ajudou e o que podemos aprimorar..."
                    className="w-full rounded-[8px] border border-borda bg-superficie px-3 py-2 text-[13px] text-ink focus:border-purple focus:outline-hidden"
                  />
                </div>

                <div className="flex items-center justify-end gap-3 pt-3">
                  <button
                    type="button"
                    onClick={() => setOpen(false)}
                    className="min-h-[44px] rounded-[8px] px-4 text-[14px] font-medium text-locked hover:text-ink cursor-pointer"
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="inline-flex min-h-[44px] items-center justify-center rounded-[8px] bg-purple px-6 text-[14px] font-bold text-paper transition hover:bg-purple/90 disabled:opacity-50 cursor-pointer"
                  >
                    {submitting ? "Enviando..." : "Enviar Avaliação"}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </>
  );
}

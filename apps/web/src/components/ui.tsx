import React from "react";
import { AuthorshipPrism, ProgressNode } from "@/lib/api";

export type NodeStatus = ProgressNode["status"];

export function AlertIcon({ className = "h-5 w-5 shrink-0 text-purple" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

export function CheckIcon({ className = "h-4 w-4 shrink-0" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

export function ArrowRightIcon({ className = "h-4 w-4 shrink-0" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <circle cx="12" cy="12" r="9" />
      <polyline points="12 8 16 12 12 16" />
      <line x1="8" y1="12" x2="16" y2="12" />
    </svg>
  );
}

export function LockIcon({ className = "h-4 w-4 shrink-0" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

export function GapIcon({ className = "h-4 w-4 shrink-0" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  );
}

/**
 * Alerta / Erro padronizado (Manual v2): nunca só cor, sem emoji e sem vermelho.
 * Usa ícone SVG (triângulo com "!") em roxo ou tinta acompanhado de texto claro.
 */
export function AlertBanner({
  children,
  variant = "error",
  className = "",
}: {
  children: React.ReactNode;
  variant?: "error" | "notice" | "gap";
  className?: string;
}) {
  if (variant === "notice") {
    return (
      <div
        role="status"
        className={`flex items-start gap-3 rounded-[10px] border border-done bg-superficie px-4 py-3 text-[15px] text-ink ${className}`}
      >
        <CheckIcon className="mt-0.5 h-5 w-5 shrink-0 text-done" />
        <div>{children}</div>
      </div>
    );
  }

  return (
    <div
      role="alert"
      className={`flex items-start gap-3 rounded-[10px] border-2 ${
        variant === "gap" ? "border-dashed border-purple" : "border-purple"
      } bg-superficie px-4 py-3 text-[15px] text-ink ${className}`}
    >
      <AlertIcon className="mt-0.5 h-5 w-5 shrink-0 text-purple" />
      <div className="leading-snug">{children}</div>
    </div>
  );
}

/**
 * Botão padronizado (Manual v2):
 * - primary: roxo (#4B2A7B), texto papel (#F6EEDC), 52 px de altura, raio 10 px. UM por tela.
 * - secondary: contorno roxo, fundo superfície ou transparente, altura mínima 44 px, raio 10 px.
 */
export function Button({
  variant = "primary",
  className = "",
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary";
}) {
  const base =
    "inline-flex items-center justify-center rounded-[10px] px-5 text-[15px] font-medium transition cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed";
  const styles =
    variant === "primary"
      ? "h-[52px] bg-purple text-paper hover:opacity-95"
      : "min-h-[44px] border-2 border-purple bg-superficie text-purple hover:bg-purple/5";

  return (
    <button className={`${base} ${styles} ${className}`} {...props}>
      {children}
    </button>
  );
}

/**
 * Balão de pergunta / comentário do orientador: fundo roxo com texto papel crema, raio 12 px.
 */
export function AdvisorBubble({
  children,
  label = "Orientador",
  className = "",
}: {
  children: React.ReactNode;
  label?: string;
  className?: string;
}) {
  return (
    <div className={`rounded-[12px] bg-purple p-4 text-paper ${className}`}>
      {label && (
        <div className="mb-1 text-[13px] font-bold uppercase tracking-wider text-paper/85">
          {label}
        </div>
      )}
      <div className="text-[15px] leading-relaxed">{children}</div>
    </div>
  );
}

/**
 * Cartão de resposta / comentário do aluno: superfície branca com borda crema.
 */
export function StudentCard({
  children,
  label = "Sua resposta",
  className = "",
}: {
  children: React.ReactNode;
  label?: string;
  className?: string;
}) {
  return (
    <div className={`rounded-[12px] border border-borda bg-superficie p-4 text-ink ${className}`}>
      {label && (
        <div className="mb-1 text-[13px] font-bold uppercase tracking-wider text-locked">
          {label}
        </div>
      )}
      <div className="text-[15px] leading-relaxed">{children}</div>
    </div>
  );
}

export const STATUS_LABELS: Record<NodeStatus | "gap", string> = {
  done: "Concluído",
  available: "Disponível",
  locked: "Bloqueado",
  skipped: "Pulado",
  needs_review: "Revisar",
  gap: "Lacuna",
};

/**
 * Crachá de estado padronizado (mesmo código em árvore, contadores, relatório e mapa):
 * - concluído = oliva, com ícone e rótulo
 * - disponível = fundo laranja com texto tinta, com ícone e rótulo
 * - lacuna / needs_review = borda roxa pontilhada, com ícone e rótulo
 * - bloqueado = cinza quente
 * - pulado = roxo claro com rótulo
 */
export function StatusBadge({
  status,
  label,
  className = "",
}: {
  status: NodeStatus | "gap";
  label?: string;
  className?: string;
}) {
  const text = label ?? STATUS_LABELS[status] ?? status;

  if (status === "done") {
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded-[6px] bg-done px-2.5 py-0.5 text-[13px] font-medium text-paper ${className}`}
      >
        <CheckIcon className="h-3.5 w-3.5" />
        <span>{text}</span>
      </span>
    );
  }

  if (status === "available") {
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded-[6px] bg-orange px-2.5 py-0.5 text-[13px] font-medium text-ink ${className}`}
      >
        <ArrowRightIcon className="h-3.5 w-3.5" />
        <span>{text}</span>
      </span>
    );
  }

  if (status === "needs_review" || status === "gap") {
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded-[6px] border-2 border-dotted border-purple bg-superficie px-2.5 py-0.5 text-[13px] font-medium text-purple ${className}`}
      >
        <GapIcon className="h-3.5 w-3.5" />
        <span>{text}</span>
      </span>
    );
  }

  if (status === "skipped") {
    return (
      <span
        className={`inline-flex items-center gap-1.5 rounded-[6px] bg-skipped-bg px-2.5 py-0.5 text-[13px] font-medium text-purple ${className}`}
      >
        <span>{text}</span>
      </span>
    );
  }

  // locked
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-[6px] border border-dashed border-locked/50 bg-paper px-2.5 py-0.5 text-[13px] font-medium text-locked ${className}`}
    >
      <LockIcon className="h-3.5 w-3.5" />
      <span>{text}</span>
    </span>
  );
}

/**
 * Prisma de Autoria (Manual v2):
 * Barra tripartida que mede a proporção entre:
 * 1. Escrita autoral humana (oliva #5F6E2F)
 * 2. Lapidação gramatical/estilo assistida (roxo #4B2A7B) — isenta de declaração textual na maioria das editoras
 * 3. Redação por IA ancorada em citações verificadas (laranja #E8761E, texto tinta #241E1A) — exige declaração
 */
export function AuthorshipPrismBar({
  prism,
  title = "Prisma de autoria e exigência de declaração",
}: {
  prism: AuthorshipPrism;
  title?: string;
}) {
  return (
    <div
      aria-label="Prisma de autoria"
      className="rounded-[12px] border border-borda bg-superficie p-4 space-y-2.5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[13px] font-bold uppercase tracking-wider text-locked">
          {title} ({prism.total_words} palavras)
        </span>

        {prism.requires_disclosure ? (
          <span className="inline-flex items-center gap-1.5 rounded-[6px] bg-orange px-2.5 py-0.5 text-[13px] font-bold text-ink">
            <AlertIcon className="h-3.5 w-3.5 shrink-0 text-ink" />
            <span>
              Declaração de IA obrigatória ({prism.ai_drafted_pct}% redigido por IA)
            </span>
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 rounded-[6px] bg-done px-2.5 py-0.5 text-[13px] font-bold text-paper">
            <CheckIcon className="h-3.5 w-3.5" />
            <span>Isento de nota de geração textual (autoria humana)</span>
          </span>
        )}
      </div>

      {/* Barra tripartida do Prisma */}
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-paper border border-borda">
        {prism.human_pct > 0 && (
          <div
            style={{ width: `${prism.human_pct}%` }}
            className="bg-done transition-all"
            title={`Escrita autoral do aluno: ${prism.human_pct}% (${prism.human_words} palavras)`}
          />
        )}
        {prism.polished_pct > 0 && (
          <div
            style={{ width: `${prism.polished_pct}%` }}
            className="bg-purple transition-all"
            title={`Lapidação gramatical/estilo: ${prism.polished_pct}% (${prism.polished_words} palavras)`}
          />
        )}
        {prism.ai_drafted_pct > 0 && (
          <div
            style={{ width: `${prism.ai_drafted_pct}%` }}
            className="bg-orange transition-all"
            title={`Redigido por IA com fontes verificadas: ${prism.ai_drafted_pct}% (${prism.ai_drafted_words} palavras)`}
          />
        )}
      </div>

      {/* Legenda detalhada */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-[13px] font-medium text-ink">
        <div className="flex flex-wrap items-center gap-4">
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-done" />
            <span>
              <strong>{prism.human_pct}%</strong> Autoral ({prism.human_words} pal.)
            </span>
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-purple" />
            <span>
              <strong>{prism.polished_pct}%</strong> Revisão leve ({prism.polished_words} pal.)
            </span>
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-orange" />
            <span>
              <strong>{prism.ai_drafted_pct}%</strong> Redigido por IA com fontes ({prism.ai_drafted_words} pal.)
            </span>
          </span>
        </div>
      </div>
    </div>
  );
}

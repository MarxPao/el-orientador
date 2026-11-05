"use client";

import { useRouter } from "next/navigation";
import React, { useRef, useState } from "react";
import { api, setToken } from "@/lib/api";
import { Logo } from "@/components/logo";
import { AlertBanner, Button } from "@/components/ui";

const inputClass =
  "mt-1.5 w-full h-[48px] rounded-[10px] border border-borda bg-superficie px-4 text-[15px] text-ink placeholder:text-locked/60 focus:border-purple outline-none transition";

export default function EntrarPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const emailRef = useRef<HTMLInputElement>(null);

  function switchMode(next: "login" | "register") {
    setMode(next);
    setError(null);
    setTimeout(() => emailRef.current?.focus(), 50);
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const body =
        mode === "login"
          ? { email: f.get("email"), password: f.get("password") }
          : {
              email: f.get("email"),
              password: f.get("password"),
              name: f.get("name") || null,
            };
      const res = await api<{ token: string }>(
        mode === "login" ? "/auth/login" : "/auth/register",
        { method: "POST", body }
      );
      setToken(res.token);
      router.push("/projetos");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Algo deu errado.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-paper text-ink">

      {/* ── Painel esquerdo (marca) ── */}
      <aside
        aria-label="Apresentação da marca"
        className="w-full lg:w-[480px] xl:w-[520px] shrink-0 bg-purple text-paper
                   flex flex-col justify-between gap-10
                   px-8 py-10 sm:px-12 sm:py-14"
      >
        {/* Topo: logo + headline — sempre visível */}
        <div>
          <Logo variant="invertida" withSignature={true} className="w-[200px] sm:w-[260px] lg:w-[280px] h-auto" />

          <h1 className="mt-8 font-display text-[24px] sm:text-[30px] lg:text-[34px] leading-tight text-paper">
            Uma pergunta por vez.<br />
            Um argumento de cada vez.
          </h1>

          <p className="mt-3 font-serif-academic text-[15px] sm:text-[17px] leading-[1.6] text-paper/85">
            O El Orientador guia sua pesquisa com o método socrático —
            cada afirmação apoiada em um trecho literal verificado,
            nenhuma resposta entregue sem antes você pensar.
          </p>

          {/* Feature list — oculta no mobile para o form aparecer acima da dobra */}
          <ul className="hidden lg:block mt-8 space-y-3">
            {[
              "Orientação socrática passo a passo",
              "Citações rastreadas até a fonte",
              "Colaboração com orientadores",
              "Relatório acadêmico gerado automaticamente",
            ].map((feat) => (
              <li key={feat} className="flex items-start gap-2.5 text-[14px] text-paper/80">
                <svg viewBox="0 0 16 16" fill="none" className="h-4 w-4 shrink-0 mt-0.5 text-orange">
                  <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" />
                  <polyline points="5,8 7,10.5 11,6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                {feat}
              </li>
            ))}
          </ul>
        </div>

        {/* Exemplo ilustrativo — oculto no mobile */}
        <div
          aria-label="Exemplo de funcionamento"
          className="hidden lg:block rounded-[14px] border border-paper/20 bg-paper p-5 text-ink space-y-4"
        >
          <p className="font-serif-academic text-[16px] leading-[1.55] text-ink">
            Toda afirmação do capítulo precisa de{" "}
            <span className="bg-orange text-ink px-1.5 py-0.5 rounded font-medium">um trecho que a sustente</span>.
          </p>
          <div className="rounded-[10px] bg-purple px-4 py-3 text-[14px] font-medium text-paper">
            Qual trecho da literatura sustenta isso?
          </div>
          <div className="flex items-center gap-3 pt-1">
            <span className="inline-block rounded-[6px] border-2 border-brand-red px-2.5 py-0.5 font-display text-[12px] tracking-wider uppercase text-brand-red -rotate-2">
              ATENÇÃO
            </span>
            <span className="text-[13px] text-ink leading-snug">
              Esta afirmação ainda não tem trecho verificado.
            </span>
          </div>
        </div>
      </aside>

      {/* ── Painel direito (formulário) ── */}
      <main className="flex-1 flex items-center justify-center px-6 py-12 sm:px-14 lg:px-20">
        <div className="w-full max-w-[400px]">

          {/* Tabs login / criar conta */}
          <div
            role="tablist"
            aria-label="Modo de acesso"
            className="mb-8 flex rounded-[12px] border border-borda bg-superficie p-1 gap-1"
          >
            {(["login", "register"] as const).map((m) => (
              <button
                key={m}
                role="tab"
                aria-selected={mode === m}
                type="button"
                onClick={() => switchMode(m)}
                className={`flex-1 min-h-[42px] rounded-[9px] text-[14px] font-medium transition cursor-pointer
                  ${mode === m
                    ? "bg-purple text-paper shadow-sm"
                    : "text-locked hover:text-ink"
                  }`}
              >
                {m === "login" ? "Entrar" : "Criar conta"}
              </button>
            ))}
          </div>

          {/* Subtítulo */}
          <p className="mb-6 text-[15px] text-locked leading-snug">
            {mode === "login"
              ? "Acesse seus projetos e continue de onde parou."
              : "Crie sua conta e comece a orientação socrática hoje."}
          </p>

          <form onSubmit={onSubmit} className="space-y-5">
            {mode === "register" && (
              <label className="block text-[15px] font-medium text-ink">
                Nome{" "}
                <span className="font-normal text-locked">(opcional)</span>
                <input
                  name="name"
                  maxLength={120}
                  autoComplete="name"
                  className={inputClass}
                  placeholder="Como prefere ser chamado"
                />
              </label>
            )}

            <label className="block text-[15px] font-medium text-ink">
              E-mail
              <input
                ref={emailRef}
                name="email"
                type="email"
                required
                autoComplete="email"
                autoFocus
                className={inputClass}
                placeholder="voce@universidade.edu.br"
              />
            </label>

            <label className="block text-[15px] font-medium text-ink">
              Senha{" "}
              {mode === "register" && (
                <span className="font-normal text-locked">(mínimo de 8 caracteres)</span>
              )}
              <input
                name="password"
                type="password"
                required
                minLength={mode === "register" ? 8 : 1}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                className={inputClass}
                placeholder={mode === "login" ? "Sua senha" : "Crie uma senha segura"}
              />
            </label>

            {error && (
              <AlertBanner variant="error">{error}</AlertBanner>
            )}

            <Button
              type="submit"
              variant="primary"
              disabled={busy}
              className="w-full"
            >
              {busy
                ? "Aguarde…"
                : mode === "login"
                  ? "Entrar na conta"
                  : "Criar conta gratuita"}
            </Button>
          </form>

          {/* Link alternativo abaixo do form */}
          <p className="mt-5 text-[14px] text-locked text-center">
            {mode === "login" ? "Não tem conta?" : "Já tem conta?"}{" "}
            <button
              type="button"
              onClick={() => switchMode(mode === "login" ? "register" : "login")}
              className="font-medium text-purple hover:underline cursor-pointer"
            >
              {mode === "login" ? "Criar conta gratuita" : "Entrar"}
            </button>
          </p>
        </div>
      </main>
    </div>
  );
}

"use client";

import { useRouter } from "next/navigation";
import React, { useState } from "react";
import { api, setToken } from "@/lib/api";
import { Logo } from "@/components/logo";
import { AlertBanner, Button } from "@/components/ui";

const inputClass =
  "mt-1.5 w-full h-[48px] rounded-[10px] border border-borda bg-superficie px-4 text-[15px] text-ink placeholder:text-locked/60 focus:border-purple";

export default function EntrarPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const body =
        mode === "login"
          ? { email: f.get("email"), password: f.get("password") }
          : { email: f.get("email"), password: f.get("password"), name: f.get("name") || null };
      const res = await api<{ token: string }>(mode === "login" ? "/auth/login" : "/auth/register", {
        method: "POST",
        body,
      });
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
      {/* Painel esquerdo roxo (480 px em desktop; bloco no topo em telas estreitas) */}
      <aside
        aria-label="Apresentação da marca"
        className="w-full lg:w-[480px] shrink-0 bg-purple text-paper p-8 sm:p-12 flex flex-col justify-between gap-10"
      >
        <div>
          <Logo variant="invertida" withSignature={true} className="w-[260px] sm:w-[300px] h-auto" />

          <h1 className="mt-10 font-display text-3xl sm:text-[34px] leading-tight text-paper">
            Uma pergunta por vez.
          </h1>

          <p className="mt-4 font-serif-academic text-[18px] leading-[1.55] text-paper/90">
            Um orientador de pesquisa que pergunta em vez de escrever por você. Cada afirmação apoiada em um trecho literal verificado.
          </p>
        </div>

        {/* Exemplo ilustrativo do produto */}
        <div
          aria-label="Exemplo de funcionamento"
          className="rounded-[14px] border border-borda bg-paper p-5 text-ink space-y-4"
        >
          <p className="font-serif-academic text-[17px] leading-[1.55] text-ink">
            Toda afirmação do capítulo precisa de{" "}
            <mark className="mark-orange font-medium">um trecho que a sustente</mark>.
          </p>

          <div className="rounded-[12px] bg-purple px-4 py-3 text-[15px] font-medium text-paper">
            Qual trecho sustenta isso?
          </div>

          <div className="flex items-center gap-3 pt-1">
            <span className="inline-block rounded-[6px] border-2 border-brand-red px-2.5 py-0.5 font-display text-[13px] tracking-wider uppercase text-brand-red -rotate-2">
              ATENÇÃO
            </span>
            <span className="text-[14px] text-ink leading-snug">
              Esta afirmação ainda não tem trecho verificado.
            </span>
          </div>
        </div>
      </aside>

      {/* Painel direito crema com o formulário em 400 px */}
      <main className="flex-1 flex items-center justify-center lg:justify-start px-6 py-12 sm:px-16 lg:px-20">
        <div className="w-full max-w-[400px]">
          <h2 className="font-display text-2xl sm:text-[28px] text-ink">
            {mode === "login" ? "Entrar" : "Criar conta"}
          </h2>
          <p className="mt-1.5 text-[15px] text-locked">
            {mode === "login"
              ? "Acesse seus projetos de pesquisa e continue de onde parou."
              : "Crie sua conta acadêmica para iniciar a orientação do seu trabalho."}
          </p>

          <form onSubmit={onSubmit} className="mt-6 space-y-5">
            {mode === "register" && (
              <label className="block text-[15px] font-medium text-ink">
                Nome (opcional)
                <input name="name" maxLength={120} autoComplete="name" className={inputClass} />
              </label>
            )}

            <label className="block text-[15px] font-medium text-ink">
              E-mail
              <input name="email" type="email" required autoComplete="email" className={inputClass} />
            </label>

            <label className="block text-[15px] font-medium text-ink">
              <span>
                Senha{" "}
                {mode === "register" && (
                  <span className="font-normal text-locked">(mínimo de 8 caracteres)</span>
                )}
              </span>
              <input
                name="password"
                type="password"
                required
                minLength={mode === "register" ? 8 : 1}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                className={inputClass}
              />
            </label>

            {error && <AlertBanner variant="error">{error}</AlertBanner>}

            <Button type="submit" variant="primary" disabled={busy} className="w-full">
              {busy ? "Aguarde…" : mode === "login" ? "Entrar" : "Criar conta"}
            </Button>
          </form>

          <div className="mt-5">
            <button
              type="button"
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError(null);
              }}
              className="inline-flex min-h-[44px] items-center text-[15px] font-medium text-purple underline cursor-pointer"
            >
              {mode === "login" ? "Não tenho conta" : "Já tenho conta"}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

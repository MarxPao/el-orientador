"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, setToken } from "@/lib/api";
import { Wordmark } from "@/components/wordmark";

const input = "w-full rounded border border-ink/30 bg-white px-3 py-2 text-sm";

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
    <main className="mx-auto w-full max-w-sm px-6 py-16">
      <h1>
        <Wordmark className="w-64" />
      </h1>
      <p className="mt-4 text-sm text-ink/70">Uma pergunta por vez. Cada afirmação com o trecho que a sustenta.</p>
      <h2 className="mt-8 text-lg font-medium">{mode === "login" ? "Entrar" : "Criar conta"}</h2>
      <form onSubmit={onSubmit} className="mt-4 space-y-4">
        {mode === "register" && (
          <label className="block text-sm">
            Nome (opcional)
            <input name="name" maxLength={120} autoComplete="name" className={input} />
          </label>
        )}
        <label className="block text-sm">
          E-mail
          <input name="email" type="email" required autoComplete="email" className={input} />
        </label>
        <label className="block text-sm">
          Senha {mode === "register" && <span className="text-ink/60">(mínimo de 8 caracteres)</span>}
          <input
            name="password"
            type="password"
            required
            minLength={mode === "register" ? 8 : 1}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            className={input}
          />
        </label>
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <button
          disabled={busy}
          className="w-full rounded bg-available px-3 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {busy ? "Aguarde…" : mode === "login" ? "Entrar" : "Criar conta"}
        </button>
      </form>
      <button
        type="button"
        onClick={() => {
          setMode(mode === "login" ? "register" : "login");
          setError(null);
        }}
        className="mt-4 text-sm text-available underline"
      >
        {mode === "login" ? "Não tenho conta" : "Já tenho conta"}
      </button>
    </main>
  );
}

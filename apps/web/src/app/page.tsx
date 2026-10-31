"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { getToken } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    router.replace(getToken() ? "/projetos" : "/entrar");
  }, [router]);
  return <main className="p-8 text-sm">Carregando…</main>;
}

"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import React, { useCallback } from "react";
import { clearToken } from "@/lib/api";
import { Logo } from "./logo";

export type AppHeaderProps = {
  projectId?: string;
  onLeave?: () => void;
};

export function AppHeader({ projectId, onLeave }: AppHeaderProps) {
  const router = useRouter();
  const pathname = usePathname();

  const handleLeave = useCallback(() => {
    if (onLeave) {
      onLeave();
      return;
    }
    clearToken();
    router.replace("/entrar");
  }, [onLeave, router]);

  const navItems = projectId
    ? [
        { label: "Árvore de progresso", href: `/projetos/${projectId}/arvore` },
        { label: "Mapa de conhecimento", href: `/projetos/${projectId}/mapa` },
        { label: "Editor", href: `/projetos/${projectId}/editor` },
        { label: "Relatório", href: `/projetos/${projectId}/relatorio` },
      ]
    : [];

  return (
    <header className="sticky top-0 z-40 h-[68px] w-full border-b border-borda bg-paper print:hidden">
      <div className="mx-auto flex h-full w-full max-w-[1440px] items-center justify-between gap-4 px-6 sm:px-10">
        <Link
          href="/projetos"
          aria-label="El Orientador — Ir para seus projetos"
          className="flex min-h-[44px] items-center py-2"
        >
          <Logo withSignature={false} className="w-[185px] sm:w-[195px] h-auto" />
        </Link>

        <nav aria-label="Navegação principal" className="flex items-center gap-2 sm:gap-5 text-[15px]">
          {projectId && (
            <>
              <div className="hidden md:flex items-center gap-1">
                {navItems.map((item) => {
                  const active = pathname?.startsWith(item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={`flex min-h-[44px] items-center rounded-[8px] px-3 font-medium transition ${
                        active
                          ? "bg-purple text-paper"
                          : "text-purple hover:bg-purple/10"
                      }`}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </div>
              <Link
                href="/projetos"
                className="flex min-h-[44px] items-center px-2 font-medium text-locked hover:text-ink hover:underline"
              >
                Todos os projetos
              </Link>
              <span aria-hidden className="h-4 w-px bg-borda" />
            </>
          )}

          <button
            type="button"
            onClick={handleLeave}
            className="flex min-h-[44px] items-center px-2 text-[15px] font-medium text-purple hover:underline cursor-pointer"
          >
            Sair
          </button>
        </nav>
      </div>
    </header>
  );
}

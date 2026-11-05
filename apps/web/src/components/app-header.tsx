"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import React, { useCallback, useState } from "react";
import { clearToken } from "@/lib/api";
import { Logo } from "./logo";

export type AppHeaderProps = {
  projectId?: string;
  projectTitle?: string;
  onLeave?: () => void;
};

export function AppHeader({ projectId, projectTitle, onLeave }: AppHeaderProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

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
    <>
      <header className="sticky top-0 z-40 h-[68px] w-full border-b border-borda bg-paper print:hidden">
        <div className="mx-auto flex h-full w-full max-w-[1440px] items-center justify-between gap-4 px-6 sm:px-10">
          {/* Logo + breadcrumb */}
          <div className="flex items-center gap-3 min-w-0">
            <Link
              href="/projetos"
              aria-label="El Orientador — Ir para seus projetos"
              className="flex shrink-0 min-h-[44px] items-center py-2"
            >
              <Logo withSignature={false} className="w-[160px] sm:w-[185px] h-auto" />
            </Link>

            {projectId && projectTitle && (
              <>
                <span aria-hidden className="hidden sm:block h-4 w-px bg-borda shrink-0" />
                <span className="hidden sm:block text-[13px] text-locked truncate max-w-[200px] lg:max-w-xs">
                  {projectTitle}
                </span>
              </>
            )}
          </div>

          {/* Nav desktop */}
          <nav aria-label="Navegação principal" className="flex items-center gap-1 sm:gap-2 text-[15px]">
            {projectId && (
              <div className="hidden md:flex items-center gap-1">
                {navItems.map((item) => {
                  const active = pathname?.startsWith(item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={`flex min-h-[44px] items-center rounded-[8px] px-3 text-[14px] font-medium transition ${
                        active
                          ? "bg-purple text-paper"
                          : "text-purple hover:bg-purple/10"
                      }`}
                    >
                      {item.label}
                    </Link>
                  );
                })}
                <span aria-hidden className="mx-1 h-4 w-px bg-borda" />
                <Link
                  href="/projetos"
                  className="flex min-h-[44px] items-center px-2 text-[14px] font-medium text-locked hover:text-ink"
                >
                  Todos os projetos
                </Link>
                <span aria-hidden className="mx-1 h-4 w-px bg-borda" />
              </div>
            )}

            <button
              type="button"
              onClick={handleLeave}
              className="hidden sm:flex min-h-[44px] items-center px-3 text-[14px] font-medium text-purple rounded-[8px] hover:bg-purple/10 transition cursor-pointer"
            >
              Sair
            </button>

            {/* Hamburger mobile */}
            <button
              type="button"
              aria-label={mobileOpen ? "Fechar menu" : "Abrir menu"}
              aria-expanded={mobileOpen}
              onClick={() => setMobileOpen((v) => !v)}
              className="md:hidden flex min-h-[44px] min-w-[44px] items-center justify-center rounded-[8px] text-ink hover:bg-borda/50 cursor-pointer"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" className="h-5 w-5">
                {mobileOpen ? (
                  <>
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </>
                ) : (
                  <>
                    <line x1="4" y1="8" x2="20" y2="8" />
                    <line x1="4" y1="16" x2="20" y2="16" />
                  </>
                )}
              </svg>
            </button>
          </nav>
        </div>
      </header>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-30 pt-[68px]" onClick={() => setMobileOpen(false)}>
          <nav
            aria-label="Menu mobile"
            className="bg-paper border-b border-borda shadow-lg px-6 py-4 space-y-1"
            onClick={(e) => e.stopPropagation()}
          >
            {projectId && (
              <>
                {navItems.map((item) => {
                  const active = pathname?.startsWith(item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setMobileOpen(false)}
                      aria-current={active ? "page" : undefined}
                      className={`flex min-h-[48px] items-center rounded-[10px] px-4 text-[15px] font-medium transition ${
                        active ? "bg-purple text-paper" : "text-purple hover:bg-purple/10"
                      }`}
                    >
                      {item.label}
                    </Link>
                  );
                })}
                <Link
                  href="/projetos"
                  onClick={() => setMobileOpen(false)}
                  className="flex min-h-[48px] items-center rounded-[10px] px-4 text-[15px] font-medium text-locked hover:text-ink hover:bg-borda/40 transition"
                >
                  Todos os projetos
                </Link>
                <div className="my-1 h-px bg-borda" />
              </>
            )}
            <button
              type="button"
              onClick={() => { setMobileOpen(false); handleLeave(); }}
              className="flex w-full min-h-[48px] items-center rounded-[10px] px-4 text-[15px] font-medium text-purple hover:bg-purple/10 transition cursor-pointer"
            >
              Sair
            </button>
          </nav>
        </div>
      )}
    </>
  );
}
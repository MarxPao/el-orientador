"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

/**
 * Thin purple progress bar that animates on every route change.
 * Wraps the actual bar so it can be used inside a <Suspense> boundary
 * (required for useSearchParams in Next.js App Router).
 */
function ProgressBarInner() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [progress, setProgress] = useState(0);
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const prevRouteRef = useRef(`${pathname}${searchParams}`);

  useEffect(() => {
    const currentRoute = `${pathname}${searchParams}`;
    if (currentRoute === prevRouteRef.current) return;
    prevRouteRef.current = currentRoute;

    // Clear any ongoing animation
    if (timerRef.current) clearTimeout(timerRef.current);
    if (intervalRef.current) clearInterval(intervalRef.current);

    // Start: show bar at 10%
    setProgress(10);
    setVisible(true);

    // Simulate progress toward 85%
    let current = 10;
    intervalRef.current = setInterval(() => {
      current += Math.random() * 12;
      if (current >= 85) {
        current = 85;
        if (intervalRef.current) clearInterval(intervalRef.current);
      }
      setProgress(current);
    }, 200);

    // Complete: jump to 100% then fade out
    timerRef.current = setTimeout(() => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      setProgress(100);
      setTimeout(() => setVisible(false), 300);
    }, 600);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [pathname, searchParams]);

  if (!visible) return null;

  return (
    <div
      role="progressbar"
      aria-label="Carregando página"
      aria-valuenow={Math.round(progress)}
      aria-valuemin={0}
      aria-valuemax={100}
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        zIndex: 9999,
        height: "3px",
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          height: "100%",
          width: `${progress}%`,
          background: "var(--color-purple, #4b2a7b)",
          transition: progress === 100 ? "width 0.15s ease, opacity 0.3s ease" : "width 0.2s ease",
          opacity: progress === 100 ? 0 : 1,
          boxShadow: "0 0 8px var(--color-purple, #4b2a7b)",
        }}
      />
    </div>
  );
}

// Re-export wrapped in Suspense (useSearchParams requires it)
import { Suspense } from "react";

export function RouteProgress() {
  return (
    <Suspense fallback={null}>
      <ProgressBarInner />
    </Suspense>
  );
}

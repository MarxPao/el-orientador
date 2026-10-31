type Props = {
  /** "principal": crema/branco background. "invertida": roxo background. "uma-cor": all purple. */
  variant?: "principal" | "invertida" | "uma-cor";
  /** Below 160 px wide the manual asks for the version without the signature. */
  withSignature?: boolean;
  className?: string;
};

/**
 * Wordmark "EL ORIENTADOR" (manual de marca v2, rascunho). No symbol, no monogram.
 * Orange band is fill only, never text (contrast 2.58:1 on paper).
 */
export function Wordmark({ variant = "principal", withSignature = true, className = "" }: Props) {
  const name =
    variant === "principal" ? "text-brand-red" : variant === "invertida" ? "text-paper" : "text-purple";
  const line = variant === "uma-cor" ? "bg-purple" : "bg-orange";
  const thin = variant === "principal" ? "bg-brand-red" : variant === "invertida" ? "bg-paper" : "bg-purple";
  return (
    <span role="img" aria-label="El Orientador" className={`inline-block leading-none ${className}`}>
      <span className={`font-letreiro block whitespace-nowrap text-2xl uppercase ${name}`}>El Orientador</span>
      <span aria-hidden className={`mt-1 block h-2 w-full ${line}`} />
      <span aria-hidden className={`mt-0.5 block h-px w-full ${thin}`} />
      {withSignature && (
        <span aria-hidden className={`mt-1 block text-[10px] uppercase tracking-[0.3em] ${name}`}>
          Pesquisa · Ciência · Escrita
        </span>
      )}
    </span>
  );
}

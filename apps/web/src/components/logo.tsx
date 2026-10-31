import React from "react";

export type LogoVariant = "padrao" | "invertida" | "uma-cor";

export type LogoProps = {
  /**
   * "padrao": sobre fundo papel crema ou branco (nome, filete e assinatura em vermelho; faixa laranja).
   * "invertida": sobre fundo roxo (nome, filete e assinatura em papel crema; faixa laranja).
   * "uma-cor": carimbo e impressão simples (tudo em roxo).
   */
  variant?: LogoVariant;
  /**
   * Abaixo de 160 px de largura e no cabeçalho de 68 px, usar sem assinatura (viewBox 0 0 886 135).
   */
  withSignature?: boolean;
  className?: string;
  ariaLabel?: string;
};

/**
 * Componente oficial do logotipo EL ORIENTADOR (Manual de Marca v2).
 *
 * Estrutura preparada para substituição direta do grupo <g data-part="wordmark-glyphs">
 * por curvas (<path />) assim que a fonte de letreiro definitiva for licenciada e convertida.
 */
export function Logo({
  variant = "padrao",
  withSignature = true,
  className = "",
  ariaLabel = "El Orientador",
}: LogoProps) {
  const primaryColor =
    variant === "padrao"
      ? "var(--brand-red)"
      : variant === "invertida"
      ? "var(--paper)"
      : "var(--purple)";

  const bandColor = variant === "uma-cor" ? "var(--purple)" : "var(--orange)";

  const viewBox = withSignature ? "0 0 886 190" : "0 0 886 135";

  return (
    <svg
      viewBox={viewBox}
      preserveAspectRatio="xMidYMid meet"
      role="img"
      aria-label={ariaLabel}
      className={`block select-none ${className}`}
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Grupo do letreiro: substituir os elementos <text> abaixo por <path d="..." /> na arte final */}
      <g
        data-part="wordmark-glyphs"
        fill={primaryColor}
        style={{
          fontFamily: "var(--font-display), serif",
          fontWeight: 400,
        }}
      >
        <text
          x={0}
          y={100}
          fontSize={100}
          textLength={130}
          lengthAdjust="spacingAndGlyphs"
        >
          EL
        </text>
        <text
          x={166}
          y={100}
          fontSize={100}
          textLength={720}
          lengthAdjust="spacingAndGlyphs"
        >
          ORIENTADOR
        </text>
      </g>

      {/* Faixa grossa (y=116, altura=6) e filete fino (y=127, altura=2.5) */}
      <g data-part="wordmark-rules">
        <rect x={0} y={116} width={886} height={6} fill={bandColor} />
        <rect x={0} y={127} width={886} height={2.5} fill={primaryColor} />
      </g>

      {/* Assinatura institucional (omitida na versão compacta/cabeçalho) */}
      {withSignature && (
        <text
          data-part="wordmark-signature"
          x={443}
          y={172}
          fill={primaryColor}
          fontSize={24}
          fontWeight={700}
          letterSpacing={9}
          textAnchor="middle"
          style={{
            fontFamily: "var(--font-sans), sans-serif",
          }}
        >
          PESQUISA · CIÊNCIA · ESCRITA
        </text>
      )}
    </svg>
  );
}

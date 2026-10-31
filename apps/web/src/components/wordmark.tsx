import { Logo, LogoVariant } from "./logo";

type Props = {
  variant?: "principal" | "invertida" | "uma-cor";
  withSignature?: boolean;
  className?: string;
};

export function Wordmark({ variant = "principal", withSignature = true, className = "" }: Props) {
  const mappedVariant: LogoVariant = variant === "principal" ? "padrao" : variant;
  return <Logo variant={mappedVariant} withSignature={withSignature} className={className} />;
}

import { Suspense } from "react";
import AdvisorShareView from "./advisor-share-view";

async function AdvisorShareRoute({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <AdvisorShareView token={token} />;
}

export default function AdvisorSharePage({ params }: { params: Promise<{ token: string }> }) {
  return (
    <Suspense fallback={<main className="p-8 text-[15px]">Carregando modo orientador…</main>}>
      <AdvisorShareRoute params={params} />
    </Suspense>
  );
}

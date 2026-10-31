import { Suspense } from "react";
import ReportView from "./report-view";

async function ReportRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ReportView id={id} />;
}

export default function ReportPage({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={<main className="p-8 text-sm">Carregando relatório…</main>}>
      <ReportRoute params={params} />
    </Suspense>
  );
}

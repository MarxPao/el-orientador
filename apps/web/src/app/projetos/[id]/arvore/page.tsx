import { Suspense } from "react";
import TreeView from "./tree-view";

async function TreeRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <TreeView id={id} />;
}

export default function ArvorePage({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={<main className="p-8 text-sm">Carregando árvore de progresso…</main>}>
      <TreeRoute params={params} />
    </Suspense>
  );
}

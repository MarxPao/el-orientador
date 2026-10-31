import { Suspense } from "react";
import EditorView from "./editor-view";

async function EditorRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <EditorView id={id} />;
}

export default function EditorPage({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={<main className="p-8 text-sm">Carregando editor…</main>}>
      <EditorRoute params={params} />
    </Suspense>
  );
}

import { Suspense } from "react";
import MapView from "./map-view";

async function MapRoute({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <MapView id={id} />;
}

export default function MapaPage({ params }: { params: Promise<{ id: string }> }) {
  return (
    <Suspense fallback={<main className="p-8 text-sm">Carregando…</main>}>
      <MapRoute params={params} />
    </Suspense>
  );
}

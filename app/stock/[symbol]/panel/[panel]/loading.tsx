import { Header } from "@/components/Header";

export default function StockPanelLoading() {
  return (
    <main className="shell">
      <Header subtitle="Loading panel" />
      <div className="content">
        <section className="panel">
          <div className="panel-body stack">
            <strong>Loading panel...</strong>
            <p className="muted">Preparing the selected analysis view.</p>
          </div>
        </section>
      </div>
    </main>
  );
}

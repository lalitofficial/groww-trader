import { Header } from "@/components/Header";

export default function StockLoading() {
  return (
    <main className="shell">
      <Header subtitle="Loading stock workstation" />
      <div className="content">
        <section className="panel">
          <div className="panel-body stack">
            <strong>Loading analysis...</strong>
            <p className="muted">Fetching market data, account context, catalysts, and chart overlays.</p>
          </div>
        </section>
      </div>
    </main>
  );
}

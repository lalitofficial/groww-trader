import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Header } from "@/components/Header";
import { StockPanelContent, type StockPanelId } from "@/components/StockPanelContent";
import { getStockAnalysis } from "@/lib/api";

export default async function StockPanelPage({ params }: { params: Promise<{ symbol: string; panel: string }> }) {
  const { symbol, panel } = await params;
  const analysis = await getStockAnalysis(symbol);
  const panelId = normalizePanel(panel);

  return (
    <main className="shell">
      <Header subtitle={`${analysis.symbol} · ${analysis.company}`} />
      <div className="content">
        <div className="page-actions">
          <Link className="btn btn-secondary w-fit" href={`/stock/${analysis.symbol}`}>
            <ArrowLeft size={14} />
            Workstation
          </Link>
        </div>
        <section className="standalone-panel">
          <StockPanelContent panel={panelId} analysis={analysis} />
        </section>
      </div>
    </main>
  );
}

function normalizePanel(value: string): StockPanelId {
  return ["overview", "trade_plan", "metrics", "tradingview", "charts", "quant", "resistances", "diagnostics", "ai", "account", "news"].includes(value) ? (value as StockPanelId) : "tradingview";
}

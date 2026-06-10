import { Header } from "@/components/Header";
import { StockWorkstation } from "@/components/StockWorkstation";
import { WorkstationProvider } from "@/components/WorkstationContext";
import { getStockAnalysis } from "@/lib/api";
import type { Timeframe } from "@/lib/types";

const VALID: Timeframe[] = ["5m", "15m", "30m", "hourly", "daily"];

export default async function StockPage({
  params,
  searchParams,
}: {
  params: Promise<{ symbol: string }>;
  searchParams: Promise<{ timeframe?: string }>;
}) {
  const { symbol } = await params;
  const search = await searchParams;
  const timeframe = (VALID.includes((search.timeframe || "") as Timeframe) ? (search.timeframe as Timeframe) : "daily");
  const analysis = await getStockAnalysis(symbol, { timeframe });

  return (
    <main className="shell">
      <WorkstationProvider symbol={analysis.symbol} timeframe={timeframe}>
        <Header subtitle={`${analysis.symbol} · ${analysis.company} · ${timeframe}`} />
        <div className="content dock-content">
          <StockWorkstation analysis={analysis} timeframe={timeframe} />
        </div>
      </WorkstationProvider>
    </main>
  );
}

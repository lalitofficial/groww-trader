"use client";

import Link from "next/link";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { Header } from "@/components/Header";

export default function StockError({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <main className="shell">
      <Header subtitle="Stock analysis unavailable" />
      <div className="content">
        <div className="page-actions">
          <Link className="btn btn-secondary w-fit" href="/">
            <ArrowLeft size={14} />
            Search
          </Link>
          <button type="button" className="btn btn-primary w-fit" onClick={reset}>
            <RefreshCw size={14} />
            Retry
          </button>
        </div>
        <section className="panel">
          <div className="panel-body stack">
            <strong>Stock analysis unavailable</strong>
            <p className="muted">Start the backend with `groww-trader dashboard --api-only` or `uvicorn groww_trader.api.app:app --reload`.</p>
            <p>{error.message}</p>
          </div>
        </section>
      </div>
    </main>
  );
}

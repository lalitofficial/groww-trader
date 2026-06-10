"use client";

import Link from "next/link";
import { ArrowLeft, RefreshCw } from "lucide-react";
import { Header } from "@/components/Header";

export default function StockPanelError({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <main className="shell">
      <Header subtitle="Panel unavailable" />
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
            <strong>Panel unavailable</strong>
            <p className="muted">The backend did not return the analysis needed for this view.</p>
            <p>{error.message}</p>
          </div>
        </section>
      </div>
    </main>
  );
}

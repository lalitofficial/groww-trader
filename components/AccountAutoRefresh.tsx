"use client";

import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

export function AccountAutoRefresh() {
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    if (!enabled) return;
    const id = window.setInterval(() => window.location.reload(), 60_000);
    return () => window.clearInterval(id);
  }, [enabled]);

  return (
    <button type="button" className="btn btn-secondary" onClick={() => setEnabled((value) => !value)}>
      <RefreshCw size={14} />
      {enabled ? "Polling on" : "Polling off"}
    </button>
  );
}

"use client";

import { Bot, Pause, Play, Settings } from "lucide-react";
import { useState } from "react";
import { useAiHeartbeat } from "@/hooks/useAiHeartbeat";
import { disableAi, enableAi } from "@/lib/api";
import { AiSettingsDrawer } from "@/components/AiSettingsDrawer";

const REASON_LABEL: Record<string, string> = {
  ok: "Live",
  disabled_by_user: "Off (paused)",
  no_heartbeat: "Idle",
  circuit_open: "Cooling",
};

export function AiStatusPill() {
  const { status, refresh } = useAiHeartbeat(true);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);

  const reason = status?.reason || "no_heartbeat";
  const tone =
    !status?.allowed && reason === "disabled_by_user"
      ? "off"
      : !status?.allowed
        ? "idle"
        : "live";

  async function toggle(event: React.MouseEvent) {
    event.preventDefault();
    if (!status) return;
    setBusy(true);
    try {
      if (status.ai_enabled) await disableAi();
      else await enableAi();
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className={`ai-status-pill ai-status-${tone}`} title={`AI: ${REASON_LABEL[reason]}`}>
        <Bot size={13} />
        <span>AI</span>
        <strong>{REASON_LABEL[reason]}</strong>
        <button type="button" className="ai-status-toggle" onClick={toggle} disabled={busy}>
          {status?.ai_enabled ? <Pause size={11} /> : <Play size={11} />}
        </button>
        <button type="button" className="ai-status-toggle" onClick={() => setOpen(true)} aria-label="AI settings">
          <Settings size={11} />
        </button>
      </div>
      {open ? <AiSettingsDrawer onClose={() => setOpen(false)} onSaved={refresh} /> : null}
    </>
  );
}

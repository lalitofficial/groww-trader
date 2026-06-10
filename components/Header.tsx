"use client";

import Link from "next/link";
import { useState } from "react";
import { CopyPlus, Layers, RefreshCw, RotateCcw, Save, Trash2 } from "lucide-react";
import { AiStatusPill } from "@/components/AiStatusPill";
import { ModePills } from "@/components/ModePills";
import { RequestBudgetTile } from "@/components/RequestBudgetTile";
import { RiskMeterPill } from "@/components/RiskMeterPill";
import { SessionDrawer } from "@/components/SessionDrawer";
import { TIMEFRAME_OPTIONS, useWorkstation } from "@/components/WorkstationContext";

export function Header({ subtitle }: { subtitle?: string }) {
  const workstation = useWorkstation();
  const [sessionOpen, setSessionOpen] = useState(false);

  return (
    <header className="sticky top-0 z-10 flex min-h-12 items-center justify-between gap-3 px-3 py-2">
      <Link href="/" className="min-w-0">
        <div className="truncate text-sm font-bold leading-tight text-slate-100">Groww AI Swing Dashboard</div>
        {subtitle ? <div className="truncate text-[11px] text-slate-500">{subtitle}</div> : null}
      </Link>
      <ModePills />
      <div className="header-actions">
        {workstation ? (
          <div className="header-workstation-tools">
            <div className="header-timeframes">
              {TIMEFRAME_OPTIONS.map((timeframe) => (
                <button
                  key={timeframe}
                  type="button"
                  className={timeframe === workstation.timeframe ? "tf-pill active" : "tf-pill"}
                  onClick={() => workstation.setTimeframe(timeframe)}
                >
                  {timeframe}
                </button>
              ))}
            </div>
            <div className="header-workspace-controls">
              <select value={workstation.activeWorkspaceId} onChange={(event) => workstation.switchWorkspace(event.target.value)} title="Workspace">
                {workstation.workspaces.map((workspace) => (
                  <option key={workspace.id} value={workspace.id}>
                    {workspace.name}
                  </option>
                ))}
              </select>
              <input
                value={workstation.workspaceDraftName}
                onChange={(event) => workstation.setWorkspaceDraftName(event.target.value)}
                aria-label="Workspace name"
              />
              <button type="button" onClick={workstation.saveActive} title="Save workspace">
                <Save size={13} />
              </button>
              <button type="button" onClick={workstation.createNew} title="Save as new workspace">
                <CopyPlus size={13} />
              </button>
              <button type="button" onClick={workstation.resetActive} title="Reset active workspace">
                <RotateCcw size={13} />
              </button>
              <button type="button" onClick={workstation.deleteActive} title="Delete custom workspace">
                <Trash2 size={13} />
              </button>
              {workstation.status ? <span>{workstation.status}</span> : null}
            </div>
          </div>
        ) : null}
        <RiskMeterPill />
        <AiStatusPill />
        <RequestBudgetTile />
        <button type="button" className="btn-icon" onClick={() => setSessionOpen(true)} title="Session">
          <Layers size={14} />
        </button>
        <Link className="btn btn-secondary" href="/account">
          Account
        </Link>
        <button type="button" className="btn-icon" onClick={() => window.location.reload()} title="Refresh">
          <RefreshCw size={14} />
        </button>
      </div>
      {sessionOpen ? <SessionDrawer onClose={() => setSessionOpen(false)} /> : null}
    </header>
  );
}

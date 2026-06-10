"use client";

import { X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { getAiSettings, updateAiSettings } from "@/lib/api";
import type { AiSettings } from "@/lib/types";

const TRIGGER_LABELS: Array<{ key: string; label: string; description: string }> = [
  { key: "near_stop", label: "Near stop", description: "Price within 0.4% of paper-trade stop" },
  { key: "near_target", label: "Near target", description: "Price within 0.4% of T1/T2 target" },
  { key: "level_break_up", label: "Level break up", description: "Close crosses a major resistance" },
  { key: "level_break_down", label: "Level break down", description: "Close breaks a major support" },
  { key: "vol_spike", label: "Volume spike", description: "1-min volume ≥ 1.8x avg" },
  { key: "supertrend_flip", label: "Supertrend flip", description: "On the active intraday TF" },
  { key: "vwap_cross_up", label: "VWAP reclaim", description: "Close crosses VWAP from below" },
  { key: "vwap_cross_down", label: "VWAP rejection", description: "Close crosses VWAP from above" },
  { key: "orb_break_up", label: "ORB break up", description: "Opening range high broken (first time)" },
  { key: "orb_break_down", label: "ORB break down", description: "Opening range low broken (first time)" },
  { key: "rsi_extreme", label: "RSI extreme", description: "RSI > 75 or < 25 on intraday TF" },
  { key: "pnl_milestone", label: "P&L milestone", description: "Unrealized hits ±1R / ±2R / -0.5R" },
  { key: "daily_loss_threshold", label: "Daily loss threshold", description: "Realized loss crosses 50% / 70% cap" },
];

export function AiSettingsDrawer({ onClose, onSaved }: { onClose: () => void; onSaved?: () => void }) {
  const [settings, setSettings] = useState<AiSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setSettings(await getAiSettings());
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not load AI settings");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function set<K extends keyof AiSettings>(key: K, value: AiSettings[K]) {
    setSettings((current) => (current ? { ...current, [key]: value } : current));
  }

  function setTrigger(key: string, value: boolean) {
    setSettings((current) =>
      current ? { ...current, event_triggers: { ...current.event_triggers, [key]: value } } : current,
    );
  }

  async function save() {
    if (!settings) return;
    setSaving(true);
    setError("");
    try {
      await updateAiSettings({
        ai_enabled: settings.ai_enabled,
        commentary_enabled: settings.commentary_enabled,
        commentary_cadence_seconds: settings.commentary_cadence_seconds,
        require_heartbeat: settings.require_heartbeat,
        heartbeat_grace_seconds: settings.heartbeat_grace_seconds,
        event_triggers: settings.event_triggers,
      });
      onSaved?.();
      onClose();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" onClick={(event) => event.stopPropagation()}>
        <header className="drawer-header">
          <div>
            <strong>AI Settings</strong>
            <div className="muted">Governs every Azure OpenAI call. Pauses automatically if the tab goes idle.</div>
          </div>
          <button type="button" className="btn-icon" onClick={onClose}>
            <X size={14} />
          </button>
        </header>
        {error ? <div className="context-badge warning">{error}</div> : null}
        {settings ? (
          <div className="drawer-body stack">
            <Section title="Master switch">
              <Toggle
                label="AI services enabled"
                description="Off = no Azure calls anywhere. Deterministic fallbacks still run."
                checked={settings.ai_enabled}
                onChange={(v) => set("ai_enabled", v)}
              />
              <Toggle
                label="Position commentary"
                description="AI comments on open paper trades on a cadence + key events."
                checked={settings.commentary_enabled}
                onChange={(v) => set("commentary_enabled", v)}
              />
              <Field label="Commentary cadence" hint="During open paper trades. Default 5 min.">
                <select
                  className="input"
                  value={settings.commentary_cadence_seconds}
                  onChange={(event) => set("commentary_cadence_seconds", Number(event.target.value))}
                >
                  <option value={60}>Every 1 min</option>
                  <option value={180}>Every 3 min</option>
                  <option value={300}>Every 5 min</option>
                  <option value={600}>Every 10 min</option>
                  <option value={900}>Every 15 min</option>
                </select>
              </Field>
            </Section>
            <Section title="Safety">
              <Toggle
                label="Require heartbeat from browser"
                description="Auto-mutes AI when no tab is active. Recommended."
                checked={settings.require_heartbeat}
                onChange={(v) => set("require_heartbeat", v)}
              />
              <Field label="Heartbeat grace" hint="Mute after this many minutes of tab inactivity.">
                <select
                  className="input"
                  value={settings.heartbeat_grace_seconds}
                  onChange={(event) => set("heartbeat_grace_seconds", Number(event.target.value))}
                >
                  <option value={300}>5 minutes</option>
                  <option value={600}>10 minutes</option>
                  <option value={1800}>30 minutes</option>
                  <option value={3600}>60 minutes</option>
                </select>
              </Field>
            </Section>
            <Section title="Auto-comment triggers">
              <p className="muted">Pick which chart events should auto-trigger AI commentary on your picks.</p>
              <div className="trigger-grid">
                {TRIGGER_LABELS.map((trigger) => (
                  <label key={trigger.key} className="trigger-row">
                    <input
                      type="checkbox"
                      checked={Boolean(settings.event_triggers[trigger.key])}
                      onChange={(event) => setTrigger(trigger.key, event.target.checked)}
                    />
                    <div>
                      <strong>{trigger.label}</strong>
                      <span className="muted">{trigger.description}</span>
                    </div>
                  </label>
                ))}
              </div>
            </Section>
          </div>
        ) : (
          <div className="drawer-body muted">Loading…</div>
        )}
        <footer className="drawer-footer">
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <button type="button" className="btn btn-primary" onClick={save} disabled={saving || !settings}>
            {saving ? "Saving…" : "Save"}
          </button>
        </footer>
      </aside>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="drawer-section">
      <strong>{title}</strong>
      <div className="stack">{children}</div>
    </section>
  );
}

function Toggle({ label, description, checked, onChange }: { label: string; description: string; checked: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="toggle-row">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <div>
        <strong>{label}</strong>
        <span className="muted">{description}</span>
      </div>
    </label>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="field">
      <label>{label}</label>
      {children}
      {hint ? <p className="muted" style={{ fontSize: 11 }}>{hint}</p> : null}
    </div>
  );
}

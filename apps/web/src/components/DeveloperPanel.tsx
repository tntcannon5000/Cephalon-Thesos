import { Pause, Play, TerminalWindow, Trash, X } from "@phosphor-icons/react";
import { motion } from "motion/react";
import { memo, useEffect, useMemo, useRef, useState } from "react";

import { useDeveloperLogs } from "../features/developer/useDeveloperLogs";
import type { DeveloperLayer, DeveloperLogEntry } from "../features/developer/types";
import "../styles/developer.css";

type LayerFilter = "all" | DeveloperLayer;

interface DeveloperPanelProps {
  onClose: () => void;
}

const FILTERS: Array<{ label: string; value: LayerFilter }> = [
  { label: "All", value: "all" },
  { label: "FE", value: "frontend" },
  { label: "BE", value: "backend" },
  { label: "AI", value: "ai" },
];
const TIME_FORMATTER = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  hour12: false,
  minute: "2-digit",
  second: "2-digit",
  fractionalSecondDigits: 3,
});

function formatTime(timestamp: string): string {
  return TIME_FORMATTER.format(new Date(timestamp));
}

function layerLabel(layer: DeveloperLayer): string {
  if (layer === "frontend") return "FE";
  if (layer === "backend") return "BE";
  return "AI";
}

const LogLine = memo(function LogLine({ entry }: { entry: DeveloperLogEntry }) {
  return (
    <article className="developer-log-line" data-layer={entry.layer} data-level={entry.level}>
      <header>
        <time dateTime={entry.timestamp}>{formatTime(entry.timestamp)}</time>
        <span>{layerLabel(entry.layer)}</span>
        <strong>{entry.level}</strong>
        <small>{entry.logger}</small>
      </header>
      <pre>{entry.message}</pre>
    </article>
  );
});

export function DeveloperPanel({ onClose }: DeveloperPanelProps) {
  const { clear, connection, logs } = useDeveloperLogs(true);
  const [filter, setFilter] = useState<LayerFilter>("all");
  const [paused, setPaused] = useState(false);
  const [frozenLogs, setFrozenLogs] = useState<DeveloperLogEntry[] | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const displayedLogs = paused ? (frozenLogs ?? logs) : logs;
  const filteredLogs = useMemo(
    () =>
      filter === "all"
        ? displayedLogs
        : displayedLogs.filter((entry) => entry.layer === filter),
    [displayedLogs, filter],
  );

  useEffect(() => {
    if (paused || !listRef.current) return;
    listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [filteredLogs, paused]);

  const togglePaused = () => {
    if (paused) {
      setFrozenLogs(null);
      setPaused(false);
      return;
    }
    setFrozenLogs(logs);
    setPaused(true);
  };

  const clearLogs = () => {
    clear();
    setFrozenLogs(null);
  };

  return (
    <motion.aside
      className="developer-panel"
      initial={{ x: "100%" }}
      animate={{ x: 0 }}
      exit={{ x: "100%" }}
      transition={{ duration: 0.34, ease: [0.22, 1, 0.36, 1] }}
      aria-label="Developer console"
    >
      <header className="developer-panel-header">
        <div>
          <TerminalWindow size={18} weight="thin" aria-hidden="true" />
          <span>Developer Console</span>
          <i className={`developer-connection is-${connection}`} />
        </div>
        <button type="button" onClick={onClose} aria-label="Close developer console" title="Close">
          <X size={17} weight="thin" />
        </button>
      </header>

      <div className="developer-toolbar">
        <div className="developer-filters" role="group" aria-label="Log source">
          {FILTERS.map((item) => (
            <button
              key={item.value}
              type="button"
              className={filter === item.value ? "is-active" : ""}
              onClick={() => setFilter(item.value)}
              aria-pressed={filter === item.value}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="developer-actions">
          <button
            type="button"
            onClick={togglePaused}
            aria-label={paused ? "Resume developer console" : "Pause developer console"}
            title={paused ? "Resume" : "Pause"}
          >
            {paused ? <Play size={16} weight="thin" /> : <Pause size={16} weight="thin" />}
          </button>
          <button type="button" onClick={clearLogs} aria-label="Clear developer console" title="Clear">
            <Trash size={16} weight="thin" />
          </button>
        </div>
      </div>

      <div className="developer-log-list" ref={listRef} role="log" aria-label="Application logs">
        {filteredLogs.length > 0 ? (
          filteredLogs.map((entry) => <LogLine key={entry.id} entry={entry} />)
        ) : (
          <p className="developer-empty">No output for this source yet.</p>
        )}
      </div>

      <footer className="developer-panel-footer">
        <span>{paused ? "Paused" : connection}</span>
        <span>{filteredLogs.length} lines</span>
      </footer>
    </motion.aside>
  );
}

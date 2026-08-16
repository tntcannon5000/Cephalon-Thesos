import { List, TerminalWindow } from "@phosphor-icons/react";
import { AnimatePresence, motion } from "motion/react";

import type { Conversation } from "../features/chat/types";

interface HeaderProps {
  developerMode: boolean;
  onDeveloperModeChange: (enabled: boolean) => void;
  onOpenMenu: () => void;
  conversation: Conversation | null;
}

export function Header({
  developerMode,
  onDeveloperModeChange,
  onOpenMenu,
  conversation,
}: HeaderProps) {
  return (
    <header className={`app-header ${conversation ? "has-conversation-title" : ""}`}>
      <AnimatePresence initial={false}>
        {conversation ? (
          <motion.div
            className="header-conversation-title"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
          >
            <i aria-hidden="true" />
            <AnimatePresence mode="wait" initial={false}>
              <motion.h1
                key={`${conversation.titleState}-${conversation.title}`}
                className={conversation.titleState === "pending" ? "is-pending" : undefined}
                initial={{ opacity: 0, y: 3 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -3 }}
                transition={{ duration: 0.24 }}
              >
                {conversation.title}
              </motion.h1>
            </AnimatePresence>
          </motion.div>
        ) : null}
      </AnimatePresence>
      <div className="header-controls">
        {import.meta.env.DEV ? (
          <label className="header-toggle developer-toggle">
            <TerminalWindow size={16} weight="thin" aria-hidden="true" />
            <span>Developer</span>
            <input
              type="checkbox"
              aria-label="Developer mode"
              checked={developerMode}
              onChange={(event) => onDeveloperModeChange(event.target.checked)}
            />
            <motion.span
              className="toggle-track"
              animate={{ backgroundColor: developerMode ? "var(--accent-dim)" : "var(--surface-raised)" }}
            >
              <motion.i animate={{ x: developerMode ? 15 : 0 }} />
            </motion.span>
          </label>
        ) : null}
        <button className="header-action" type="button">Log in</button>
        <button className="header-action is-primary" type="button">Sign up</button>
        <button className="mobile-menu-button" type="button" onClick={onOpenMenu} aria-label="Open menu">
          <List size={24} weight="thin" />
        </button>
      </div>
    </header>
  );
}

import {
  ChatCircle,
  ClockCounterClockwise,
  GearSix,
  Info,
  LockSimple,
  Palette,
  Plus,
  PushPin,
  X,
} from "@phosphor-icons/react";
import { AnimatePresence, motion } from "motion/react";
import { useMemo, useState } from "react";

import type { Conversation } from "../features/chat/types";
import { TransmissionContextMenu } from "./TransmissionContextMenu";
import { SidebarResizeHandle } from "./SidebarResizeHandle";

interface SidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  open: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onTogglePinned: (id: string) => void;
  onOpenThemes: () => void;
  width: number;
  onWidthChange: (width: number) => void;
  onWidthReset: () => void;
}

function relativeDate(timestamp: string): string {
  const elapsedMinutes = Math.max(0, Math.floor((Date.now() - Date.parse(timestamp)) / 60_000));
  if (elapsedMinutes < 1) return "now";
  if (elapsedMinutes < 60) return `${elapsedMinutes}m`;
  const hours = Math.floor(elapsedMinutes / 60);
  return hours < 24 ? `${hours}h` : `${Math.floor(hours / 24)}d`;
}

export function Sidebar({
  conversations,
  activeId,
  open,
  onClose,
  onNewChat,
  onSelect,
  onDelete,
  onTogglePinned,
  onOpenThemes,
  width,
  onWidthChange,
  onWidthReset,
}: SidebarProps) {
  const [contextMenu, setContextMenu] = useState<{ id: string; x: number; y: number } | null>(
    null,
  );
  const pinned = useMemo(() => conversations.filter((conversation) => conversation.pinned), [conversations]);
  const recent = useMemo(() => conversations.filter((conversation) => !conversation.pinned), [conversations]);
  const selectedForMenu = contextMenu
    ? conversations.find((conversation) => conversation.id === contextMenu.id) ?? null
    : null;

  const transmissionEntry = (conversation: Conversation) => (
    <motion.button
      layout
      key={conversation.id}
      type="button"
      className={`history-entry ${conversation.id === activeId ? "is-active" : ""}`}
      onClick={() => onSelect(conversation.id)}
      onContextMenu={(event) => {
        event.preventDefault();
        setContextMenu({ id: conversation.id, x: event.clientX, y: event.clientY });
      }}
      onKeyDown={(event) => {
        if (event.key === "ContextMenu" || (event.shiftKey && event.key === "F10")) {
          event.preventDefault();
          const bounds = event.currentTarget.getBoundingClientRect();
          setContextMenu({ id: conversation.id, x: bounds.right - 8, y: bounds.top + 8 });
        }
      }}
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -8 }}
    >
      <ChatCircle size={15} weight="thin" />
      <AnimatePresence mode="wait" initial={false}>
        <motion.span
          key={`${conversation.titleState}-${conversation.title}`}
          className={conversation.titleState === "pending" ? "is-title-pending" : undefined}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
        >
          {conversation.title}
        </motion.span>
      </AnimatePresence>
      <time>{relativeDate(conversation.updatedAt)}</time>
    </motion.button>
  );

  return (
    <>
      <AnimatePresence>
        {open ? (
          <motion.button
            className="sidebar-scrim"
            type="button"
            aria-label="Close menu"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
        ) : null}
      </AnimatePresence>
      <motion.aside
        className={`sidebar ${open ? "is-open" : ""}`}
        initial={false}
        aria-label="Conversation navigation"
      >
        <div className="sidebar-rail" aria-hidden="true"><i /><i /><i /></div>
        <SidebarResizeHandle
          width={width}
          onChange={onWidthChange}
          onReset={onWidthReset}
        />
        <button className="sidebar-close" type="button" onClick={onClose} aria-label="Close menu">
          <X size={22} weight="thin" />
        </button>
        <button className="new-chat-button" type="button" onClick={onNewChat}>
          <Plus size={17} weight="thin" />
          <span>New chat</span>
        </button>

        <div className="transmission-groups">
          <div className="history-heading is-pinned">
            <PushPin size={15} weight="thin" />
            <span>Pinned transmissions</span>
          </div>
          <div className="history-list pinned-list">
            <AnimatePresence mode="popLayout" initial={false}>
              {pinned.length > 0 ? (
                pinned.map(transmissionEntry)
              ) : (
                <motion.p
                  className="pinned-empty"
                  key="pinned-empty"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                >
                  Right click a transmission and pin it to keep it here for your convenience.
                </motion.p>
              )}
            </AnimatePresence>
          </div>

          <div className="history-heading is-recent">
            <ClockCounterClockwise size={15} weight="thin" />
            <span>Recent transmissions</span>
          </div>
          <div className="history-list">
            <AnimatePresence mode="popLayout" initial={false}>
              {recent.length > 0 ? (
                recent.map(transmissionEntry)
              ) : conversations.length === 0 ? (
                <motion.div
                  className="history-empty"
                  key="empty"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                >
                  <span className="speaker-mark">THESOS</span>
                  <p>I will save our chats here, ready for your return.</p>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </div>
        </div>

        <nav className="secondary-nav" aria-label="Project information">
          <a href="/about"><Info size={17} weight="thin" /> About</a>
          <a href="/privacy"><LockSimple size={17} weight="thin" /> Privacy</a>
          <button type="button" onClick={onOpenThemes}><Palette size={17} weight="thin" /> Theme</button>
          <button type="button"><GearSix size={17} weight="thin" /> Settings</button>
        </nav>
      </motion.aside>
      <AnimatePresence>
        {contextMenu && selectedForMenu ? (
          <TransmissionContextMenu
            conversation={selectedForMenu}
            position={contextMenu}
            onClose={() => setContextMenu(null)}
            onTogglePinned={() => {
              onTogglePinned(selectedForMenu.id);
              setContextMenu(null);
            }}
            onDelete={() => {
              onDelete(selectedForMenu.id);
              setContextMenu(null);
            }}
          />
        ) : null}
      </AnimatePresence>
    </>
  );
}

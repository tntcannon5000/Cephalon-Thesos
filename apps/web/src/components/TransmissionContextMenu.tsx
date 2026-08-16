import { PushPin, ShareNetwork, Trash } from "@phosphor-icons/react";
import { motion } from "motion/react";
import { useEffect, useRef } from "react";

import type { Conversation } from "../features/chat/types";

interface TransmissionContextMenuProps {
  conversation: Conversation;
  position: { x: number; y: number };
  onClose: () => void;
  onDelete: () => void;
  onTogglePinned: () => void;
}

export function TransmissionContextMenu({
  conversation,
  position,
  onClose,
  onDelete,
  onTogglePinned,
}: TransmissionContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);
  const left = Math.min(position.x, window.innerWidth - 202);
  const top = Math.min(position.y, window.innerHeight - 150);

  useEffect(() => {
    const closeFromPointer = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) onClose();
    };
    const closeFromKeyboard = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("pointerdown", closeFromPointer);
    window.addEventListener("keydown", closeFromKeyboard);
    window.addEventListener("resize", onClose);
    return () => {
      window.removeEventListener("pointerdown", closeFromPointer);
      window.removeEventListener("keydown", closeFromKeyboard);
      window.removeEventListener("resize", onClose);
    };
  }, [onClose]);

  return (
    <motion.div
      ref={menuRef}
      className="transmission-context-menu"
      role="menu"
      aria-label={`Actions for ${conversation.title}`}
      style={{ left, top }}
      onContextMenu={(event) => event.preventDefault()}
      initial={{ opacity: 0, scale: 0.96, y: -4 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.97, y: -3 }}
      transition={{ duration: 0.14 }}
    >
      <button type="button" role="menuitem" onClick={onTogglePinned}>
        <PushPin size={15} weight={conversation.pinned ? "fill" : "thin"} />
        {conversation.pinned ? "Unpin" : "Pin"}
      </button>
      <button type="button" role="menuitem" disabled title="Sharing is not available yet">
        <ShareNetwork size={15} weight="thin" />
        Share
      </button>
      <button className="is-destructive" type="button" role="menuitem" onClick={onDelete}>
        <Trash size={15} weight="thin" />
        Delete
      </button>
    </motion.div>
  );
}

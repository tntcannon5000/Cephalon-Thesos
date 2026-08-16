import { ArrowUp, Paperclip, PencilSimple, Square, X } from "@phosphor-icons/react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef } from "react";

interface ComposerProps {
  draft: string;
  editing: boolean;
  landing: boolean;
  running: boolean;
  terminated: boolean;
  onDraftChange: (value: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  onCancelEdit: () => void;
  onNewChat: () => void;
}

export function Composer({
  draft,
  editing,
  landing,
  running,
  terminated,
  onDraftChange,
  onSubmit,
  onStop,
  onCancelEdit,
  onNewChat,
}: ComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "0px";
    const nextHeight = Math.min(textarea.scrollHeight, 132);
    textarea.style.height = `${nextHeight}px`;
    textarea.style.overflowY = textarea.scrollHeight > 132 ? "auto" : "hidden";
  }, [draft]);

  return (
    <motion.div
      layout
      className={`composer-wrap ${landing ? "is-landing" : "is-docked"}`}
      transition={{ layout: { duration: 0.58, ease: [0.22, 1, 0.36, 1] } }}
    >
      {terminated ? (
        <motion.div
          className="termination-banner composer-shell"
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          role="status"
        >
          <div>
            <span className="speaker-mark">ARCHIVE LINK CLOSED</span>
            <p>This conversation has been terminated.</p>
          </div>
          <button type="button" onClick={onNewChat}>New chat</button>
        </motion.div>
      ) : (
        <>
          <AnimatePresence initial={false}>
            {editing ? (
              <motion.div
                className="editing-strip"
                initial={{ opacity: 0, y: 8, height: 0 }}
                animate={{ opacity: 1, y: 0, height: 30 }}
                exit={{ opacity: 0, y: 8, height: 0 }}
              >
                <PencilSimple size={14} weight="thin" />
                <span>Editing this turn will remove everything after it</span>
                <button type="button" onClick={onCancelEdit} aria-label="Cancel edit" title="Cancel edit">
                  <X size={15} weight="thin" />
                </button>
              </motion.div>
            ) : null}
          </AnimatePresence>
          <form
            className="composer-shell"
            aria-label="Message composer"
            onPointerDownCapture={(event) => {
              const target = event.target as HTMLElement;
              if (!target.closest(".submit-button")) textareaRef.current?.focus();
            }}
            onSubmit={(event) => {
              event.preventDefault();
              onSubmit();
            }}
          >
            <button
              className="composer-icon"
              type="button"
              disabled
              aria-label="Attach a file"
              title="Attachments are not enabled in this alpha"
            >
              <Paperclip size={23} weight="thin" />
            </button>
            <div className="composer-input">
              <textarea
                ref={textareaRef}
                value={draft}
                onChange={(event) => onDraftChange(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    onSubmit();
                  }
                }}
                rows={1}
                aria-label="Message Thesos"
              />
              {!draft ? <span className="composer-placeholder" aria-hidden="true">Ask Thesos...</span> : null}
            </div>
            <div className="composer-divider" />
            {running ? (
              <motion.button
                className="submit-button is-stop"
                type="button"
                onClick={onStop}
                aria-label="Stop response"
                title="Stop response"
                initial={{ scale: 0.8, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
              >
                <Square size={15} weight="fill" />
              </motion.button>
            ) : (
              <motion.button
                className="submit-button"
                type="submit"
                disabled={!draft.trim()}
                aria-label="Send message"
                title="Send message"
                whileHover={draft.trim() ? { scale: 1.05 } : undefined}
                whileTap={draft.trim() ? { scale: 0.94 } : undefined}
              >
                <ArrowUp size={22} weight="thin" />
              </motion.button>
            )}
          </form>
        </>
      )}
    </motion.div>
  );
}

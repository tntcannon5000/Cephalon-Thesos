import {
  ArrowsClockwise,
  BracketsAngle,
  Check,
  CircleNotch,
  CirclesThree,
  Copy,
  PencilSimple,
  Snowflake,
  Sparkle,
  SpinnerGap,
  TreeStructure,
  WarningCircle,
  Waveform,
  Wrench,
} from "@phosphor-icons/react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import type { AgentActivity, ChatMessage, Conversation } from "../features/chat/types";
import { useTheme } from "../features/theme/ThemeContext";

interface ConversationViewProps {
  conversation: Conversation;
  onEdit: (message: ChatMessage) => void;
  onRevealComplete: (messageId: string) => void;
}

function AssistantResponse({
  message,
  onRevealComplete,
}: {
  message: ChatMessage;
  onRevealComplete: (messageId: string) => void;
}) {
  const reducedMotion = useReducedMotion();
  const words = useMemo(() => message.content.match(/\S+\s*/g) ?? [], [message.content]);
  const [progressive] = useState(message.reveal === true);
  const [visibleWordCount, setVisibleWordCount] = useState(() =>
    message.reveal === true ? 0 : words.length,
  );
  const completionReported = useRef(false);

  useEffect(() => {
    if (!progressive || visibleWordCount >= words.length) return;
    const timer = window.setTimeout(
      () => setVisibleWordCount((current) => Math.min(current + 1, words.length)),
      reducedMotion ? 0 : 34,
    );
    return () => window.clearTimeout(timer);
  }, [progressive, reducedMotion, visibleWordCount, words.length]);

  useEffect(() => {
    if (
      !progressive ||
      completionReported.current ||
      words.length === 0 ||
      visibleWordCount < words.length
    ) {
      return;
    }
    completionReported.current = true;
    onRevealComplete(message.id);
  }, [message.id, onRevealComplete, progressive, visibleWordCount, words.length]);

  return (
    <>
      <p className="streaming-response" aria-label={message.content}>
        {words.slice(0, visibleWordCount).map((word, index) => (
          <motion.span
            className="streamed-word"
            aria-hidden="true"
            key={`${message.id}-word-${index}`}
            initial={progressive && !reducedMotion ? { opacity: 0, y: 3 } : false}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: reducedMotion ? 0 : 0.22,
            }}
          >
            {word}
          </motion.span>
        ))}
      </p>
      {message.state === "streaming" || visibleWordCount < words.length ? (
        <i className="response-caret" aria-hidden="true" />
      ) : null}
    </>
  );
}

function ActivityIndicator({ activity }: { activity: AgentActivity }) {
  const reducedMotion = useReducedMotion();
  const { theme } = useTheme();
  const themedIcon = {
    sigil: SpinnerGap,
    orbit: CircleNotch,
    signal: Waveform,
    fracture: BracketsAngle,
    gust: Snowflake,
    breathe: CirclesThree,
    articulate: TreeStructure,
  }[theme.motion.activity];
  const themedAnimation = {
    sigil: { rotate: [0, 90, 180, 270, 360], scale: [0.86, 1, 0.86] },
    orbit: { rotate: 360 },
    signal: { scaleX: [0.72, 1.12, 0.72], opacity: [0.55, 1, 0.55] },
    fracture: { x: [-1.5, 1.5, 0], opacity: [0.55, 1, 0.55] },
    gust: { x: [-2, 2, -2], rotate: [-4, 4, -4], opacity: [0.5, 1, 0.5] },
    breathe: { scale: [0.78, 1.12, 0.78], opacity: [0.48, 1, 0.48] },
    articulate: { rotate: [0, -14, 9, 0], x: [0, 1, -1, 0] },
  }[theme.motion.activity];
  const Icon =
    activity.kind === "tool"
      ? Wrench
      : activity.kind === "composing"
        ? Sparkle
        : activity.kind === "connecting"
          ? ArrowsClockwise
          : themedIcon;
  const animation =
    activity.kind === "tool"
      ? { rotate: [-10, 12, -10] }
      : activity.kind === "composing"
        ? { scale: [0.82, 1.08, 0.82], opacity: [0.55, 1, 0.55] }
        : themedAnimation;

  return (
    <motion.div
      className={`thesos-activity is-${activity.kind}`}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -4 }}
      role="status"
      aria-label={activity.label}
    >
      <motion.span
        className="activity-icon"
        aria-hidden="true"
        animate={reducedMotion ? undefined : animation}
        transition={
          reducedMotion
            ? undefined
            : { duration: activity.kind === "tool" ? 0.9 : 1.1, repeat: Infinity, ease: "linear" }
        }
      >
        <Icon size={15} weight="thin" />
      </motion.span>
      <span>{activity.label}</span>
    </motion.div>
  );
}

export function ConversationView({
  conversation,
  onEdit,
  onRevealComplete,
}: ConversationViewProps) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const renderedConversationId = useRef<string | null>(null);
  const copyResetTimer = useRef<number | null>(null);
  const [copiedMessageId, setCopiedMessageId] = useState<string | null>(null);

  useLayoutEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const conversationChanged = renderedConversationId.current !== conversation.id;
    const distanceFromBottom = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight;
    if (conversationChanged || distanceFromBottom < 180) {
      if (typeof viewport.scrollTo === "function") {
        viewport.scrollTo({
          top: viewport.scrollHeight,
          behavior: conversationChanged ? "auto" : "smooth",
        });
      } else {
        viewport.scrollTop = viewport.scrollHeight;
      }
    }
    renderedConversationId.current = conversation.id;
  }, [conversation.activity, conversation.id, conversation.messages]);

  useEffect(
    () => () => {
      if (copyResetTimer.current !== null) window.clearTimeout(copyResetTimer.current);
    },
    [],
  );

  const copyMessage = async (message: ChatMessage) => {
    await navigator.clipboard.writeText(message.content);
    setCopiedMessageId(message.id);
    if (copyResetTimer.current !== null) window.clearTimeout(copyResetTimer.current);
    copyResetTimer.current = window.setTimeout(() => setCopiedMessageId(null), 1400);
  };

  return (
    <div className="conversation-shell">
      <div className="conversation-view" ref={viewportRef}>
        <div className="conversation-feed">
          <div className="conversation-column">
            <AnimatePresence initial={false}>
              {conversation.messages.map((message) => (
            <motion.article
              layout="position"
              key={message.id}
              className={`message ${message.role} ${message.state}`}
              initial={{ opacity: 0, y: 14 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8, height: 0 }}
              transition={{ duration: 0.28 }}
            >
              <header><span>{message.role === "assistant" ? "THESOS" : "TENNO"}</span></header>
              {message.role === "user" ? (
                <>
                  <div className="message-bubble"><p>{message.content}</p></div>
                  <footer className="message-actions">
                    <button
                      type="button"
                      onClick={() => onEdit(message)}
                      aria-label="Edit this message"
                      title="Edit this message"
                    >
                      <PencilSimple size={14} weight="thin" />
                    </button>
                    <button
                      type="button"
                      onClick={() => void copyMessage(message)}
                      aria-label="Copy this message"
                      title="Copy this message"
                    >
                      {copiedMessageId === message.id ? (
                        <Check size={14} weight="thin" />
                      ) : (
                        <Copy size={14} weight="thin" />
                      )}
                    </button>
                  </footer>
                </>
              ) : (
                <div className="assistant-message-copy">
                  <AssistantResponse message={message} onRevealComplete={onRevealComplete} />
                  {message.state === "failed" ? (
                    <small><WarningCircle size={14} weight="thin" /> Archive link interrupted</small>
                  ) : null}
                </div>
              )}
            </motion.article>
              ))}
            </AnimatePresence>
            <AnimatePresence>
              {conversation.activity ? (
                <ActivityIndicator activity={conversation.activity} />
              ) : null}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
}

import { AnimatePresence, motion } from "motion/react";
import { lazy, Suspense, useCallback, useState, type CSSProperties } from "react";
import { Route, Routes } from "react-router-dom";

import { Composer } from "../components/Composer";
import { ConversationView } from "../components/ConversationView";
import { Header } from "../components/Header";
import { IntroSequence } from "../components/IntroSequence";
import { Landing } from "../components/Landing";
import { Sidebar } from "../components/Sidebar";
import { ThemePicker } from "../components/ThemePicker";
import { ThesosBrand } from "../components/ThesosBrand";
import { useChatController } from "../features/chat/useChatController";
import { useUserIdentity } from "../features/identity/useUserIdentity";
import { useSidebarWidth } from "../features/shell/useSidebarWidth";
import { InfoPage } from "./InfoPage";

const ArchiveScene = lazy(async () => {
  const module = await import("../components/ArchiveScene");
  return { default: module.ArchiveScene };
});
const DeveloperPanel = import.meta.env.DEV
  ? lazy(async () => {
      const module = await import("../components/DeveloperPanel");
      return { default: module.DeveloperPanel };
    })
  : null;

const DEVELOPER_MODE_KEY = "thesos.developer-mode";

function ChatPage() {
  const identity = useUserIdentity();
  const chat = useChatController(identity.displayName);
  const { resetSidebarWidth, setSidebarWidth, sidebarWidth } = useSidebarWidth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [themePickerOpen, setThemePickerOpen] = useState(false);
  const [developerMode, setDeveloperMode] = useState(
    () =>
      import.meta.env.DEV &&
      (localStorage.getItem(DEVELOPER_MODE_KEY) === "true" ||
        localStorage.getItem("veris.developer-mode") === "true"),
  );
  const showIntro =
    chat.conversationCount === 0 &&
    !identity.introComplete &&
    chat.activeConversation === null;
  const showLanding = !chat.activeConversation || chat.activeConversation.messages.length === 0;
  const changeDeveloperMode = useCallback((enabled: boolean) => {
    localStorage.setItem(DEVELOPER_MODE_KEY, String(enabled));
    localStorage.removeItem("veris.developer-mode");
    setDeveloperMode(enabled);
  }, []);

  return (
    <div
      className={`app-shell ${showIntro ? "intro-active" : ""} ${developerMode ? "developer-open" : ""} ${showLanding ? "" : "has-active-conversation"}`}
      style={{ "--sidebar-width": `${sidebarWidth}px` } as CSSProperties}
    >
      <Suspense fallback={null}>
        <ArchiveScene />
      </Suspense>
      <ThesosBrand intro={showIntro} />
      <AnimatePresence>
        {showIntro ? <IntroSequence onComplete={identity.completeIntro} /> : null}
      </AnimatePresence>
      <motion.div
        className="interface-layer"
        initial={false}
        animate={{ opacity: showIntro ? 0 : 1 }}
        transition={{ duration: 0.65, delay: showIntro ? 0 : 0.18 }}
        aria-hidden={showIntro}
        inert={showIntro}
      >
        <Sidebar
          conversations={chat.conversations}
          activeId={chat.activeId}
          open={menuOpen}
          onClose={() => setMenuOpen(false)}
          onNewChat={() => {
            chat.newChat();
            setMenuOpen(false);
          }}
          onSelect={(conversationId) => {
            chat.setActiveId(conversationId);
            setMenuOpen(false);
          }}
          onDelete={chat.deleteConversation}
          onTogglePinned={chat.toggleConversationPinned}
          onOpenThemes={() => {
            setThemePickerOpen(true);
            setMenuOpen(false);
          }}
          width={sidebarWidth}
          onWidthChange={setSidebarWidth}
          onWidthReset={resetSidebarWidth}
        />
        <Header
          conversation={showLanding ? null : chat.activeConversation}
          developerMode={developerMode}
          onDeveloperModeChange={changeDeveloperMode}
          onOpenMenu={() => setMenuOpen(true)}
        />
        <AnimatePresence>
          {themePickerOpen ? <ThemePicker onClose={() => setThemePickerOpen(false)} /> : null}
        </AnimatePresence>
        <AnimatePresence>
          {developerMode && DeveloperPanel ? (
            <Suspense fallback={null}>
              <DeveloperPanel onClose={() => changeDeveloperMode(false)} />
            </Suspense>
          ) : null}
        </AnimatePresence>
        <section className={`workspace ${showLanding ? "is-landing" : "is-conversation"}`}>
          <AnimatePresence mode="wait" initial={false}>
            {showLanding ? (
              <motion.div
                key="landing"
                className="workspace-state"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
              >
                <Landing
                  newVisitor={chat.conversationCount === 0}
                  onSuggestion={(prompt) => void chat.submit(prompt)}
                />
              </motion.div>
            ) : (
              <motion.div
                key={chat.activeConversation?.id}
                className="workspace-state"
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
              >
                {chat.activeConversation ? (
              <ConversationView
                conversation={chat.activeConversation}
                branchingDisabled={chat.running || chat.activeConversation.terminated}
                onBranch={chat.branchFromMessage}
                onEdit={chat.beginEdit}
                onRevealComplete={chat.completeReveal}
              />
                ) : null}
              </motion.div>
            )}
          </AnimatePresence>
          <Composer
            draft={chat.draft}
            editing={chat.editingMessageId !== null}
            landing={showLanding}
            running={chat.running}
            terminated={chat.activeConversation?.terminated ?? false}
            onDraftChange={chat.setDraft}
            onSubmit={() => void chat.submit()}
            onStop={() => void chat.stop()}
            onCancelEdit={() => {
              chat.setEditingMessageId(null);
              chat.setDraft("");
            }}
            onNewChat={chat.newChat}
          />
          <footer className="legal-note">Unofficial. Answers can be wrong. Check cited sources.</footer>
        </section>
      </motion.div>
    </div>
  );
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<ChatPage />} />
      <Route
        path="/about"
        element={
          <InfoPage title="About">
            <p>
              Thesos is an unofficial conversational archive built to help players explore
              Warframe systems, builds, and the wider ecosystem around the game.
            </p>
          </InfoPage>
        }
      />
      <Route
        path="/privacy"
        element={
          <InfoPage title="Privacy">
            <p>
              This local alpha stores conversations in your browser and sends submitted prompts to
              the configured model provider. Production retention and provider controls are still
              being commissioned.
            </p>
          </InfoPage>
        }
      />
    </Routes>
  );
}

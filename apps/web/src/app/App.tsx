import { AnimatePresence, motion } from "motion/react";
import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import { Route, Routes } from "react-router-dom";

import { Composer } from "../components/Composer";
import { AuthActionPage } from "../components/AuthActionPage";
import { AuthGate } from "../components/AuthGate";
import { ConversationView } from "../components/ConversationView";
import { Header } from "../components/Header";
import { IntroSequence } from "../components/IntroSequence";
import { Landing } from "../components/Landing";
import { Sidebar } from "../components/Sidebar";
import { ThemePicker } from "../components/ThemePicker";
import { ThesosBrand } from "../components/ThesosBrand";
import { useAuth } from "../features/auth/AuthContext";
import { useChatController } from "../features/chat/useChatController";
import { useUserIdentity } from "../features/identity/useUserIdentity";
import { useSidebarWidth } from "../features/shell/useSidebarWidth";
import { useTheme } from "../features/theme/ThemeContext";
import { isThemeId } from "../features/theme/themes";
import { InfoPage } from "./InfoPage";
import { AdminPage } from "./AdminPage";

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

interface ChatPageProps {
  resumeIntroAfterAuth?: boolean;
}

function ChatPage({ resumeIntroAfterAuth = false }: ChatPageProps) {
  const auth = useAuth();
  const identity = useUserIdentity();
  const { setThemeId, themeId } = useTheme();
  const displayName = auth.user?.preferences.display_name ?? identity.displayName;
  const chat = useChatController(displayName, auth.user?.id);
  const { resetSidebarWidth, setSidebarWidth, sidebarWidth } = useSidebarWidth();
  const initializedPreferences = useRef<string | null>(null);
  const skipPreferenceSync = useRef(false);
  const updatePreferences = useRef(auth.updatePreferences);
  const refreshAuth = useRef(auth.refresh);
  const wasRunning = useRef(false);
  const accountId = auth.user?.id;
  const [menuOpen, setMenuOpen] = useState(false);
  const [themePickerOpen, setThemePickerOpen] = useState(false);
  const [namePromptDismissed, setNamePromptDismissed] = useState(false);
  const [developerMode, setDeveloperMode] = useState(
    () =>
      import.meta.env.DEV &&
      (localStorage.getItem(DEVELOPER_MODE_KEY) === "true" ||
        localStorage.getItem("veris.developer-mode") === "true"),
  );
  const showIntro =
    chat.hydrated &&
    chat.conversationCount === 0 &&
    !displayName &&
    !namePromptDismissed &&
    chat.activeConversation === null;
  const showLanding = !chat.activeConversation || chat.activeConversation.messages.length === 0;

  useEffect(() => {
    updatePreferences.current = auth.updatePreferences;
    refreshAuth.current = auth.refresh;
  }, [auth.refresh, auth.updatePreferences]);

  useEffect(() => {
    if (wasRunning.current && !chat.running) void refreshAuth.current();
    wasRunning.current = chat.running;
  }, [chat.running]);

  useEffect(() => {
    const account = auth.user;
    if (!account || initializedPreferences.current === account.id) return;
    skipPreferenceSync.current = true;
    initializedPreferences.current = account.id;
    if (isThemeId(account.preferences.theme_id)) setThemeId(account.preferences.theme_id);
    if (account.preferences.sidebar_width !== null) {
      setSidebarWidth(account.preferences.sidebar_width);
    }
  }, [auth.user, setSidebarWidth, setThemeId]);

  useEffect(() => {
    if (!accountId || initializedPreferences.current !== accountId) return;
    if (skipPreferenceSync.current) {
      skipPreferenceSync.current = false;
      return;
    }
    const timer = window.setTimeout(() => {
      void updatePreferences.current({ theme_id: themeId, sidebar_width: sidebarWidth });
    }, 700);
    return () => window.clearTimeout(timer);
  }, [accountId, sidebarWidth, themeId]);
  const changeDeveloperMode = useCallback((enabled: boolean) => {
    localStorage.setItem(DEVELOPER_MODE_KEY, String(enabled));
    localStorage.removeItem("veris.developer-mode");
    setDeveloperMode(enabled);
  }, []);

  if (!chat.hydrated) {
    return (
      <div className="app-shell">
        <Suspense fallback={null}><ArchiveScene /></Suspense>
        <div className="auth-loading" aria-label="Synchronising the Archives"><i /></div>
      </div>
    );
  }

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
        {showIntro ? (
          <IntroSequence
            skipTyping={resumeIntroAfterAuth}
            onComplete={(name) => {
              setNamePromptDismissed(true);
              identity.completeIntro(name);
              if (name) void auth.updatePreferences({ display_name: name });
            }}
          />
        ) : null}
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

function RootPage() {
  const auth = useAuth();
  const [authMode, setAuthMode] = useState<"login" | "register" | null>(null);
  const [enteredThroughIntro, setEnteredThroughIntro] = useState(false);
  if (auth.status === "loading") {
    return <div className="auth-loading" aria-label="Opening the Archives"><i /></div>;
  }
  if (!auth.user) {
    return (
      <div className="app-shell intro-active logged-out-intro">
        <Suspense fallback={null}><ArchiveScene /></Suspense>
        <ThesosBrand intro />
        <IntroSequence
          mode="auth"
          onLogin={() => {
            setEnteredThroughIntro(true);
            setAuthMode("login");
          }}
          onRegister={() => {
            setEnteredThroughIntro(true);
            setAuthMode("register");
          }}
        />
        <AnimatePresence>
          {authMode ? (
            <motion.div
              className="auth-modal-backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.35 }}
              onMouseDown={(event) => {
                if (event.target === event.currentTarget) setAuthMode(null);
              }}
            >
              <AuthGate
                key={authMode}
                initialMode={authMode}
                modal
                onClose={() => setAuthMode(null)}
              />
            </motion.div>
          ) : null}
        </AnimatePresence>
      </div>
    );
  }
  return <ChatPage resumeIntroAfterAuth={enteredThroughIntro} />;
}

export function App() {
  return (
    <Routes>
      <Route path="/" element={<RootPage />} />
      <Route path="/verify" element={<AuthActionPage action="verify" />} />
      <Route path="/reset-password" element={<AuthActionPage action="reset" />} />
      <Route path="/admin" element={<AdminPage />} />
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
              Thesos stores account settings and conversations so they remain available across
              sessions. Submitted prompts are sent to the configured model provider. Passwords,
              session tokens, and security signals are stored only in protected or pseudonymous
              forms; ordinary IP addresses are not retained.
            </p>
          </InfoPage>
        }
      />
      <Route
        path="/terms"
        element={
          <InfoPage title="Private Alpha Terms">
            <p>
              Thesos is an experimental, unofficial Warframe knowledge assistant. Submitted
              prompts may be sent to configured model providers and answers may be inaccurate.
              Do not submit private, confidential, or sensitive information.
            </p>
          </InfoPage>
        }
      />
    </Routes>
  );
}

import { motion } from "motion/react";

import { suggestions } from "../features/chat/suggestions";
import { SuggestionRail } from "./SuggestionRail";

interface LandingProps {
  newVisitor: boolean;
  onSuggestion: (prompt: string) => void;
}

export function Landing({ newVisitor, onSuggestion }: LandingProps) {
  return (
    <main className="landing-view">
      <motion.div
        className="archive-prompt"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.65 }}
      >
        {newVisitor ? <span className="speaker-mark">WELCOME, TENNO</span> : null}
        <div className="prompt-line">
          <i />
          <h1>Ask of what you need, Tenno. I will search the Archives.</h1>
          <i />
        </div>
        <p>
          {newVisitor
            ? "Begin with a question, a build, or something you encountered in the Origin System."
            : "The Archive link is open. Where shall we begin?"}
        </p>
      </motion.div>
      <SuggestionRail suggestions={suggestions} onSelect={onSuggestion} />
    </main>
  );
}

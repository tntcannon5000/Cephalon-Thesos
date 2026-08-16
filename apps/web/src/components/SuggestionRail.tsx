import { Atom, BellRinging, Compass, Sparkle } from "@phosphor-icons/react";
import { motion } from "motion/react";
import type { Icon } from "@phosphor-icons/react";

import type { Suggestion } from "../features/chat/types";

const icons: Record<Suggestion["icon"], Icon> = {
  orbit: Atom,
  signal: BellRinging,
  archive: Compass,
  build: Sparkle,
};

interface SuggestionRailProps {
  suggestions: Suggestion[];
  onSelect: (prompt: string) => void;
}

export function SuggestionRail({ suggestions, onSelect }: SuggestionRailProps) {
  return (
    <motion.div
      className="suggestion-rail"
      initial="hidden"
      animate="visible"
      variants={{
        hidden: {},
        visible: { transition: { staggerChildren: 0.07, delayChildren: 0.16 } },
      }}
      aria-label="Suggested questions"
    >
      {suggestions.map((suggestion) => {
        const SuggestionIcon = icons[suggestion.icon];
        return (
          <motion.button
            className="suggestion-card"
            type="button"
            key={suggestion.id}
            onClick={() => onSelect(suggestion.prompt)}
            variants={{
              hidden: { opacity: 0, y: 12 },
              visible: { opacity: 1, y: 0 },
            }}
            whileHover={{ y: -3 }}
            whileTap={{ scale: 0.985 }}
          >
            <SuggestionIcon className="suggestion-icon" size={28} weight="thin" />
            <span className="suggestion-prompt">{suggestion.prompt}</span>
            <small>{suggestion.meta}</small>
            <i aria-hidden="true" />
          </motion.button>
        );
      })}
    </motion.div>
  );
}


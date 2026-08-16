import type { Suggestion } from "./types";

export const suggestions: Suggestion[] = [
  {
    id: "incarnons",
    prompt: "Which Incarnon Genesis adapters are available this week?",
    meta: "Weekly rotation",
    icon: "orbit",
  },
  {
    id: "events",
    prompt: "What events and alerts are active right now?",
    meta: "Live state",
    icon: "signal",
  },
  {
    id: "archon",
    prompt: "Where does Archon Stretch drop?",
    meta: "Archive lookup",
    icon: "archive",
  },
  {
    id: "build",
    prompt: "Build me a Steel Path setup for Gyre.",
    meta: "Build planning",
    icon: "build",
  },
];

import { Check, X } from "@phosphor-icons/react";
import { motion } from "motion/react";
import { useEffect } from "react";

import { useTheme } from "../features/theme/ThemeContext";
import { themes } from "../features/theme/themes";

interface ThemePickerProps {
  onClose: () => void;
}

export function ThemePicker({ onClose }: ThemePickerProps) {
  const { themeId, setThemeId } = useTheme();
  const themeGroups = [
    { scheme: "light" as const, label: "Light environments" },
    { scheme: "dark" as const, label: "Dark environments" },
  ];

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <>
      <motion.button
        className="theme-picker-scrim"
        type="button"
        aria-label="Close theme selection"
        onClick={onClose}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
      />
      <motion.section
        className="theme-picker"
        role="dialog"
        aria-modal="true"
        aria-labelledby="theme-picker-title"
        initial={{ opacity: 0, x: -10, y: 8 }}
        animate={{ opacity: 1, x: 0, y: 0 }}
        exit={{ opacity: 0, x: -8, y: 6 }}
        transition={{ duration: 0.2 }}
      >
        <header>
          <div>
            <span>APPEARANCE</span>
            <h2 id="theme-picker-title">Interface theme</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close theme selection">
            <X size={18} weight="thin" />
          </button>
        </header>
        <div className="theme-groups">
          {themeGroups.map(({ scheme, label }) => (
            <section className="theme-group" key={scheme}>
              <h3>{label}</h3>
              <div className="theme-options">
                {themes
                  .filter((theme) => theme.colorScheme === scheme)
                  .map((theme) => {
                    const selected = theme.id === themeId;
                    return (
                      <button
                        className={`theme-option ${selected ? "is-selected" : ""}`}
                        type="button"
                        key={theme.id}
                        aria-pressed={selected}
                        onClick={() => setThemeId(theme.id)}
                      >
                        <span
                          className="theme-preview"
                          data-profile={theme.scene.profile}
                          style={{
                            backgroundColor: theme.palette.background,
                            backgroundImage: theme.backdrop
                              ? `linear-gradient(${theme.backdrop.overlay}, ${theme.backdrop.overlay}), url("${theme.backdrop.image}")`
                              : undefined,
                            backgroundPosition: theme.backdrop?.position,
                            backgroundSize: theme.backdrop ? "cover" : undefined,
                            borderColor: theme.palette.lineStrong,
                            color: theme.palette.accent,
                            "--preview-surface": theme.palette.surfaceRaised,
                            "--preview-secondary": theme.palette.secondary,
                          } as React.CSSProperties}
                          aria-hidden="true"
                        >
                          <i />
                          <i />
                          <i />
                          <i />
                          {theme.id === "sentient-eclipse" ? <em>OLED</em> : null}
                          {selected ? <Check size={18} weight="bold" /> : null}
                        </span>
                        <strong>{theme.name}</strong>
                        <small>{theme.description}</small>
                      </button>
                    );
                  })}
              </div>
            </section>
          ))}
        </div>
      </motion.section>
    </>
  );
}

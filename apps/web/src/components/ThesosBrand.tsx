import { motion, useReducedMotion } from "motion/react";

interface ThesosBrandProps {
  intro: boolean;
}

export function ThesosBrand({ intro }: ThesosBrandProps) {
  const reducedMotion = useReducedMotion();

  return (
    <motion.div
      className={`brand-block thesos-brand ${intro ? "is-intro" : ""}`}
      initial={intro && !reducedMotion ? { opacity: 0 } : false}
      animate={{ opacity: 1 }}
      transition={{ duration: reducedMotion ? 0 : 0.5, delay: intro ? 0.26 : 0 }}
      aria-label="Thesos, a Warframe knowledge Cephalon"
    >
      <span>THESOS</span>
      <small><i /> A WARFRAME KNOWLEDGE CEPHALON</small>
    </motion.div>
  );
}

import { useState } from "react";

import {
  MAX_SIDEBAR_WIDTH,
  MIN_SIDEBAR_WIDTH,
} from "../features/shell/useSidebarWidth";

interface SidebarResizeHandleProps {
  width: number;
  onChange: (width: number) => void;
  onReset: () => void;
}

export function SidebarResizeHandle({
  width,
  onChange,
  onReset,
}: SidebarResizeHandleProps) {
  const [resizing, setResizing] = useState(false);

  const finishResize = (element: HTMLDivElement, pointerId: number) => {
    if (element.hasPointerCapture(pointerId)) element.releasePointerCapture(pointerId);
    setResizing(false);
  };

  return (
    <div
      className={`sidebar-resize-handle ${resizing ? "is-resizing" : ""}`}
      role="separator"
      aria-label="Resize conversation panel"
      aria-orientation="vertical"
      aria-valuemin={MIN_SIDEBAR_WIDTH}
      aria-valuemax={MAX_SIDEBAR_WIDTH}
      aria-valuenow={width}
      tabIndex={0}
      onDoubleClick={onReset}
      onKeyDown={(event) => {
        if (event.key === "ArrowLeft") {
          event.preventDefault();
          onChange(width - (event.shiftKey ? 24 : 8));
        }
        if (event.key === "ArrowRight") {
          event.preventDefault();
          onChange(width + (event.shiftKey ? 24 : 8));
        }
        if (event.key === "Home") {
          event.preventDefault();
          onChange(MIN_SIDEBAR_WIDTH);
        }
        if (event.key === "End") {
          event.preventDefault();
          onChange(MAX_SIDEBAR_WIDTH);
        }
      }}
      onPointerDown={(event) => {
        if (event.pointerType === "mouse" && event.button !== 0) return;
        event.currentTarget.setPointerCapture(event.pointerId);
        setResizing(true);
        onChange(event.clientX);
      }}
      onPointerMove={(event) => {
        if (!event.currentTarget.hasPointerCapture(event.pointerId)) return;
        onChange(event.clientX);
      }}
      onPointerUp={(event) => finishResize(event.currentTarget, event.pointerId)}
      onPointerCancel={(event) => finishResize(event.currentTarget, event.pointerId)}
    >
      <i aria-hidden="true" />
    </div>
  );
}

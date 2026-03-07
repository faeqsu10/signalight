"use client";

import { useState } from "react";

interface TooltipProps {
  content: React.ReactNode;
  children?: React.ReactNode;
}

export default function Tooltip({ content, children }: TooltipProps) {
  const [show, setShow] = useState(false);

  return (
    <span
      className="relative inline-flex items-center"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children ?? (
        <span className="ml-1 inline-flex items-center justify-center w-4 h-4 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400 text-[10px] font-bold cursor-help hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors">
          ?
        </span>
      )}
      {show && (
        <div className="absolute top-full left-0 mt-2 z-50 w-64 p-3 rounded-lg bg-[var(--tooltip-bg)] border border-[var(--tooltip-border)] shadow-xl text-xs text-[var(--foreground)] leading-relaxed">
          <div className="absolute bottom-full left-4 w-0 h-0 border-l-4 border-r-4 border-b-4 border-transparent border-b-[var(--tooltip-border)]" />
          {content}
        </div>
      )}
    </span>
  );
}

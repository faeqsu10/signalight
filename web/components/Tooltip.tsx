"use client";

import { useState, useRef, useEffect } from "react";

interface TooltipProps {
  content: React.ReactNode;
  children?: React.ReactNode;
}

export default function Tooltip({ content, children }: TooltipProps) {
  const [show, setShow] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!show) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setShow(false);
      }
    };
    document.addEventListener("click", handleClickOutside);
    return () => document.removeEventListener("click", handleClickOutside);
  }, [show]);

  return (
    <span
      ref={ref}
      className="relative inline-flex items-center"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
      onClick={(e) => {
        e.stopPropagation();
        setShow((prev) => !prev);
      }}
    >
      {children ?? (
        <span
          className="ml-1 inline-flex items-center justify-center w-4 h-4 rounded-full text-[10px] font-bold cursor-help transition-colors"
          style={{
            background: "var(--glass)",
            border: "1px solid var(--glass-border)",
            color: "var(--text-dim)",
          }}
          onMouseEnter={e => (e.currentTarget.style.borderColor = "var(--accent)")}
          onMouseLeave={e => (e.currentTarget.style.borderColor = "var(--glass-border)")}
        >
          ?
        </span>
      )}
      {show && (
        <div
          className="absolute top-full left-0 mt-2 z-50 w-64 p-3 rounded-xl text-xs leading-relaxed"
          style={{
            background: "var(--dropdown-bg)",
            backdropFilter: "blur(20px)",
            border: "1px solid var(--glass-border)",
            boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
            color: "var(--foreground)",
          }}
        >
          <div
            className="absolute bottom-full left-4 w-0 h-0"
            style={{
              borderLeft: "4px solid transparent",
              borderRight: "4px solid transparent",
              borderBottom: "4px solid var(--glass-border)",
            }}
          />
          {content}
        </div>
      )}
    </span>
  );
}

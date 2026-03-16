"use client";

import Link from "next/link";

type WatchItem = {
  idx: number;
  ticker: string;
  name: string;
  market: string;
};

function SignalDot({ strength }: { strength: string | undefined }) {
  if (!strength) return null;
  if (strength === "strong_buy" || strength === "buy") {
    return (
      <span
        className="ml-1 inline-block h-2 w-2 flex-shrink-0 rounded-full"
        style={{ background: "var(--buy)", boxShadow: "0 0 4px var(--buy)" }}
      />
    );
  }
  if (strength === "strong_sell" || strength === "sell") {
    return (
      <span
        className="ml-1 inline-block h-2 w-2 flex-shrink-0 rounded-full"
        style={{ background: "var(--sell)", boxShadow: "0 0 4px var(--sell)" }}
      />
    );
  }
  return (
    <span
      className="ml-1 inline-block h-2 w-2 flex-shrink-0 rounded-full"
      style={{ background: "var(--text-dim)" }}
    />
  );
}

type SignalsWorkspaceHeaderProps = {
  selectedName: string;
  selectedTicker: string;
  hasData: boolean;
  isFavorite: boolean;
  compareActive: boolean;
  favorites: string[];
  compareCandidates: WatchItem[];
  searchResults: WatchItem[];
  signalCache: Record<string, string>;
  searchQuery: string;
  showSearch: boolean;
  showComparePicker: boolean;
  mounted: boolean;
  notifPermission: NotificationPermission;
  onToggleFavorite: () => void;
  onToggleCompare: () => void;
  onCloseCompare: () => void;
  onSelectCompare: (idx: number) => void;
  onSearchQueryChange: (value: string) => void;
  onSearchOpen: () => void;
  onSearchClose: () => void;
  onSelectTicker: (idx: number) => void;
  onRequestNotifications: () => void;
};

export default function SignalsWorkspaceHeader({
  selectedName,
  selectedTicker,
  hasData,
  isFavorite,
  compareActive,
  favorites,
  compareCandidates,
  searchResults,
  signalCache,
  searchQuery,
  showSearch,
  showComparePicker,
  mounted,
  notifPermission,
  onToggleFavorite,
  onToggleCompare,
  onCloseCompare,
  onSelectCompare,
  onSearchQueryChange,
  onSearchOpen,
  onSearchClose,
  onSelectTicker,
  onRequestNotifications,
}: SignalsWorkspaceHeaderProps) {
  return (
    <section className="px-4 pt-8">
      <div
        className="mx-auto flex max-w-7xl flex-col gap-4 rounded-[28px] px-6 py-6 lg:flex-row lg:items-center lg:justify-between glass-card"
        style={{
          background: "var(--hero-surface)",
        }}
      >
        <div className="flex items-start gap-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.26em]" style={{ color: "var(--accent)" }}>
              KR Signals
            </p>
            <h1 className="mt-2 text-2xl font-bold tracking-[0.16em]" style={{ color: "var(--foreground)" }}>
              ANALYSIS WORKSTATION
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6" style={{ color: "var(--text-dim)" }}>
              한 종목을 깊게 읽는 KR 분석 화면입니다.
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]">
              <span
                className="rounded-full px-2.5 py-1"
                style={{
                  color: "var(--foreground)",
                  background: "rgba(255,255,255,0.04)",
                  border: "1px solid rgba(255,255,255,0.05)",
                }}
              >
                선택 종목 {selectedName} · {selectedTicker}
              </span>
              <span
                className="rounded-full px-2.5 py-1"
                style={{
                  color: "var(--buy)",
                  background: "rgba(255,207,51,0.08)",
                  border: "1px solid rgba(255,207,51,0.12)",
                }}
              >
                Analysis Live
              </span>
              {hasData && (
                <span style={{ color: "var(--text-dim)" }}>
                  Last Sync {new Date().toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" })}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 lg:justify-end">
          <button
            onClick={onToggleFavorite}
            title={isFavorite ? "즐겨찾기 해제" : "즐겨찾기 추가"}
            className="rounded-xl px-3 py-2 text-sm transition-colors focus:outline-none"
            style={{
              color: isFavorite ? "var(--hold)" : "var(--text-dim)",
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.05)",
            }}
            aria-label={isFavorite ? "즐겨찾기 해제" : "즐겨찾기 추가"}
          >
            {isFavorite ? "★ 즐겨찾기" : "☆ 즐겨찾기"}
          </button>
          <div className="relative">
            <button
              onClick={onToggleCompare}
              className="rounded-xl px-3 py-2 text-sm transition-colors"
              style={{
                border: "1px solid var(--glass-border)",
                background: compareActive ? "rgba(246,197,68,0.12)" : "rgba(255,255,255,0.03)",
                color: compareActive ? "var(--accent)" : "var(--text-dim)",
              }}
            >
              {compareActive ? "비교 해제" : "종목 비교"}
            </button>
            {showComparePicker && (
              <>
                <div className="fixed inset-0 z-40" onClick={onCloseCompare} />
                <div
                  className="absolute left-0 top-full z-50 mt-2 max-h-64 w-52 overflow-y-auto rounded-xl"
                  style={{
                    background: "var(--dropdown-bg)",
                    backdropFilter: "blur(20px)",
                    border: "1px solid var(--glass-border)",
                    boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
                  }}
                >
                  {compareCandidates.map((item) => (
                    <button
                      key={item.ticker}
                      onClick={() => onSelectCompare(item.idx)}
                      className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors"
                      style={{ color: "var(--foreground)" }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--glass)")}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                    >
                      <span
                        className="flex-shrink-0 rounded px-1.5 py-0.5 text-[10px]"
                        style={{
                          background: item.market === "KR" ? "rgba(246,197,68,0.14)" : "rgba(255,207,51,0.08)",
                          color: item.market === "KR" ? "var(--accent)" : "var(--buy)",
                        }}
                      >
                        {item.market}
                      </span>
                      <span className="truncate">{item.name}</span>
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
          <Link
            href="/autonomous"
            className="hidden rounded-xl px-3 py-2 text-sm transition-colors sm:inline"
            style={{
              color: "var(--accent)",
              background: "rgba(246,197,68,0.08)",
              border: "1px solid rgba(246,197,68,0.12)",
            }}
          >
            자율매매 →
          </Link>
          <div className="relative z-50">
            <input
              type="text"
              placeholder="종목 검색..."
              value={searchQuery}
              onChange={(e) => onSearchQueryChange(e.target.value)}
              onFocus={onSearchOpen}
              className="w-44 rounded-xl px-3 py-2 text-sm focus:outline-none sm:w-52"
              style={{ color: "var(--foreground)" }}
            />
            {showSearch && searchResults.length > 0 && (
              <div
                className="absolute left-0 right-0 top-full z-50 mt-2 max-h-64 overflow-y-auto rounded-xl"
                style={{
                  background: "var(--dropdown-bg)",
                  backdropFilter: "blur(20px)",
                  border: "1px solid var(--glass-border)",
                  boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
                }}
              >
                {searchResults.map((item) => {
                  const itemIsFav = favorites.includes(item.ticker);
                  const strength = signalCache[item.ticker];
                  return (
                    <button
                      key={item.ticker}
                      onClick={() => onSelectTicker(item.idx)}
                      className="flex min-h-[44px] w-full items-center justify-between px-3 py-2.5 text-left text-sm transition-colors"
                      style={{ color: "var(--foreground)" }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--glass)")}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                    >
                      <span className="flex items-center gap-1.5">
                        {itemIsFav && (
                          <span className="text-xs leading-none" style={{ color: "var(--hold)" }}>
                            ★
                          </span>
                        )}
                        <span
                          className="rounded px-1.5 py-0.5 text-[10px]"
                          style={{
                            background: item.market === "KR" ? "rgba(108,92,231,0.2)" : "rgba(0,212,170,0.15)",
                            color: item.market === "KR" ? "var(--accent)" : "var(--buy)",
                          }}
                        >
                          {item.market}
                        </span>
                        {item.name}
                        <SignalDot strength={strength} />
                      </span>
                      <span className="ml-2 flex-shrink-0 text-xs" style={{ color: "var(--text-dim)" }}>
                        {item.ticker}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
            {showSearch && <div className="fixed inset-0 z-40" onClick={onSearchClose} />}
          </div>
          {mounted && "Notification" in window && (
            <button
              onClick={onRequestNotifications}
              title={
                notifPermission === "granted"
                  ? "알림 활성"
                  : notifPermission === "denied"
                    ? "알림 차단됨"
                    : "알림 설정"
              }
              className="rounded-xl px-3 py-2 text-sm transition-opacity hover:opacity-80"
              style={{
                color: notifPermission === "granted" ? "var(--buy)" : "var(--text-dim)",
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.05)",
              }}
            >
              {notifPermission === "granted" ? "🔔 알림" : "🔕 알림"}
            </button>
          )}
        </div>
      </div>
    </section>
  );
}

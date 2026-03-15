"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
  createSeriesMarkers,
} from "lightweight-charts";
import { OHLCVData } from "@/lib/yahoo-finance";
import { useTheme } from "./ThemeProvider";

interface SignalHistoryEntry {
  index: number;
  type: "buy" | "sell";
  name: string;
}

interface Props {
  ohlcv: OHLCVData[];
  shortMA: (number | null)[];
  longMA: (number | null)[];
  bollingerUpper?: (number | null)[];
  bollingerLower?: (number | null)[];
  signalHistory?: SignalHistoryEntry[];
}

export default function CandleChart({ ohlcv, shortMA, longMA, bollingerUpper, bollingerLower, signalHistory }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();

  useEffect(() => {
    if (!containerRef.current || ohlcv.length === 0) return;

    const isDark = theme === "dark";

    const chart = createChart(containerRef.current, {
      layout: {
        background: {
          type: ColorType.Solid,
          color: isDark ? "#0a0e1a" : "#f0f2f5",
        },
        textColor: isDark ? "#d1d5db" : "#374151",
      },
      grid: {
        vertLines: { color: isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)" },
        horzLines: { color: isDark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)" },
      },
      width: containerRef.current.clientWidth,
      height: window.innerWidth < 640 ? 250 : 400,
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#00d4aa",
      downColor: "#ff4757",
      borderUpColor: "#00d4aa",
      borderDownColor: "#ff4757",
      wickUpColor: "#00d4aa",
      wickDownColor: "#ff4757",
    });

    candleSeries.setData(
      ohlcv
        .filter(d => d.date && 
                d.open != null && !isNaN(d.open) &&
                d.high != null && !isNaN(d.high) &&
                d.low != null && !isNaN(d.low) &&
                d.close != null && !isNaN(d.close))
        .map((d) => ({
          time: d.date,
          open: d.open,
          high: d.high,
          low: d.low,
          close: d.close,
        }))
    );

    if (signalHistory && signalHistory.length > 0) {
      const markers = signalHistory
        .filter((e) => e.index < ohlcv.length && ohlcv[e.index]?.date)
        .map((e) => ({
          time: ohlcv[e.index].date as string,
          position: e.type === "buy" ? ("belowBar" as const) : ("aboveBar" as const),
          color: e.type === "buy" ? "#00d4aa" : "#ff4757",
          shape: e.type === "buy" ? ("arrowUp" as const) : ("arrowDown" as const),
          text: e.type === "buy" ? "매수" : "매도",
        }))
        .sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));
      createSeriesMarkers(candleSeries, markers);
    }

    const shortMASeries = chart.addSeries(LineSeries, {
      color: "#facc15",
      lineWidth: 1,
      title: "MA10",
    });
    shortMASeries.setData(
      ohlcv
        .map((d, i) => {
          const val = shortMA[i];
          return (d.date && val !== null && !isNaN(val as number))
            ? { time: d.date, value: val as number }
            : null;
        })
        .filter((item): item is { time: string; value: number } => item !== null)
    );

    const longMASeries = chart.addSeries(LineSeries, {
      color: "#a78bfa",
      lineWidth: 1,
      title: "MA50",
    });
    longMASeries.setData(
      ohlcv
        .map((d, i) => {
          const val = longMA[i];
          return (d.date && val !== null && !isNaN(val as number))
            ? { time: d.date, value: val as number }
            : null;
        })
        .filter((item): item is { time: string; value: number } => item !== null)
    );

    // Bollinger Bands overlay
    if (bollingerUpper && bollingerLower) {
      const bbUpperSeries = chart.addSeries(LineSeries, {
        color: "rgba(156,163,175,0.5)",
        lineWidth: 1,
        lineStyle: 2, // Dashed
        title: "BB Upper",
      });
      bbUpperSeries.setData(
        ohlcv
          .map((d, i) => {
            const val = bollingerUpper[i];
            return (d.date && val !== null && !isNaN(val as number))
              ? { time: d.date, value: val as number }
              : null;
          })
          .filter((item): item is { time: string; value: number } => item !== null)
      );

      const bbLowerSeries = chart.addSeries(LineSeries, {
        color: "rgba(156,163,175,0.5)",
        lineWidth: 1,
        lineStyle: 2, // Dashed
        title: "BB Lower",
      });
      bbLowerSeries.setData(
        ohlcv
          .map((d, i) => {
            const val = bollingerLower[i];
            return (d.date && val !== null && !isNaN(val as number))
              ? { time: d.date, value: val as number }
              : null;
          })
          .filter((item): item is { time: string; value: number } => item !== null)
      );
    }

    // Volume histogram
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });
    volumeSeries.setData(
      ohlcv
        .filter(d => d.date && d.volume != null && !isNaN(d.volume))
        .map((d) => ({
          time: d.date,
          value: d.volume,
          color: d.close >= d.open
            ? "rgba(0,212,170,0.3)"
            : "rgba(255,71,87,0.3)",
        }))
    );

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
          height: window.innerWidth < 640 ? 250 : 400,
        });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [ohlcv, shortMA, longMA, bollingerUpper, bollingerLower, signalHistory, theme]);

  return (
    <div ref={containerRef} className="w-full rounded-lg overflow-hidden" />
  );
}

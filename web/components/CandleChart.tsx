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

  useEffect(() => {
    if (!containerRef.current || ohlcv.length === 0) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: {
          type: ColorType.Solid,
          color: "#0a0e1a",
        },
        textColor: "#d1d5db",
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.06)" },
        horzLines: { color: "rgba(255,255,255,0.06)" },
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
      ohlcv.map((d) => ({
        time: d.date,
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
      }))
    );

    if (signalHistory && signalHistory.length > 0) {
      const markers = signalHistory
        .filter((e) => e.index < ohlcv.length)
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
        .map((d, i) =>
          shortMA[i] !== null
            ? { time: d.date, value: shortMA[i] as number }
            : null
        )
        .filter(Boolean) as { time: string; value: number }[]
    );

    const longMASeries = chart.addSeries(LineSeries, {
      color: "#a78bfa",
      lineWidth: 1,
      title: "MA50",
    });
    longMASeries.setData(
      ohlcv
        .map((d, i) =>
          longMA[i] !== null
            ? { time: d.date, value: longMA[i] as number }
            : null
        )
        .filter(Boolean) as { time: string; value: number }[]
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
          .map((d, i) =>
            bollingerUpper[i] !== null
              ? { time: d.date, value: bollingerUpper[i] as number }
              : null
          )
          .filter(Boolean) as { time: string; value: number }[]
      );

      const bbLowerSeries = chart.addSeries(LineSeries, {
        color: "rgba(156,163,175,0.5)",
        lineWidth: 1,
        lineStyle: 2, // Dashed
        title: "BB Lower",
      });
      bbLowerSeries.setData(
        ohlcv
          .map((d, i) =>
            bollingerLower[i] !== null
              ? { time: d.date, value: bollingerLower[i] as number }
              : null
          )
          .filter(Boolean) as { time: string; value: number }[]
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
      ohlcv.map((d) => ({
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
  }, [ohlcv, shortMA, longMA, bollingerUpper, bollingerLower, signalHistory]);

  return (
    <div ref={containerRef} className="w-full rounded-lg overflow-hidden" />
  );
}

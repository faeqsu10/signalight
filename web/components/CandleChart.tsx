"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  CandlestickSeries,
  LineSeries,
} from "lightweight-charts";
import { OHLCVData } from "@/lib/yahoo-finance";

interface Props {
  ohlcv: OHLCVData[];
  shortMA: (number | null)[];
  longMA: (number | null)[];
}

export default function CandleChart({ ohlcv, shortMA, longMA }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || ohlcv.length === 0) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "#0f0f0f" },
        textColor: "#d1d5db",
      },
      grid: {
        vertLines: { color: "#1f2937" },
        horzLines: { color: "#1f2937" },
      },
      width: containerRef.current.clientWidth,
      height: 400,
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#ef4444",
      downColor: "#3b82f6",
      borderUpColor: "#ef4444",
      borderDownColor: "#3b82f6",
      wickUpColor: "#ef4444",
      wickDownColor: "#3b82f6",
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

    const shortMASeries = chart.addSeries(LineSeries, {
      color: "#facc15",
      lineWidth: 1,
      title: "MA5",
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
      title: "MA20",
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

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [ohlcv, shortMA, longMA]);

  return (
    <div ref={containerRef} className="w-full rounded-lg overflow-hidden" />
  );
}

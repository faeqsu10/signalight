"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  LineSeries,
  HistogramSeries,
} from "lightweight-charts";
import { OHLCVData } from "@/lib/yahoo-finance";

interface Props {
  ohlcv: OHLCVData[];
  macdLine: (number | null)[];
  signalLine: (number | null)[];
  histogram: (number | null)[];
}

export default function MACDChart({
  ohlcv,
  macdLine,
  signalLine,
  histogram,
}: Props) {
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
      height: window.innerWidth < 640 ? 150 : 200,
    });

    const histSeries = chart.addSeries(HistogramSeries, {
      title: "Histogram",
    });
    histSeries.setData(
      ohlcv
        .map((d, i) =>
          histogram[i] !== null
            ? {
                time: d.date,
                value: histogram[i] as number,
                color:
                  (histogram[i] as number) >= 0 ? "#ef444490" : "#3b82f690",
              }
            : null
        )
        .filter(Boolean) as { time: string; value: number; color: string }[]
    );

    const macdSeries = chart.addSeries(LineSeries, {
      color: "#22d3ee",
      lineWidth: 2,
      title: "MACD",
    });
    macdSeries.setData(
      ohlcv
        .map((d, i) =>
          macdLine[i] !== null
            ? { time: d.date, value: macdLine[i] as number }
            : null
        )
        .filter(Boolean) as { time: string; value: number }[]
    );

    const sigSeries = chart.addSeries(LineSeries, {
      color: "#f97316",
      lineWidth: 2,
      title: "Signal",
    });
    sigSeries.setData(
      ohlcv
        .map((d, i) =>
          signalLine[i] !== null
            ? { time: d.date, value: signalLine[i] as number }
            : null
        )
        .filter(Boolean) as { time: string; value: number }[]
    );

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({
          width: containerRef.current.clientWidth,
          height: window.innerWidth < 640 ? 150 : 200,
        });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [ohlcv, macdLine, signalLine, histogram]);

  return (
    <div ref={containerRef} className="w-full rounded-lg overflow-hidden" />
  );
}

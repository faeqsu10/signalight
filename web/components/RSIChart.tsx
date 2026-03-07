"use client";

import { useEffect, useRef } from "react";
import { createChart, ColorType, LineSeries } from "lightweight-charts";
import { OHLCVData } from "@/lib/yahoo-finance";
import { useTheme } from "./ThemeProvider";

interface Props {
  ohlcv: OHLCVData[];
  rsiValues: (number | null)[];
}

export default function RSIChart({ ohlcv, rsiValues }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { theme } = useTheme();

  useEffect(() => {
    if (!containerRef.current || ohlcv.length === 0) return;

    const isDark = theme === "dark";

    const chart = createChart(containerRef.current, {
      layout: {
        background: {
          type: ColorType.Solid,
          color: isDark ? "#0f0f0f" : "#ffffff",
        },
        textColor: isDark ? "#d1d5db" : "#374151",
      },
      grid: {
        vertLines: { color: isDark ? "#1f2937" : "#e5e7eb" },
        horzLines: { color: isDark ? "#1f2937" : "#e5e7eb" },
      },
      width: containerRef.current.clientWidth,
      height: window.innerWidth < 640 ? 150 : 200,
      rightPriceScale: {
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
    });

    const rsiSeries = chart.addSeries(LineSeries, {
      color: "#22d3ee",
      lineWidth: 2,
      title: "RSI",
    });

    rsiSeries.setData(
      ohlcv
        .map((d, i) =>
          rsiValues[i] !== null
            ? { time: d.date, value: rsiValues[i] as number }
            : null
        )
        .filter(Boolean) as { time: string; value: number }[]
    );

    const dates = ohlcv
      .filter((_, i) => rsiValues[i] !== null)
      .map((d) => d.date);

    if (dates.length > 0) {
      const obSeries = chart.addSeries(LineSeries, {
        color: "#ef444480",
        lineWidth: 1,
        lineStyle: 2,
      });
      obSeries.setData(dates.map((d) => ({ time: d, value: 70 })));

      const osSeries = chart.addSeries(LineSeries, {
        color: "#3b82f680",
        lineWidth: 1,
        lineStyle: 2,
      });
      osSeries.setData(dates.map((d) => ({ time: d, value: 30 })));
    }

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
  }, [ohlcv, rsiValues, theme]);

  return (
    <div ref={containerRef} className="w-full rounded-lg overflow-hidden" />
  );
}

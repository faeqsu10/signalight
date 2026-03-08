interface SourceMetrics {
  success: number;
  failure: number;
}

const metrics: Record<string, SourceMetrics> = {};

export function recordSuccess(source: string): void {
  if (!metrics[source]) metrics[source] = { success: 0, failure: 0 };
  metrics[source].success++;
}

export function recordFailure(source: string): void {
  if (!metrics[source]) metrics[source] = { success: 0, failure: 0 };
  metrics[source].failure++;
}

export function getMetrics(): Record<string, SourceMetrics & { successRate: string }> {
  const result: Record<string, SourceMetrics & { successRate: string }> = {};
  for (const [source, m] of Object.entries(metrics)) {
    const total = m.success + m.failure;
    result[source] = {
      ...m,
      successRate: total > 0 ? ((m.success / total) * 100).toFixed(1) + "%" : "N/A",
    };
  }
  return result;
}

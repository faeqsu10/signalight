/**
 * API 요청/응답 시간 로깅 유틸리티
 */
export function logApiRequest(method: string, path: string, status: number, durationMs: number): void {
  console.log(`[API] ${method} ${path} → ${status} (${durationMs}ms)`);
}

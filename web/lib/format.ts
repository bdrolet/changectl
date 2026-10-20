export function relativeAge(iso: string, now = Date.now()): string {
  const seconds = Math.floor((now - Date.parse(iso)) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  return `${Math.floor(days / 7)}w`;
}

export function bytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function dateOnly(iso: string): string {
  return new Date(iso).toISOString().slice(0, 10);
}

export function timeUtc(iso: string): string {
  return `${new Date(iso).toISOString().slice(11, 16)} UTC`;
}

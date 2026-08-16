function sameLocalDate(left: Date, right: Date): boolean {
  return (
    left.getFullYear() === right.getFullYear() &&
    left.getMonth() === right.getMonth() &&
    left.getDate() === right.getDate()
  );
}

export function formatMessageTimestamp(value: string, reference = new Date()): string {
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return "Unknown time";
  if (sameLocalDate(timestamp, reference)) {
    return timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  return timestamp.toLocaleString([], {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

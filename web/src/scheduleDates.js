export function tripOccursOnDate(trip, dateKey) {
  const first = trip.start_date || String(trip.starts_at || '').slice(0, 10);
  const last = trip.end_date || String(trip.ends_at || '').slice(0, 10);
  return Boolean(first && last && first <= dateKey && dateKey <= last);
}

export function vietnamDateTime(day, time) {
  return `${day}T${time}:00+07:00`;
}

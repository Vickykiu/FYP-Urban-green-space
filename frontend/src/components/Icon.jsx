const paths = {
  grid: 'M3 3h6v6H3z M15 3h6v6h-6z M3 15h6v6H3z M15 15h6v6h-6z',
  map: 'm3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2z M9 3v16 M15 5v16',
  search: 'M21 21l-5-5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0',
  target: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M17 12a5 5 0 1 1-10 0 5 5 0 0 1 10 0 M12 11v2',
  chart: 'M4 13h3v8H4z M10 8h3v13h-3z M16 3h3v18h-3z',
  filter: 'M3 4h18l-7 8v7l-4 2v-9z',
  report: 'M6 2h8l4 4v16H6z M14 2v5h4 M9 12h6 M9 16h6',
  login: 'M14 3h7v18h-7 M3 12h12 M10 7l5 5-5 5',
  leaf: 'M20 3C8 1 2 7 5 15c5 7 15 2 15-12z M4 21 15 9',
  pin: 'M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0 M14 10a2 2 0 1 1-4 0 2 2 0 0 1 4 0',
  refresh: 'M20 7a9 9 0 1 0 1 9 M20 2v6h-6',
  close: 'M6 6l12 12 M18 6 6 18', menu: 'M3 6h18 M3 12h18 M3 18h18',
  info: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M12 11v6 M12 7v1',
};
export default function Icon({ name, size = 18, ...props }) {
  if (name === 'tree') return <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" {...props}>
    <path fill="#86cd91" d="M10 3a4 4 0 0 1 7 3 4 4 0 0 1 1 8 4 4 0 0 1-6 2 4 4 0 0 1-6-2 4 4 0 0 1-1-7 4 4 0 0 1 5-4Z" />
    <path d="M12 10v11m0-7-3-3m3 5 4-4" fill="none" stroke="#967749" strokeWidth="1.4" strokeLinecap="round" />
  </svg>;
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
    <path d={paths[name] || paths.map} />
  </svg>;
}

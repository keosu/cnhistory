// Local SVG controls share one view box and stroke style.
const shapes = {
  gem:'<path d="m3 8 4-5h10l4 5-9 13ZM3 8h18M7 3l5 18 5-18"/>',
  flame:'<path d="M12 3c1 5-4 6-4 10 0 2 1 3 2 3-1-4 4-4 4-7 4 4 6 7 3 10-3 4-11 2-11-3 0-5 4-6 6-13Z"/>',
  spark:'<path d="m12 2 2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5ZM20 2v4m-2-2h4"/>',
  play:'<path d="m9 5 11 7-11 7Z" fill="currentColor" stroke="none"/>',
  pause:'<rect x="6" y="5" width="4" height="14" rx="1" fill="currentColor" stroke="none"/><rect x="14" y="5" width="4" height="14" rx="1" fill="currentColor" stroke="none"/>',
  previous:'<path d="M5 5v14M19 5l-10 7 10 7Z"/>',
  next:'<path d="M19 5v14M5 5l10 7-10 7Z"/>',
  sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
  moon:'<path d="M20.5 13A8.5 8.5 0 0 1 11 3.5 8.5 8.5 0 1 0 20.5 13Z"/>',
  paper:'<path d="M6 3h10a2 2 0 0 1 2 2v13M6 3a2 2 0 0 0-2 2v13a3 3 0 0 0 3 3h11a2 2 0 0 0 2-2v-2H8v2M8 7h6m-6 4h6"/>',
  fullscreen:'<path d="M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5"/>',
  minimize:'<path d="M3 8h5V3m13 5h-5V3M8 21v-5H3m13 5v-5h5"/>',
  panel:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16m3-11v6"/>',
  panelClose:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16m-6-11 3 3-3 3"/>',
  close:'<path d="m6 6 12 12M18 6 6 18"/>',
  download:'<path d="M12 3v12m-5-5 5 5 5-5M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/>',
  layers:'<path d="m12 3 10 6-10 6L2 9Zm-10 11 10 6 10-6M2 18l10 6 10-6" transform="translate(0 -1) scale(1 .92)"/>',
  image:'<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="1.5"/><path d="m21 15-5-5L6 21"/>',
  map:'<path d="m3 5 6-2 6 2 6-2v16l-6 2-6-2-6 2Zm6-2v16m6-14v16"/>',
  labels:'<path d="M4 5h16M12 5v15M8 20h8M4 5v4m16-4v4"/>',
  locate:'<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="2"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',
  minus:'<path d="M5 12h14"/>',
  search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  crown:'<path d="m3 6 4 4 5-7 5 7 4-4-2 13H5ZM5 22h14" transform="translate(0 -1)"/>',
  history:'<path d="M3 10a9 9 0 1 1 1.5 8M3 4v6h6m3-3v5l4 2"/>',
  database:'<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 4 16 4 16 0V5M4 12c0 4 16 4 16 0"/>',
  arrow:'<path d="M5 12h14m-6-6 6 6-6 6"/>',
  calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 11h18m-13 4h2m4 0h2"/>',
  speed:'<path d="M4 19a9 9 0 1 1 16 0M12 12l5-5M5 12h1m6-7v1m6 6h1"/><circle cx="12" cy="12" r="1.5"/>',
};

export function icon(name) {
  return `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${shapes[name] || shapes.map}</svg>`;
}

export function setIcon(element, name) {
  element.innerHTML=icon(name);
  element.dataset.icon=name;
}

export function hydrateIcons(root=document) {
  root.querySelectorAll('[data-icon]').forEach(element=>setIcon(element,element.dataset.icon));
}

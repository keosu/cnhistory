import {TimelineTransport} from './playback.js';
import {icon, setIcon, hydrateIcons} from './icons.js';
import {layoutLandmarks} from './timeline-layout.js';

const root = new URL('../', import.meta.url);
const $ = (selector) => document.querySelector(selector);
const state = {year:-2000, tab:'polities', mode:'vector', search:'', selected:null, active:[], currentFeatures:[], renderId:0};
const cache = new Map();
let data, map, territoryLayer, labelLayer, basemapLayer, riverLayer, fillLayer, borderLayer, transport;
let palette = {};
const narrowScreen=matchMedia('(max-width:760px)');
const themeIcons={light:'sun',dark:'moon',paper:'paper',vivid:'gem',vermilion:'flame',neon:'spark'};
const kinds = {polity_start:'政权',polity_change:'政权变更',polity_end:'政权',ruler_start:'任期开始',ruler_end:'任期结束',era_start:'年号',territory_change:'疆域变化'};
const escapeHTML = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const nameOf = (record) => record?.names?.zh || record?.names?.en || record?.names?.ja || '未命名';
const yearText = (year, full=false) => year < 0 ? `公元前 ${-year}${full?' 年':''}` : `公元 ${year}${full?' 年':''}`;
const compactYear = (year) => year < 0 ? `前${-year}` : String(year);
const intervalText = (record) => `${compactYear(record.start_year)} — ${record.end_year === 9999 ? '' : compactYear(record.end_year)}`;
const activeAt = (record, year) => record.start_year <= year && year < record.end_year;
const inFocus = ([x,y]) => x>=data.metadata.focus_bbox[0] && x<=data.metadata.focus_bbox[2] && y>=data.metadata.focus_bbox[1] && y<=data.metadata.focus_bbox[3];

async function getJSON(path) {
  if (!cache.has(path)) {
    const promise = fetch(new URL(path, root)).then(response => {
      if (!response.ok) throw new Error(`${path}：HTTP ${response.status}`);
      return response.json();
    }).catch(error => {cache.delete(path);throw error;});
    cache.set(path,promise);
    if(cache.size>180) cache.delete(cache.keys().next().value);
  }
  return cache.get(path);
}

function status(text, error=false) {$('#map-status').textContent=text;$('#map-status').hidden=!text;$('#map-status').classList.toggle('error',error);}

function preference(key, fallback) {
  try{return localStorage.getItem(key) ?? fallback;}catch{return fallback;}
}

function remember(key, value) {
  try{localStorage.setItem(key,String(value));}catch{}
}

function applyTheme(value) {
  const theme=Object.hasOwn(themeIcons,value)?value:'light';
  document.documentElement.dataset.theme=theme;
  setIcon($('#theme-toggle'),themeIcons[theme]);
  document.querySelectorAll('[data-theme-option]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.themeOption===theme)));
  remember('atlas-theme',theme);
  const css=getComputedStyle(document.documentElement);
  const color=key=>css.getPropertyValue(key).trim();
  palette={land:color('--map-land'),coast:color('--map-coast'),river:color('--map-river'),border:color('--map-border'),saturation:color('--territory-saturation'),lightness:color('--territory-lightness'),opacity:Number(color('--territory-opacity')),hueShift:Number(color('--territory-hue-shift')),borderWeight:Number(color('--map-border-weight')),borderOpacity:Number(color('--map-border-opacity'))};
  $('meta[name="theme-color"]').content=color('--app');
  basemapLayer?.setStyle({fillColor:palette.land,color:palette.coast});
  riverLayer?.setStyle({color:palette.river});
  fillLayer?.setStyle(feature=>({fillColor:sourceColor(feature.properties.source_color),fillOpacity:palette.opacity}));
  borderLayer?.setStyle({color:palette.border,weight:palette.borderWeight,opacity:palette.borderOpacity});
}

function openRecords(open, persist=true) {
  document.body.classList.toggle('records-open',open);
  const button=$('#toggle-records');
  button.setAttribute('aria-expanded',String(open));
  button.setAttribute('aria-label',open?'收起历史记录':'展开历史记录');
  button.title=button.getAttribute('aria-label');
  setIcon(button,open?'panelClose':'panel');
  if(persist)remember(narrowScreen.matches?'atlas-panel-mobile':'atlas-panel-desktop',open);
}

function restoreRecords() {
  openRecords(preference(narrowScreen.matches?'atlas-panel-mobile':'atlas-panel-desktop',String(!narrowScreen.matches))==='true',false);
}

function focusBounds() {
  const [w,s,e,n]=data.metadata.focus_bbox;
  return [[s,w],[n,e]];
}

function setupMap() {
  // Geographic CRS keeps the original equirectangular images correctly aligned.
  map=L.map('map',{crs:L.CRS.EPSG4326,zoomControl:false,attributionControl:false,minZoom:1,maxZoom:7,zoomSnap:.1,zoomDelta:.5,
    maxBounds:[[-75,-180],[90,240]],maxBoundsViscosity:.6,preferCanvas:true});
  L.control.scale({imperial:false,position:'bottomright',maxWidth:100}).addTo(map);
  map.createPane('land');map.getPane('land').style.zIndex=200;
  map.createPane('rivers');map.getPane('rivers').style.zIndex=230;
  map.createPane('territory');map.getPane('territory').style.zIndex=300;
  map.createPane('names');map.getPane('names').style.zIndex=450;
  basemapLayer=L.geoJSON(data.land,{pane:'land',interactive:false,style:{fillColor:palette.land,fillOpacity:1,color:palette.coast,weight:.65}}).addTo(map);
  riverLayer=L.geoJSON(data.rivers,{pane:'rivers',interactive:false,style:{color:palette.river,weight:.7,opacity:.25}}).addTo(map);
  territoryLayer=L.layerGroup().addTo(map);labelLayer=L.layerGroup().addTo(map);
  map.fitBounds(focusBounds(),{padding:[20,20]});
  map.on('zoomend',renderLabels);
  let resizeFrame;
  new ResizeObserver(()=>{
    cancelAnimationFrame(resizeFrame);
    resizeFrame=requestAnimationFrame(()=>{map.invalidateSize({pan:true,animate:false});renderLabels();});
  }).observe($('#map'));
}

function sourceColor(hex) {
  // Theme colors only affect the display; exports keep the source colors.
  const r=parseInt(hex.slice(1,3),16)/255,g=parseInt(hex.slice(3,5),16)/255,b=parseInt(hex.slice(5,7),16)/255;
  const max=Math.max(r,g,b),min=Math.min(r,g,b),d=max-min;
  let h=0;
  if(d) h=(max===r?(g-b)/d+(g<b?6:0):max===g?(b-r)/d+2:(r-g)/d+4)*60;
  return `hsl(${h+palette.hueShift}, ${palette.saturation}, ${palette.lightness})`;
}

function activePolities() {
  return data.entities.filter(e=>activeAt(e,state.year)).flatMap(entity=>{
    const period=entity.periods.find(p=>activeAt(p,state.year));
    return period && !period.sovereign_entity_id ? [{entity,period,rulers:(data.rulersByEntity.get(entity.id)||[]).filter(r=>activeAt(r,state.year))}] : [];
  }).sort((a,b)=>(a.period.display_level??0)-(b.period.display_level??0)||nameOf(a.period).localeCompare(nameOf(b.period),'zh'));
}

function matches(record) {
  if(!state.search) return true;
  return [nameOf(record.period),...Object.values(record.period.names||{}),...record.rulers.map(nameOf)].join(' ').toLowerCase().includes(state.search);
}

function renderLabels() {
  if(!labelLayer) return;
  labelLayer.clearLayers();
  if($('#show-labels').getAttribute('aria-pressed')!=='true') return;
  const occupied=[];
  for(const item of state.active) {
    const p=item.period;
    if(!p.label_position || !inFocus(p.label_position) || !matches(item)) continue;
    const [lon,lat]=p.label_position;
    const name=nameOf(p);
    const size=(p.display_level??0)>0?'small':'';
    const pixel=map.latLngToLayerPoint([lat,lon]);
    const width=Math.min(name.length*13,180);
    if(occupied.some(o=>Math.abs(o.x-pixel.x)<(o.w+width)/2+5&&Math.abs(o.y-pixel.y)<22)) continue;
    occupied.push({x:pixel.x,y:pixel.y,w:width});
    const marker=L.marker([lat,lon],{pane:'names',icon:L.divIcon({className:'polity-label',html:`<span class="${size}">${escapeHTML(name)}</span>`,iconSize:[0,0],iconAnchor:[0,0]}),title:name,keyboard:true});
    marker.bindTooltip(`<strong>${escapeHTML(name)}</strong><br>${escapeHTML(intervalText(p))}${item.rulers.length?`<br>${escapeHTML(item.rulers.slice(0,2).map(nameOf).join(' · '))}`:''}`,{direction:'top'});
    marker.on('click',()=>showDetail(item.entity.id));
    marker.addTo(labelLayer);
  }
}

function renderPolities() {
  const visible=state.active.filter(matches);
  $('#record-count').textContent=`${visible.length}`;
  $('#polity-list').innerHTML=visible.length ? visible.map(({entity,period,rulers})=>`<button class="polity-card" data-entity="${entity.id}"><span class="arrow">${icon('arrow')}</span><h3>${escapeHTML(nameOf(period))}</h3><span class="years">${escapeHTML(intervalText(period))}</span><p>${escapeHTML(rulers.slice(0,2).map(r=>`${r.role?.zh||r.role?.en||''} ${nameOf(r)}`).join(' · ') || period.names?.en || '')}</p></button>`).join('') : '<p class="empty">暂无匹配记录</p>';
  if(state.selected) showDetail(state.selected,false);
}

function renderEvents() {
  const filter=$('#event-filter').value;
  const events=data.events.filter(e=>(filter==='all'||e.kind.startsWith(filter))&&(!state.search||e.title.toLowerCase().includes(state.search)))
    .sort((a,b)=>Math.abs(a.year-state.year)-Math.abs(b.year-state.year)||a.year-b.year).slice(0,80);
  $('#event-list').innerHTML=events.length ? events.map(e=>`<button class="event-card" data-year="${e.year}"><span class="date">${compactYear(e.year)}</span><span>${escapeHTML(e.kind==='territory_change'?'疆域变化':e.title.replace('记录开始','出现').replace('记录结束','结束'))}<span class="kind">${kinds[e.kind]||escapeHTML(e.kind)}</span></span></button>`).join('') : '<p class="empty">暂无匹配记录</p>';
}

function showDetail(entityId, pan=true) {
  const record=state.active.find(r=>r.entity.id===entityId);
  if(!record){state.selected=null;$('#detail').hidden=true;return;}
  state.selected=entityId;
  const {period,rulers}=record;
  $('#detail').innerHTML=`<button class="close icon-button" aria-label="关闭详情" title="关闭详情">${icon('close')}</button><h3>${escapeHTML(nameOf(period))}</h3><p>${escapeHTML(period.names?.en||'')}</p><p>${escapeHTML(intervalText(period))}</p>${rulers.length?`<ul>${rulers.map(r=>`<li>${escapeHTML(r.role?.zh||r.role?.en||'')} · ${escapeHTML(nameOf(r))}<br><span class="years">${escapeHTML(intervalText(r))}</span></li>`).join('')}</ul>`:''}`;
  $('#detail').hidden=false;
  if(pan)openRecords(true);
  if(pan&&period.label_position) map.panTo([period.label_position[1],period.label_position[0]]);
}

function snapshotForYear(tile,year) {
  let lo=0,hi=tile.snapshots.length;
  while(lo<hi){const mid=(lo+hi)>>1;if(tile.snapshots[mid].start_year<=year)lo=mid+1;else hi=mid;}
  const result=tile.snapshots[lo-1];
  return result&&year<result.end_year ? result : null;
}

async function vectorFeatures(year) {
  const snapshot=snapshotForYear({snapshots:data.timeline},year);
  return (await getJSON(snapshot.path)).features;
}

async function renderTerritories() {
  const token=++state.renderId,year=state.year,mode=state.mode;
  territoryLayer.clearLayers();state.currentFeatures=[];
  $('#map').dataset.renderState='loading';
  status('加载中…');
  try {
    if(mode==='vector') {
      const snapshot=snapshotForYear({snapshots:data.timeline},year);
      const [collection,boundaries]=await Promise.all([getJSON(snapshot.path),getJSON(snapshot.boundary_path)]);
      const features=collection.features;
      if(token!==state.renderId) return;
      state.currentFeatures=features;
      fillLayer=L.geoJSON(collection,{pane:'territory',interactive:false,style:feature=>({fillColor:sourceColor(feature.properties.source_color),fillOpacity:palette.opacity,stroke:false})}).addTo(territoryLayer);
      borderLayer=L.geoJSON(boundaries,{pane:'territory',interactive:false,style:{color:palette.border,opacity:palette.borderOpacity,weight:palette.borderWeight,fill:false}}).addTo(territoryLayer);
    } else if(mode==='raster') {
      const snapshots=data.tiles.map(tile=>({tile,snapshot:snapshotForYear(tile,year)})).filter(s=>s.snapshot);
      await Promise.all(snapshots.map(({tile,snapshot})=>new Promise((resolve,reject)=>{
        const [w,s,e,n]=tile.bbox;
        const overlay=L.imageOverlay(new URL(snapshot.path,root).href,[[s,w],[n,e]],{pane:'territory',opacity:.55,interactive:false});
        overlay.once('load',resolve);overlay.once('error',()=>reject(new Error(`图像读取失败：${snapshot.path}`)));
        overlay.addTo(territoryLayer);
      })));
      if(token!==state.renderId) return;
    }
    if(token!==state.renderId) return;
    $('#map').dataset.renderState='ready';$('#map').dataset.year=String(year);$('#map').dataset.mode=mode;
    status('');
  }catch(error){if(token===state.renderId){$('#map').dataset.renderState='error';status('地图加载失败，请刷新重试',true);console.error(error);}}
}

function renderNavigation() {
  const periods=data.navigation.primary_periods;
  const nav=$('#dynasty-nav');
  nav.innerHTML='<svg class="landmark-lines" aria-hidden="true"></svg>'+periods.map(p=>`<button data-year="${p.jump_year}" data-period="${p.id}" title="${escapeHTML(p.name)} · ${escapeHTML(yearText(p.jump_year,true))}"><span>${escapeHTML(p.name)}</span><small>${compactYear(p.jump_year)}</small></button>`).join('');
  let lastWidth=0;
  const layout=()=>{
    const width=nav.clientWidth;
    if(!width)return;
    lastWidth=width;
    const buttons=[...nav.querySelectorAll('button')];
    const {markers}=layoutLandmarks(buttons.map(button=>({year:Number(button.dataset.year),width:button.offsetWidth,id:button.dataset.period})),width,data.navigation.min_year,data.navigation.max_year,narrowScreen.matches?2:6);
    const height=narrowScreen.matches?42:54;
    nav.style.height=`${height}px`;
    const lines=nav.querySelector('svg');
    lines.setAttribute('viewBox',`0 0 ${width} ${height}`);
    lines.innerHTML=markers.map((marker,i)=>{
      const top=16;
      const button=buttons[i];
      button.style.left=`${marker.left}px`;button.style.top=`${top}px`;
      button.dataset.anchor=String(marker.x);
      return `<g data-period="${marker.id}"><path d="M${marker.x} 0V4L${marker.left+marker.width/2} ${top-3}"/><circle cx="${marker.x}" cy="0" r="2"/></g>`;
    }).join('');
    updateNavigation(state.year);
  };
  layout();
  new ResizeObserver(()=>{if(nav.clientWidth!==lastWidth)layout();}).observe(nav);
  document.fonts.ready.then(layout);
}

function updateNavigation(year) {
  const periods=data.navigation.primary_periods;
  document.querySelectorAll('#dynasty-nav [data-period]').forEach(button=>{
    const period=periods.find(p=>p.id===button.dataset.period);
    const active=activeAt(period,year);button.classList.toggle('selected',active);
    if(button.tagName==='BUTTON')button.setAttribute('aria-pressed',String(active));
  });
}

function setYear(value) {
  let year=Number(value);
  if(!Number.isFinite(year)) return;
  year=Math.min(data.navigation.max_year,Math.max(data.navigation.min_year,Math.trunc(year)));
  if(year===0) year=state.year<0?1:-1;
  state.year=year;
  $('#year-slider').value=year;$('#year-input').value=year;
  $('#year-slider').setAttribute('aria-valuetext',yearText(year,true));
  $('#year-slider').style.setProperty('--progress',`${(year-data.navigation.min_year)/(data.navigation.max_year-data.navigation.min_year)*100}%`);
  $('#map-year').textContent=yearText(year,true);
  const eras=data.eras.filter(e=>e.country==='cn'&&activeAt(e,year));
  $('#era-line').textContent=eras.length?eras.map(e=>`${e.name.trim()} ${year-e.start_year+(e.start_year<0&&year>0?0:1)}年`).join(' · '):'';
  updateNavigation(year);
  state.active=activePolities();
  renderPolities();renderEvents();renderLabels();renderTerritories();
  history.replaceState(null,'',`#year=${year}`);
}

function stepYear(direction) {
  let next=state.year+direction;
  if(next===0)next=direction;
  if(next<data.navigation.min_year||next>data.navigation.max_year)return false;
  setYear(next);
  return true;
}
function stop(){transport?.stop();}

function wireTransport() {
  transport=new TimelineTransport({step:stepYear,onChange:playing=>{
    setIcon($('#play'),playing?'pause':'play');$('#play').setAttribute('aria-pressed',String(playing));
    $('#play').setAttribute('aria-label',playing?'暂停时间线':'播放时间线');
    $('#play').title=$('#play').getAttribute('aria-label');
  }});
  transport.setSpeed(preference('atlas-speed',1));
  $('#playback-speed').value=String(transport.speed);
  $('#playback-speed').addEventListener('change',event=>{transport.setSpeed(event.target.value);remember('atlas-speed',transport.speed);});
  $('#play').addEventListener('click',()=>transport.playing?transport.pause():transport.play());
  let heldKey=null,heldPointer=null;
  for(const [selector,direction] of [['#previous',-1],['#next',1]]) {
    const button=$(selector);
    button.addEventListener('pointerdown',event=>{
      if(event.button!==0)return;
      event.preventDefault();heldPointer=event.pointerId;button.setPointerCapture(event.pointerId);
      button.focus({preventScroll:true});transport.hold(direction);
    });
    const release=event=>{if(heldPointer===event.pointerId){heldPointer=null;transport.release();}};
    button.addEventListener('pointerup',release);button.addEventListener('pointercancel',release);button.addEventListener('lostpointercapture',release);
    button.addEventListener('contextmenu',event=>event.preventDefault());
    button.addEventListener('click',event=>{if(event.detail===0){stop();stepYear(direction);}});
  }
  const editable=target=>target instanceof Element&&target.closest('input,select,textarea,[contenteditable="true"],[contenteditable=""]');
  document.addEventListener('keydown',event=>{
    if(!['ArrowLeft','ArrowRight'].includes(event.key)||event.altKey||event.ctrlKey||event.metaKey||editable(event.target))return;
    event.preventDefault();event.stopPropagation();
    if(event.repeat&&heldKey===event.key)return;
    heldKey=event.key;transport.hold(event.key==='ArrowRight'?1:-1);
  },true);
  document.addEventListener('keyup',event=>{
    if(event.key!==heldKey)return;
    event.preventDefault();event.stopPropagation();heldKey=null;transport.release();
  },true);
  const cancelInteraction=()=>{heldKey=null;heldPointer=null;stop();};
  window.addEventListener('blur',cancelInteraction);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)cancelInteraction();});
}

function downloadJSON(name,value) {
  const url=URL.createObjectURL(new Blob([JSON.stringify(value)],{type:'application/geo+json'}));
  const link=document.createElement('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}

function wireIconMenus() {
  const pairs=[['#theme-toggle','#theme-menu'],['#layer-toggle','#layer-menu']];
  const closeMenus=()=>pairs.forEach(([trigger,menu])=>{$(menu).hidden=true;$(trigger).setAttribute('aria-expanded','false');});
  for(const [trigger,menu] of pairs) {
    $(trigger).addEventListener('click',()=>{
      const open=$(menu).hidden;closeMenus();
      $(menu).hidden=!open;$(trigger).setAttribute('aria-expanded',String(open));
      if(open)$(menu).querySelector('[aria-pressed="true"]').focus({preventScroll:true});
    });
  }
  document.addEventListener('click',event=>{
    if(!event.target.closest('.popover-wrap'))closeMenus();
    const theme=event.target.closest('[data-theme-option]');
    const layer=event.target.closest('[data-layer]');
    if(theme){applyTheme(theme.dataset.themeOption);closeMenus();$('#theme-toggle').focus({preventScroll:true});}
    if(layer){
      state.mode=layer.dataset.layer;
      document.querySelectorAll('[data-layer]').forEach(button=>button.setAttribute('aria-pressed',String(button===layer)));
      setIcon($('#layer-toggle'),{vector:'layers',raster:'image',none:'map'}[state.mode]);
      renderTerritories();closeMenus();$('#layer-toggle').focus({preventScroll:true});
    }
  });
  document.addEventListener('keydown',event=>{
    if(event.key!=='Escape')return;
    const open=pairs.find(([,menu])=>!$(menu).hidden);
    if(open){event.preventDefault();closeMenus();$(open[0]).focus({preventScroll:true});}
  });
  document.addEventListener('focusin',event=>{
    if(!event.target.closest('.popover-wrap'))closeMenus();
  });
}

function wireFullscreen() {
  const button=$('#toggle-fullscreen'),element=document.documentElement;
  const enter=element.requestFullscreen || element.webkitRequestFullscreen;
  const leave=document.exitFullscreen || document.webkitExitFullscreen;
  const current=()=>document.fullscreenElement || document.webkitFullscreenElement;
  button.hidden=!enter || !leave;
  const sync=()=>{
    const active=Boolean(current());
    setIcon(button,active?'minimize':'fullscreen');
    button.setAttribute('aria-pressed',String(active));
    button.setAttribute('aria-label',active?'退出全屏':'进入全屏');button.title=button.getAttribute('aria-label');
  };
  button.addEventListener('click',async()=>{
    try{if(current())await leave.call(document);else await enter.call(element);sync();}
    catch{status('无法进入全屏',true);}
  });
  document.addEventListener('fullscreenchange',sync);
  document.addEventListener('webkitfullscreenchange',sync);
  sync();
}

function wireControls() {
  let debounce;
  window.addEventListener('hashchange',()=>{
    const year=new URLSearchParams(location.hash.slice(1)).get('year');
    if(year!==null&&year.trim()!==''&&Number.isFinite(Number(year))){stop();setYear(year);}
  });
  $('#year-slider').addEventListener('input',e=>{stop();clearTimeout(debounce);const value=e.target.value;debounce=setTimeout(()=>setYear(value),60);});
  $('#year-form').addEventListener('submit',e=>{e.preventDefault();stop();setYear($('#year-input').value);});
  document.addEventListener('click',e=>{
    const yearButton=e.target.closest('button[data-year]');if(yearButton){stop();setYear(yearButton.dataset.year);}
    const entityButton=e.target.closest('button[data-entity]');if(entityButton)showDetail(entityButton.dataset.entity);
    if(e.target.closest('.detail .close')){state.selected=null;$('#detail').hidden=true;}
    const tab=e.target.closest('[data-tab]');if(tab){state.tab=tab.dataset.tab;document.querySelectorAll('[data-tab]').forEach(b=>{b.classList.toggle('active',b===tab);b.setAttribute('aria-selected',String(b===tab));});document.querySelectorAll('.panel').forEach(p=>p.hidden=p.id!==`${state.tab}-panel`);}
  });
  wireTransport();
  wireIconMenus();wireFullscreen();
  $('#search').addEventListener('input',e=>{state.search=e.target.value.trim().toLowerCase();renderPolities();renderEvents();renderLabels();});
  $('#show-labels').addEventListener('click',event=>{const button=event.currentTarget;button.setAttribute('aria-pressed',String(button.getAttribute('aria-pressed')!=='true'));renderLabels();});
  $('#reset-view').addEventListener('click',()=>map.fitBounds(focusBounds(),{padding:[20,20]}));
  $('#zoom-in').addEventListener('click',()=>map.zoomIn());
  $('#zoom-out').addEventListener('click',()=>map.zoomOut());
  $('#event-filter').addEventListener('change',renderEvents);
  $('#toggle-records').addEventListener('click',()=>openRecords(!document.body.classList.contains('records-open')));
  $('#close-records').addEventListener('click',()=>{openRecords(false);$('#toggle-records').focus({preventScroll:true});});
  narrowScreen.addEventListener('change',restoreRecords);
  $('#download-snapshot').addEventListener('click',async e=>{
    const button=e.currentTarget,year=state.year;button.disabled=true;
    try{downloadJSON(`territories-${year}.geojson`,{type:'FeatureCollection',year,features:await vectorFeatures(year)});}catch(error){status(`导出失败：${error.message}`,true);}finally{button.disabled=false;}
  });
  $('#download-labels').addEventListener('click',()=>downloadJSON(`polity-labels-${state.year}.geojson`,{type:'FeatureCollection',year:state.year,features:state.active.filter(r=>r.period.label_position).map(({period})=>({type:'Feature',id:period.id,geometry:{type:'Point',coordinates:period.label_position},properties:{...period,position_kind:'source_label_anchor_not_capital'}}))}));
}

async function init() {
  try {
    hydrateIcons();restoreRecords();
    applyTheme(preference('atlas-theme','light'));
    const [metadata,entities,rulers,eras,allEvents,tiles,land,rivers,timeline,navigation]=await Promise.all(['data/metadata.json','data/focus/entities.json','data/focus/rulers.json','data/focus/eras.json','data/focus/events.json','data/focus/territory-index.json','data/basemap/land.geojson','data/basemap/rivers.geojson','data/focus/territory-timeline.curated.json','data/navigation.json'].map(getJSON));
    const seenTerritoryYears=new Set();
    const events=allEvents.filter(e=>{
      if(e.year<navigation.min_year||e.year>navigation.max_year||e.year===0)return false;
      if(e.kind==='territory_change'){if(seenTerritoryYears.has(e.year))return false;seenTerritoryYears.add(e.year);}
      return true;
    });
    data={metadata,entities,rulers,eras,events,tiles,land,rivers,timeline,navigation,rulersByEntity:new Map()};
    for(const ruler of rulers){if(!data.rulersByEntity.has(ruler.entity_id))data.rulersByEntity.set(ruler.entity_id,[]);data.rulersByEntity.get(ruler.entity_id).push(ruler);}
    $('#dataset-counts').innerHTML=`<div><strong>${metadata.counts.focus_entities}</strong><span>政权</span></div><div><strong>${timeline.length.toLocaleString()}</strong><span>疆域版本</span></div><div><strong>${metadata.counts.focus_rulers.toLocaleString()}</strong><span>人物任期</span></div><div><strong>${metadata.counts.focus_events.toLocaleString()}</strong><span>变化记录</span></div>`;
    setupMap();renderNavigation();wireControls();
    const initial=new URLSearchParams(location.hash.slice(1)).get('year');
    setYear(initial!==null&&initial.trim()!==''&&Number.isFinite(Number(initial))?initial:navigation.default_year);
  }catch(error){status('地图加载失败，请刷新重试',true);console.error(error);}
}
init();

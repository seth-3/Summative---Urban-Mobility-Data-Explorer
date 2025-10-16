async function fetchJSON(url){const r=await fetch(url);return r.json();}
function fmt(n, d=0){return Number(n||0).toFixed(d)}
function pad(n){return n<10?`0${n}`:`${n}`}
function fmtDate(dt){
  return `${dt.getFullYear()}-${pad(dt.getMonth()+1)}-${pad(dt.getDate())} ${pad(dt.getHours())}:${pad(dt.getMinutes())}:${pad(dt.getSeconds())}`;
}

function getCustomFilters(){
  const ids=['min_distance','max_distance','min_speed','max_speed','min_fare','max_fare','cell','hod_start','hod_end'];
  const o={};
  ids.forEach(id=>{const el=document.getElementById(id); if(!el) return; const v=el.value; if(v!==''&&v!=null) o[id]=v;});
  return o;
}

async function load(opts={}){
  const params = new URLSearchParams();
  if(opts.start) params.set('start', opts.start);
  if(opts.end) params.set('end', opts.end);
  const cf = getCustomFilters();
  Object.entries(cf).forEach(([k,v])=>params.set(k,v));
  const summaryUrl = `/api/summary${params.toString()?`?${params.toString()}`:''}`;

  const summary = await fetchJSON(summaryUrl);
  const noDataEl = document.getElementById('no-data');
  if(!summary || !summary.trips){
    noDataEl.hidden = false;
  } else {
    noDataEl.hidden = true;
  }
  document.getElementById('avg-trip').textContent = `${summary.trips||0} trips`;
  document.getElementById('avg-speed').textContent = `${fmt(summary.avg_speed,1)} km/h`;
  document.getElementById('avg-fpk').textContent = `$${fmt(summary.avg_fpk,2)}/km`;
  const rangeNote = document.getElementById('range-note');
  if(summary && (opts.start || opts.end)){
    rangeNote.textContent = `${opts.start||''} → ${opts.end||''}`;
  } else if(summary && summary.min_ts && summary.max_ts) {
    rangeNote.textContent = `${summary.min_ts} → ${summary.max_ts}`;
  } else {
    rangeNote.textContent = '';
  }

  const monthsUrl = `/api/monthly_counts${params.toString()?`?${params.toString()}`:''}`;
  const months = await fetchJSON(monthsUrl);
  if(months && months.length){
    const barCanvas = document.getElementById('barChart');
    const labels = months.map(m=>m.month);
    const values = months.map(m=>m.count);
    const narrow = barCanvas.clientWidth < 420;
    const tooMany = labels.length > 10;
    const fs = narrow ? 0.9 : 1;
    if (narrow || tooMany){
      // Horizontal bars improve readability with many labels or narrow width
      drawBarsH('barChart', values, labels, { title: 'Monthly Trips', xLabel: 'Trips', yLabel: 'Month (YYYY-MM)', fontScale: fs });
    } else {
      drawBars('barChart', values, labels, { title: 'Monthly Trips', xLabel: 'Month (YYYY-MM)', yLabel: 'Trips', fontScale: fs });
    }
  } else {
    const c=document.getElementById('barChart'); const ctx=c.getContext('2d'); const w=c.clientWidth; const h=c.clientHeight||c.height; ctx.clearRect(0,0,w,h);
  }

  const cellsParams = new URLSearchParams(params);
  cellsParams.set('k','8');
  const cellsUrl = `/api/top_cells?${cellsParams.toString()}`;
  const cells = await fetchJSON(cellsUrl);
  const ul = document.getElementById('top-cells');
  ul.innerHTML = '';
  if(cells && cells.length){
    cells.forEach(c=>{const li=document.createElement('li');li.innerHTML=`<span>${c.cell}</span><b>${c.count}</b>`;ul.appendChild(li);});
  } else {
    const li=document.createElement('li'); li.className='muted'; li.textContent='No data for this range'; ul.appendChild(li);
  }

  // make a simple line chart from monthly totals as placeholder for average
  if(months && months.length){
    const lineCanvas = document.getElementById('lineChart');
    const fsLine = lineCanvas.clientWidth < 420 ? 0.9 : 1;
    drawLine('lineChart', months.map(m=>m.count), months.map(m=>m.month), { title: 'Trips Over Time', xLabel: 'Month (YYYY-MM)', yLabel: 'Trips', fontScale: fsLine });
  } else {
    const c=document.getElementById('lineChart'); const ctx=c.getContext('2d'); const w=c.clientWidth; const h=c.clientHeight||c.height; ctx.clearRect(0,0,w,h);
  }
}

function setupNav(){
  document.querySelectorAll('.rail-nav .btn').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      const target = document.querySelector(btn.getAttribute('data-target'));
      if(target) target.scrollIntoView({behavior:'smooth', block:'start'});
      document.querySelectorAll('.rail-nav .btn').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
    });
  });
}

let currentFilterBtn = null;
function setupFilters(){
  const applyDays = async (days)=>{
    if(!days){ await load({}); return; }
    // fetch global summary to get dataset max_ts for a stable reference point
    const base = await fetchJSON('/api/summary');
    const end = base && base.max_ts ? new Date(base.max_ts.replace(' ', 'T')) : new Date();
    const start = new Date(end.getTime() - Number(days)*24*60*60*1000);
    await load({ start: fmtDate(start), end: fmtDate(end) });
  };
  document.querySelectorAll('.rail-filters .btn').forEach(btn=>{
    btn.addEventListener('click', async ()=>{
      document.querySelectorAll('.rail-filters .btn').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      currentFilterBtn = btn;
      const days = btn.getAttribute('data-days');
      await applyDays(days);
    });
  });

  // custom filters apply/clear
  const applyBtn = document.getElementById('apply-custom');
  const clearBtn = document.getElementById('clear-custom');
  if(applyBtn){
    applyBtn.addEventListener('click', async ()=>{
      // reload with current date range context if any
      if(currentFilterBtn){
        const days=currentFilterBtn.getAttribute('data-days');
        if(days) return await (async()=>{const base=await fetchJSON('/api/summary'); const end=base&&base.max_ts?new Date(base.max_ts.replace(' ','T')):new Date(); const start=new Date(end.getTime()-Number(days)*24*60*60*1000); await load({start:fmtDate(start), end:fmtDate(end)});})();
      }
      await load({});
    });
  }
  if(clearBtn){
    clearBtn.addEventListener('click', async ()=>{
      ['min_distance','max_distance','min_speed','max_speed','min_fare','max_fare','cell','hod_start','hod_end'].forEach(id=>{const el=document.getElementById(id); if(el) el.value='';});
      if(currentFilterBtn){
        const days=currentFilterBtn.getAttribute('data-days');
        if(days) return await (async()=>{const base=await fetchJSON('/api/summary'); const end=base&&base.max_ts?new Date(base.max_ts.replace(' ','T')):new Date(); const start=new Date(end.getTime()-Number(days)*24*60*60*1000); await load({start:fmtDate(start), end:fmtDate(end)});})();
      }
      await load({});
    });
  }
}

window.addEventListener('DOMContentLoaded', async ()=>{
  setupNav();
  setupFilters();
  await load({});
});

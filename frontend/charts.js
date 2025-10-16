function drawLine(id, data, labels, opts={}){
  const c = document.getElementById(id); const ctx = c.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const cssW = Math.max(1, c.clientWidth);
  const cssH = (c.clientHeight && c.clientHeight > 0) ? c.clientHeight : Math.round(cssW * 0.6);
  c.width = Math.floor(cssW * dpr);
  c.height = Math.floor(cssH * dpr);
  const w = c.width; const h = c.height; ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,w,h);
  const max = Math.max(...data, 1);
  // layout paddings for axes and title
  const fs = (opts.fontScale||1);
  const padLeft = 40*fs; const padRight = 10*fs; const padTop = (opts.title ? 24 : 10)*fs; const padBottom = (28 + (opts.xLabel ? 12 : 0))*fs;
  const innerW = Math.max(1, w - padLeft - padRight);
  const innerH = Math.max(1, h - padTop - padBottom);
  const step = innerW/((data.length-1)||1);

  // title
  if (opts.title){ ctx.fillStyle='#e5e7eb'; ctx.font=`${12*fs}px sans-serif`; ctx.textAlign='center'; ctx.fillText(opts.title, w/2, 14*fs); }

  // axes labels
  if (opts.yLabel){ ctx.save(); ctx.fillStyle='#9ca3af'; ctx.font=`${11*fs}px sans-serif`; ctx.translate(12*fs, padTop + innerH/2); ctx.rotate(-Math.PI/2); ctx.textAlign='center'; ctx.fillText(opts.yLabel, 0, 0); ctx.restore(); }
  if (opts.xLabel){ ctx.fillStyle='#9ca3af'; ctx.font=`${11*fs}px sans-serif`; ctx.textAlign='center'; ctx.fillText(opts.xLabel, padLeft + innerW/2, padTop + innerH + 22*fs); }

  // y axis line
  ctx.strokeStyle='#9ca3af'; ctx.lineWidth=1; ctx.beginPath(); ctx.moveTo(padLeft, padTop); ctx.lineTo(padLeft, padTop+innerH); ctx.stroke();

  // line series
  ctx.strokeStyle='rgba(255,255,255,.9)'; ctx.lineWidth=2*fs; ctx.beginPath();
  const points = data.map((v,i)=>({x: padLeft + i*step, y: padTop + innerH - (v/max)*innerH}));
  points.forEach((p,i)=>{ if(i) ctx.lineTo(p.x,p.y); else ctx.moveTo(p.x,p.y); });
  ctx.stroke();
  // area fill for readability
  if (opts.area !== false){
    ctx.save(); ctx.globalAlpha = 0.15; ctx.fillStyle = '#60a5fa';
    ctx.beginPath(); ctx.moveTo(points[0]?.x||padLeft, padTop+innerH);
    points.forEach((p)=>ctx.lineTo(p.x,p.y));
    ctx.lineTo(points[points.length-1]?.x||padLeft, padTop+innerH); ctx.closePath(); ctx.fill(); ctx.restore();
  }

  // x labels (skip to avoid overlap)
  if(labels&&labels.length){
    const maxLabels=8; const skip=Math.max(1, Math.ceil(labels.length/maxLabels));
    ctx.fillStyle='rgba(255,255,255,.9)'; ctx.font=`${10*fs}px sans-serif`; ctx.textAlign='left';
    for(let i=0;i<labels.length;i+=skip){
      const x = padLeft + i*step; const y = padTop + innerH + 12*fs;
      ctx.save(); ctx.translate(x, y); ctx.rotate(-Math.PI/4); ctx.fillText(String(labels[i]), 0, 0); ctx.restore();
    }
  }
}
function drawBars(id, data, labels, opts={}){
  const c = document.getElementById(id); const ctx = c.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const cssW = Math.max(1, c.clientWidth);
  const cssH = (c.clientHeight && c.clientHeight > 0) ? c.clientHeight : Math.round(cssW * 0.6);
  c.width = Math.floor(cssW * dpr);
  c.height = Math.floor(cssH * dpr);
  const w = c.width; const h = c.height; ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,w,h);
  const max = Math.max(...data, 1);
  // layout paddings
  const fs = (opts.fontScale||1);
  const padLeft = 40*fs; const padRight = 10*fs; const padTop = (opts.title ? 24 : 10)*fs; const padBottom = (28 + (opts.xLabel ? 12 : 0))*fs;
  const innerW = Math.max(1, w - padLeft - padRight);
  const innerH = Math.max(1, h - padTop - padBottom);

  // title
  if (opts.title){ ctx.fillStyle='#111827'; ctx.font=`${12*fs}px sans-serif`; ctx.textAlign='center'; ctx.fillText(opts.title, w/2, 14*fs); }

  // axes labels
  if (opts.yLabel){ ctx.save(); ctx.fillStyle='#6b7280'; ctx.font=`${11*fs}px sans-serif`; ctx.translate(12*fs, padTop + innerH/2); ctx.rotate(-Math.PI/2); ctx.textAlign='center'; ctx.fillText(opts.yLabel, 0, 0); ctx.restore(); }
  if (opts.xLabel){ ctx.fillStyle='#6b7280'; ctx.font=`${11*fs}px sans-serif`; ctx.textAlign='center'; ctx.fillText(opts.xLabel, padLeft + innerW/2, padTop + innerH + 22*fs); }

  // y axis line
  ctx.strokeStyle='#9ca3af'; ctx.lineWidth=1; ctx.beginPath(); ctx.moveTo(padLeft, padTop); ctx.lineTo(padLeft, padTop+innerH); ctx.stroke();

  // bars with configurable spacing (higher spacing => more gap)
  const spacing = (opts.spacing || 1.8);
  const bw=innerW/((data.length*spacing)||1);
  const maxLabels=10; const skip=Math.max(1, Math.ceil((labels?labels.length:data.length)/maxLabels));
  data.forEach((v,i)=>{
    const x = padLeft + i*bw*spacing; const bh = (v/max)*innerH; const y = padTop + innerH - bh;
    ctx.fillStyle = i===data.length-1 ? '#34d399' : '#e5e7eb';
    ctx.fillRect(x, y, bw, bh);
    // x label
    ctx.fillStyle='#6b7280'; ctx.font=`${10*fs}px sans-serif`;
    if((i%skip)===0){ ctx.save(); ctx.translate(x+2, padTop + innerH + 12*fs); ctx.rotate(-Math.PI/4); ctx.fillText(String(labels?labels[i]:i+1), 0, 0); ctx.restore(); }
    // value label (only if bars wide enough)
    if(bw>18*fs){ ctx.fillStyle='#374151'; ctx.font=`${10*fs}px sans-serif`; ctx.fillText(String(v), x+2, y-2); }
  });
}

// Horizontal bars for better readability on small widths or many labels
function drawBarsH(id, data, labels, opts={}){
  const c = document.getElementById(id); const ctx = c.getContext('2d');
  const dpr = window.devicePixelRatio || 1;
  const cssW = Math.max(1, c.clientWidth);
  const cssH = (c.clientHeight && c.clientHeight > 0) ? c.clientHeight : Math.round(cssW * 0.6);
  c.width = Math.floor(cssW * dpr);
  c.height = Math.floor(cssH * dpr);
  const w = c.width; const h = c.height; ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,w,h);
  const max = Math.max(...data, 1);
  const fs = (opts.fontScale||1);
  const padLeft = Math.max(60*fs, (labels?Math.min(180, (labels.reduce((m,s)=>Math.max(m,String(s).length),0))*6*fs):60*fs));
  const padRight = 12*fs; const padTop = (opts.title ? 24 : 10)*fs; const padBottom = (opts.xLabel? 20 : 6)*fs;
  const innerW = Math.max(1, w - padLeft - padRight);
  const innerH = Math.max(1, h - padTop - padBottom);

  if (opts.title){ ctx.fillStyle='#111827'; ctx.font=`${12*fs}px sans-serif`; ctx.textAlign='center'; ctx.fillText(opts.title, w/2, 14*fs); }
  if (opts.xLabel){ ctx.fillStyle='#6b7280'; ctx.font=`${11*fs}px sans-serif`; ctx.textAlign='center'; ctx.fillText(opts.xLabel, padLeft + innerW/2, padTop + innerH + 18*fs); }
  if (opts.yLabel){ ctx.save(); ctx.fillStyle='#6b7280'; ctx.font=`${11*fs}px sans-serif`; ctx.translate(12*fs, padTop + innerH/2); ctx.rotate(-Math.PI/2); ctx.textAlign='center'; ctx.fillText(opts.yLabel, 0, 0); ctx.restore(); }

  const rowGap = (opts.rowGap != null ? opts.rowGap : 0.3); // proportion of row reserved for gap
  const rowH = innerH / Math.max(1, data.length);
  data.forEach((v,i)=>{
    const y = padTop + i*rowH + rowH*(rowGap/2);
    const barH = rowH*(1 - rowGap);
    const bw = (v/max)*innerW;
    // label at left
    if(labels && labels[i] != null){ ctx.fillStyle='#374151'; ctx.font=`${11*fs}px sans-serif`; ctx.textAlign='right'; ctx.textBaseline='middle'; ctx.fillText(String(labels[i]), padLeft-6*fs, y+barH/2); }
    // bar
    ctx.fillStyle = i===data.length-1 ? '#34d399' : '#93c5fd';
    ctx.fillRect(padLeft, y, bw, barH);
    // value at end
    ctx.fillStyle='#111827'; ctx.font=`${11*fs}px sans-serif`; ctx.textAlign='left'; ctx.textBaseline='middle';
    ctx.fillText(String(v), padLeft + bw + 6*fs, y+barH/2);
  });
}

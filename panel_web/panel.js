/* Panel de gestión Minera Anita. Los cálculos de negocio vienen de la app de producción (iframe, misma sesión). */
(function(){
'use strict';
const $=s=>document.querySelector(s);
const nf=(n,d=0)=>n==null||isNaN(n)?'—':Number(n).toLocaleString('es-CL',{minimumFractionDigits:d,maximumFractionDigits:d});
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const MES=['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre'];
const DOW=['domingo','lunes','martes','miércoles','jueves','viernes','sábado'];
const fl=d=>{const x=new Date(d+'T12:00:00');return DOW[x.getDay()].replace(/^./,c=>c.toUpperCase())+' '+x.getDate()+' de '+MES[x.getMonth()]+' de '+x.getFullYear()};
const fc=d=>d?d.slice(8)+'/'+d.slice(5,7):'—';
const fh=iso=>{const d=new Date(iso);return d.toLocaleDateString('es-CL',{day:'2-digit',month:'2-digit'})+' '+d.toLocaleTimeString('es-CL',{hour:'2-digit',minute:'2-digit'})};
const pausa=ms=>new Promise(r=>setTimeout(r,ms));
let tt;function toast(t){const e=$('#toast');e.textContent=t;e.classList.add('show');clearTimeout(tt);tt=setTimeout(()=>e.classList.remove('show'),2600)}
const SULF=3.92*1.06,REC=0.70;

/* ---------- sesión ---------- */
let YO=null,lastAct=Date.now(),lastPing=Date.now();
async function api(u,o){const r=await fetch(u,{cache:'no-store',credentials:'same-origin',...o});if(r.status===401){location.replace('/panel');throw new Error('sesión')}if(!r.ok)throw new Error('HTTP '+r.status);return r.json()}
async function salir(motivo){try{await fetch('/panel/salir',{method:'POST',credentials:'same-origin'})}catch(e){}location.replace('/panel'+(motivo?'#'+motivo:''))}
function actividad(){lastAct=Date.now();if(Date.now()-lastPing>120e3){lastPing=Date.now();api('/panel/api/yo').catch(()=>{})}}
['click','keydown','scroll','mousemove','touchstart'].forEach(e=>document.addEventListener(e,actividad,{passive:true,capture:true}));
setInterval(()=>{if(YO&&Date.now()-lastAct>YO.minutos*60e3)salir('inactividad')},30e3);
$('#outBtn').addEventListener('click',()=>salir());

/* ---------- app de producción (motor de datos) ---------- */
const frame=$('#app');let APP=null;
frame.addEventListener('load',()=>{
  const w=frame.contentWindow;
  try{if(!w.location.pathname.startsWith('/panel/app')){location.replace('/panel');return}
    ['click','keydown','scroll','touchstart'].forEach(e=>w.document.addEventListener(e,actividad,{passive:true,capture:true}))}catch(e){}
});
async function esperarApp(){for(let i=0;i<600;i++){try{const w=frame.contentWindow;if(w.APP&&w.APP.listo()){APP=w.APP;return}}catch(e){}await pausa(300)}throw new Error('La app de datos no respondió')}

/* ---------- estado de las planillas y Actualizar ---------- */
function verEstado(m){
  if(!m){$('#sync').textContent='Sin conexión';return}
  if(m.cargando){const F=Object.values(m.fuentes||{}),ok=F.filter(f=>f.fase==='lista'||f.fase==='error').length;$('#sync').textContent='Descargando planillas… '+ok+' de '+F.length;return}
  $('#sync').textContent=m.actualizado?'Planillas actualizadas '+fh(m.actualizado):'Planillas aún no descargadas';
  const bad=Object.values(m.fuentes||{}).filter(f=>f.ok===false);
  $('#warn').hidden=!bad.length;$('#warn').innerHTML=bad.map(f=>`⚠ <b>${esc(f.nombre)}</b>: no se pudo actualizar. ${f.hora?'Se muestran los datos del '+fh(f.hora)+'.':'Sin datos.'} <small>(${esc(f.error||'')})</small>`).join('<br>');
  ESTADO=m;
}
let ESTADO=null,UPD=false;
async function esperarDescarga(){let m;for(let i=0;i<200;i++){m=await api('/panel/app/api/estado');verEstado(m);if(!m.cargando)return m;await pausa(1500)}return m}
$('#updBtn').addEventListener('click',async()=>{
  if(UPD)return;UPD=true;const b=$('#updBtn');b.disabled=true;b.textContent='Actualizando…';
  try{await api('/panel/app/api/actualizar',{method:'POST'});await pausa(600);const m=await esperarDescarga();await APP.recargar();pintar();
    toast(Object.values(m.fuentes).some(f=>f.ok===false)?'Actualizado con avisos':'Datos actualizados')}
  catch(e){toast('No se pudo actualizar')}
  finally{UPD=false;b.disabled=false;b.textContent='⟳ Actualizar'}
});

/* ---------- navegación ---------- */
const VISTAS={resumen:['Resumen',1],simulador:['Simulador de planta',1],reportes:['Reportes',0],usuarios:['Usuarios y accesos',0],
  prod:['Producción',0],pla:['Planta · control químico',0],min:['Mineral y pilas',0],pal:['Bodega y despachos',0],ins:['Insumos',0]};
const NATIVAS=['resumen','simulador','reportes','usuarios'];
let VISTA='resumen',DIA=null,R=null;
function ir(v){
  if(!VISTAS[v]||(v==='usuarios'&&(!YO||YO.rol!=='admin')))v='resumen';
  VISTA=v;history.replaceState(null,'','#'+v);
  document.querySelectorAll('.nav').forEach(b=>b.classList.toggle('on',b.dataset.v===v));
  $('#tTitle').textContent=VISTAS[v][0];$('#dayNav').hidden=!VISTAS[v][1];
  ['Resumen','Simulador','Reportes','Usuarios'].forEach(n=>$('#v'+n).hidden=v!==n.toLowerCase());
  $('#vApp').hidden=NATIVAS.includes(v);
  $('#side').classList.remove('open');
  pintar();
}
$('#nav').addEventListener('click',e=>{const b=e.target.closest('[data-v]');if(b)ir(b.dataset.v)});
$('#menuBtn').addEventListener('click',()=>$('#side').classList.toggle('open'));
function moverDia(n){if(!R)return;const f=R.dias,i=f.indexOf(DIA)+n;if(i>=0&&i<f.length){DIA=f[i];pintar()}}
$('#dPrev').addEventListener('click',()=>moverDia(-1));$('#dNext').addEventListener('click',()=>moverDia(1));
$('#dDay').addEventListener('change',()=>{const v=$('#dDay').value;if(!R||!v)return;DIA=R.dias.includes(v)?v:(R.dias.filter(x=>x<=v).pop()||R.dias[0]);pintar()});

function pintar(){
  if(!APP)return;
  if(!NATIVAS.includes(VISTA)){APP.vista(VISTA);$('#tSub').textContent='Datos de las planillas de Dropbox';return}
  R=APP.resumen(DIA);DIA=R.dia;
  const dd=$('#dDay');dd.value=DIA;if(R.dias.length){dd.min=R.dias[0];dd.max=R.dias[R.dias.length-1]}
  $('#tSub').textContent=VISTAS[VISTA][1]?fl(DIA):'';
  if(VISTA==='resumen')resumen();else if(VISTA==='simulador')simulador();else if(VISTA==='reportes')reportes();else usuarios();
}

/* ---------- gráfico de barras: esperados vs producidos ---------- */
function barras(serie){
  const W=760,H=200,L=36,Rm=8,T=14,B=24,iw=W-L-Rm,ih=H-T-B,n=Math.max(serie.length,1),st=iw/n,bw=Math.max(3,Math.min(16,st*.36));
  const top=v=>{const p=Math.pow(10,Math.floor(Math.log10(v||1)));return [1,1.5,2,2.5,3,4,5,6,8,10].find(k=>v/p<=k)*p};
  const mx=top(Math.max(10,...serie.flatMap(s=>[s[1],s[2]]))*1.02/4)*4,y=v=>T+ih-v/mx*ih;
  let o=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Sacos esperados y producidos por día">`;
  for(let i=0;i<=4;i++){const yy=T+ih*i/4;o+=`<line x1="${L}" x2="${W-Rm}" y1="${yy}" y2="${yy}" stroke="${i===4?'#E3E9F2':'#EEF2F8'}"/><text x="${L-6}" y="${yy+3}" text-anchor="end" font-size="10" fill="#64708A">${nf(mx*(1-i/4))}</text>`}
  serie.forEach(([f,e,p],i)=>{const cx=L+st*i+st/2;
    o+=`<g><title>${fc(f)} · esperados ${nf(e)} · producidos ${nf(p)} sacos</title><rect x="${cx-bw-1}" y="${y(e)}" width="${bw}" height="${T+ih-y(e)}" rx="2.5" fill="var(--c1)"/><rect x="${cx+1}" y="${y(p)}" width="${bw}" height="${T+ih-y(p)}" rx="2.5" fill="var(--c2)"/><rect x="${cx-st/2}" y="${T}" width="${st}" height="${ih}" fill="transparent"/></g>`;
    if(n<=16||i%2===0||i===n-1)o+=`<text x="${cx}" y="${H-7}" text-anchor="middle" font-size="10" fill="#64708A">${+f.slice(8)}</text>`});
  return o+'</svg>';
}

/* ---------- RESUMEN ---------- */
const SOLS=[['PLS','PLS','var(--c1)'],['ILS LIX','ILS','var(--c5)'],['REF LIX','REF LIX','var(--c3)'],['REF SX 1','REF SX 1','var(--c8)'],['REF SX 2','REF SX 2','var(--c2)'],['ELECTROLITO 1','Electrolito 1','var(--c4)'],['ELECTROLITO 2','Electrolito 2','var(--c7)']];
function resumen(){
  const p=R.prod,ex=p.extraccion,op=ex.filter(e=>e!=null),eg=op.length?op.reduce((a,b)=>a+b,0)/op.length:null,M=R.mineral,A=R.acido,B=R.bodega,Pe=R.petroleo;
  const dif=p.esperados!=null&&p.registrado?p.sacos-p.esperados:null;
  const tE=R.serie.reduce((a,s)=>a+s[1],0),tP=R.serie.reduce((a,s)=>a+s[2],0),mes=MES[+DIA.slice(5,7)-1];
  const diasAc=A&&A.consumoProm?A.total/A.consumoProm:null;
  // avisos
  const av=[];
  ex.forEach((e,i)=>{if(e==null)av.push(['r','Tren '+(i+1)+' detenido','Sin muestras de REF SX '+(i+1)+' este día.'])});
  if(dif!=null&&p.esperados>0&&p.sacos<p.esperados*.9)av.push(['w','Producción bajo lo esperado',nf(p.sacos)+' de '+nf(p.esperados)+' sacos esperados ('+nf(p.sacos/p.esperados*100)+'%).']);
  if(p.esperados&&!p.registrado)av.push(['w','Sin producción registrada','La planilla RECUPERACIÓN no tiene este día.']);
  const ref=R.sol['REF LIX']&&R.sol['REF LIX'].cu,baja=ref!=null?R.pilas.filter(x=>x.cu!=null&&x.cu-ref<0.4):[];
  if(baja.length)av.push(['w','Pilas con poco cobre',baja.map(x=>x.k.slice(0,6)).join(', ')+' entregan menos de 0,4 g/L sobre el refino ('+nf(ref,2)+' g/L).']);
  if(diasAc!=null&&diasAc<7)av.push(['w','Ácido: stock para '+nf(diasAc)+' días',nf(A.total,1)+' t en estanques · consumo promedio '+nf(A.consumoProm,1)+' t/día.']);
  const bad=ESTADO?Object.values(ESTADO.fuentes||{}).filter(f=>f.ok===false):[];
  bad.forEach(f=>av.push(['r','Planilla con error: '+f.nombre,'Se muestran sus últimos datos buenos.']));
  if(!av.length)av.push(['o','Todo en orden','Sin avisos para este día.']);
  const ico={r:'!',w:'!',o:'✓'};
  $('#vResumen').innerHTML=`
  <div class="k4">
   <div class="card kpi hero"><small>Producción del día</small><b>${p.registrado?nf(p.kg)+' kg':'—'}</b><em>${p.registrado?nf(p.sacos)+' sacos · ':''}acumulado ${mes} ${nf(p.kgMes/1000,1)} t</em></div>
   <div class="card kpi"><small>Producidos / esperados</small><b>${p.registrado?nf(p.sacos):'—'} <span>/ ${nf(p.esperados)} sacos</span></b>${dif!=null&&p.esperados?`<em class="${dif>=0?'up':'dn'}">${dif>=0?'▲ +':'▼ −'}${nf(Math.abs(dif))} · ${nf(p.sacos/p.esperados*100)}% de lo esperado</em>`:'<em>esperados según control químico</em>'}</div>
   <div class="card kpi"><small>Extracción global SX</small><b>${eg!=null?nf(eg*100,1)+'%':'—'}</b><em>${ex.map((e,i)=>`<span class="tg ${e!=null?'g2':'r2'}">T${i+1} · ${e!=null?nf(e*100,1)+'%':'detenido'}</span>`).join('')}</em></div>
   <div class="card kpi"><small>Mineral por chancar</small><b>${M?nf(M.disp,1)+' t':'—'}</b><em>${M?'stock pile '+nf(M.stockPile)+' t · rechazo '+nf(M.rechazo)+' t':'sin datos de mineral'}</em></div>
  </div>
  <div class="g2c">
   <div class="card"><h3>Producción de ${mes} <span>sacos esperados vs producidos, hasta el ${fc(DIA)}</span></h3>
    <div class="chart">${barras(R.serie)}</div>
    <div class="leg"><span><i class="dot" style="background:var(--c1)"></i>Esperados</span><span><i class="dot" style="background:var(--c2)"></i>Producidos</span>
     <span style="margin-left:auto">Producidos ${nf(tP)} / esperados ${nf(tE)} · cumplimiento <b class="${tP>=tE?'up':'dn'}">${tE?nf(tP/tE*100,1)+'%':'—'}</b></span></div></div>
   <div class="card"><h3>Atención <span>${av[0][0]==='o'?'sin avisos':av.length+(av.length>1?' avisos':' aviso')}</span></h3>
    ${av.map(a=>`<div class="al"><div class="ic ${a[0]}">${ico[a[0]]}</div><div><b>${esc(a[1])}</b><span>${esc(a[2])}</span></div></div>`).join('')}</div>
  </div>
  <div class="g3c">
   <div class="card"><h3>Soluciones del día <span>promedio g/L</span></h3>
    ${Object.keys(R.sol).length?`<table><tr><th>Solución</th><th>Cu</th><th>H+</th><th>pH</th></tr>${SOLS.filter(s=>R.sol[s[0]]&&R.sol[s[0]].cu!=null).map(s=>{const o=R.sol[s[0]];return `<tr><td><i class="dot" style="background:${s[2]}"></i>${s[1]}</td><td><b>${nf(o.cu,o.cu<10?2:1)}</b></td><td>${nf(o.h,1)}</td><td>${o.ph!=null?nf(o.ph,2):'—'}</td></tr>`}).join('')}</table>`:'<p class="empty">Sin muestras este día.</p>'}</div>
   <div class="card"><h3>Pilas en riego <span>${R.pilas.length} ${R.pilas.length===1?'pila':'pilas'}</span></h3>
    ${R.pilas.length?`<table><tr><th>Pila</th><th>Días</th><th>Cu g/L</th><th>Destino</th></tr>${R.pilas.map(x=>`<tr><td>${esc(x.k)} ${x.ripio?'<span class="tg b2">ripio</span>':''}</td><td>${x.dias}</td><td><b>${nf(x.cu,2)}</b></td><td>${esc((x.destino||'—').replace(' LIX',''))}</td></tr>`).join('')}</table>`:'<p class="empty">Sin pilas con lecturas este día.</p>'}</div>
   <div class="card"><h3>Insumos y bodega</h3>
    <div class="row"><span>Ácido en estanques</span><b>${A?nf(A.total,1)+' t':'—'}</b></div>
    ${A?`<div class="row" style="margin-top:4px;color:var(--mut)"><span>TK3 ${nf(A.tk3,1)} t · TK4 ${nf(A.tk4,1)} t</span><span>${diasAc!=null?'≈ '+nf(diasAc)+' días de consumo':''}</span></div>`:''}
    <div class="row"><span>Ácido consumido el día</span><b>${A&&A.consumoDia!=null?nf(A.consumoDia,1)+' t':'—'}</b></div>
    <div class="row"><span>Mineral chancado el día</span><b>${M&&M.chancadoDia?nf(M.chancadoDia,1)+' t':'—'}</b></div>
    <div class="row"><span>Mineral chancado en ${mes}</span><b>${M?nf(M.chancadoMes,1)+' t':'—'}</b></div>
    <div class="row"><span>Petróleo entregado en ${mes}</span><b>${Pe?nf(Pe.mes)+' L':'—'}</b></div>
    <div class="row"><span>Pallets en bodega</span><b>${B?nf(B.pallets)+' · '+nf(B.ton,1)+' t':'—'}</b></div>
    <div class="row"><span>Despachos en ${mes}</span><b>${B?nf(B.despMes)+' pallets':'—'}</b></div></div>
  </div>
  <p class="note">Datos de las planillas de Dropbox. Control químico hasta el ${R.cqHasta?fc(R.cqHasta)+'/'+R.cqHasta.slice(0,4):'—'}. Sacos esperados = Cu PLS × ${R.flujo} L/min × 1.440 min × extracción de cada tren × 3,92 × ${nf(R.humedad,2)} ÷ 25 kg.</p>`;
}

/* ---------- SIMULADOR ---------- */
let SIM=null;
function simBase(){
  const s=R.sol,pls=s.PLS&&s.PLS.cu,ex=R.prod.extraccion,op=ex.filter(e=>e!=null),M=R.mineral||{};
  return {t:Math.round(M.chancadoDia||250),ley:+(M.leyDia||0.7).toFixed(2),pls:+((pls||2).toFixed(2)),flujo:R.flujo,ext:+((op.length?op.reduce((a,b)=>a+b,0)/op.length:0.9)*100).toFixed(1),trenes:op.length||1};
}
function diagrama(){
  const s=R.sol,g=k=>s[k]&&s[k].cu,h=k=>s[k]&&s[k].h,ex=R.prod.extraccion,M=R.mineral||{},A=R.acido||{};
  let o='';
  const OFF={fill:'#F4F6FA',stroke:'#DDE3EC'};
  const box=(x,y,w,hh,t,m,v,op={})=>{o+=`<rect x="${x}" y="${y}" width="${w}" height="${hh}" rx="10" fill="${op.dark?'url(#gn)':op.fill||'url(#gb)'}" stroke="${op.stroke||'#C9D6EC'}"/>`;
    const dk=op.dark;o+=`<text class="t" x="${x+w/2}" y="${y+16}" text-anchor="middle" style="fill:${dk?'#fff':op.mut?'#9AA6B8':'#101B33'}">${t}</text>`;
    if(m)o+=`<text class="m" x="${x+w/2}" y="${y+29}" text-anchor="middle" style="fill:${dk?'#B9C8F0':'#64708A'}">${m}</text>`;
    if(v)o+=`<text class="v" x="${x+w/2}" y="${y+hh-8}" text-anchor="middle" style="fill:${dk?'#7FE6FF':op.mut?'#9AA6B8':'#0A1A5C'}">${v}</text>`};
  const ar=(d,c,dash)=>{o+=`<path d="${d}" fill="none" stroke="${c||'#8FA2C8'}" stroke-width="1.6" ${dash?'stroke-dasharray="4 3"':''} marker-end="url(#ar)"/>`};
  const lab=(x,y,t,c)=>{o+=`<text class="m" x="${x}" y="${y}" text-anchor="middle" style="fill:${c||'#64708A'}">${t}</text>`};
  const sec=(y,t,x)=>{o+=`<text x="${x||6}" y="${y}" style="font-weight:800;font-size:11px;fill:#1E73D8;letter-spacing:1px">${t}</text>`};
  const cu=v=>v==null?'—':nf(v,v<10?2:1);
  sec(14,'CHANCADO Y AGLOMERACIÓN');
  box(6,24,78,50,'Buzón','chancado día',M.chancadoDia?nf(M.chancadoDia,1)+' t':'—');ar('M84 49H110');lab(97,43,'C1');
  box(112,24,104,50,'Chancador 1°','mandíbula','');ar('M216 49H242');lab(229,43,'C2');
  box(244,24,84,50,'Harnero','corte 3/8"','');
  ar('M328 49H398');lab(363,43,'sobretamaño');box(400,24,104,50,'Chancador 2°','cono','');ar('M504 49H530');lab(517,43,'C3');
  box(532,24,104,50,'Chancador 3°','cono','');ar('M636 49H660V111H630');lab(672,82,'C4');
  ar('M286 74V111H518');lab(400,105,'bajo 3/8" · C5');
  box(520,86,108,50,'Aglomeración',M.leyDia?'ley '+nf(M.leyDia,2)+'%':'+ agua + ácido',A.consumoDia!=null?'ácido '+nf(A.consumoDia,1)+' t':'',{fill:'#FFF7EE',stroke:'#F0C9A6'});
  box(700,86,110,50,'Rechazo','stock',M.rechazo!=null?nf(M.rechazo)+' t':'—',{fill:'#FDF1F0',stroke:'#F0B9B3'});
  sec(166,'LIXIVIACIÓN · 12 MÓDULOS + MEGAPILA');
  ar('M574 136V176');
  const mod={};R.pilas.forEach(p=>{const n=parseInt(p.k.slice(1,3),10);if(n>=1&&n<=12)mod[n]=p});
  for(let i=0;i<12;i++){const x=6+i%6*112,y=178+Math.floor(i/6)*58,p=mod[i+1];
    o+=`<g><title>${p?esc(p.k)+' · día '+p.dias+' · Cu '+cu(p.cu)+' g/L':'Módulo '+(i+1)+' sin riego'}</title><rect x="${x}" y="${y}" width="104" height="50" rx="9" fill="${p?(p.ripio?'#EEF8F2':'#EAF4FF'):'#F4F6FA'}" stroke="${p?(p.ripio?'#A6DDC0':'#9CC4F2'):'#DDE3EC'}"/>
    <text class="t" x="${x+10}" y="${y+17}" style="fill:${p?'#0A1A5C':'#9AA6B8'}">${p?esc(p.k.slice(0,6)):'Módulo '+String(i+1).padStart(2,'0')}</text>
    <text x="${x+10}" y="${y+37}" style="font-size:11px;fill:${p?'#101B33':'#9AA6B8'}">${p?'Cu <tspan font-weight="800">'+cu(p.cu)+'</tspan> · d'+p.dias:'sin riego'}</text>${p?`<circle cx="${x+92}" cy="${y+13}" r="4" fill="${p.ripio?'#1baf7a':'#16D3FF'}"/>`:''}</g>`}
  box(684,178,126,108,'Megapila','','sin datos',{...OFF,mut:1});
  sec(318,'PISCINAS');
  box(120,332,170,58,'Piscina ILS','intermedia','Cu '+cu(g('ILS LIX'))+' · H+ '+nf(h('ILS LIX'),1),{fill:'#E8FBFF',stroke:'#9CE3F5'});
  box(330,332,170,58,'Piscina PLS','rica · a planta','Cu '+cu(g('PLS'))+' · H+ '+nf(h('PLS'),1)+(s.PLS&&s.PLS.ph!=null?' · pH '+nf(s.PLS.ph,2):''),{dark:1});
  box(540,332,170,58,'Piscina REF','refino · a riego','Cu '+cu(g('REF LIX'))+' · H+ '+nf(h('REF LIX'),1),{fill:'#EAF7F0',stroke:'#A6DDC0'});
  ar('M170 332V296','#16A8C8');lab(150,317,'riego','#16A8C8');ar('M240 294V330');lab(266,317,'drenaje');ar('M415 294V330');lab(441,317,'drenaje');ar('M625 332V296','#1BAF7A');lab(647,317,'riego','#14804A');
  sec(428,'EXTRACCIÓN POR SOLVENTES Y CRISTALIZACIÓN',40);
  ar('M415 390V408H24V619H98','#1E73D8');lab(492,404,'PLS · '+R.flujo+' L/min por tren','#1E73D8');
  const tren=(i,y,E)=>{const on=ex[i]!=null,col=on?'#14804A':'#C0392B',hh=on?126:92,st=on?{}:{...OFF,mut:1};
    o+=`<rect x="34" y="${y}" width="750" height="${hh}" rx="12" fill="${on?'#F5FAFF':'#FAFBFD'}" stroke="${on?'#BCD8F7':'#E3E9F2'}" ${on?'':'stroke-dasharray="5 4"'}/><text x="46" y="${y+18}" style="font-weight:800;font-size:11px;fill:${col}">TREN ${i+1} · ${on?'OPERATIVO · EXTRACCIÓN '+nf(ex[i]*100,1)+'%':'DETENIDO (sin muestras)'}</text>`;
    const by=y+(on?44:28),bh=on?58:52,el=s['ELECTROLITO '+(i+1)],rs=g('REF SX '+(i+1));
    if(on)ar(`M24 ${by+29}H98`,'#1E73D8');else ar(`M24 ${by+26}H98`,'#C9D0DC',1);
    box(100,by,100,bh,E[0],'extracción',on?'PLS '+cu(g('PLS')):'—',st);ar(`M200 ${by+bh/2}H228`,on?null:'#C9D0DC');
    box(230,by,100,bh,E[1],'extracción',on?'REF SX '+cu(rs):'—',st);
    if(on){ar(`M150 ${by}V${by-12}H410V${by-2}`,'#6250D6');lab(352,by-17,'orgánico cargado','#6250D6')}else ar(`M330 ${by+bh/2}H368`,'#C9D0DC');
    box(370,by,120,bh,'Cristalizador '+E[2],on?'orgánico + electrolito':'',el&&el.cu!=null?'Cu '+cu(el.cu)+' · H+ '+nf(el.h,0):'—',on?{fill:'#F1EEFF',stroke:'#C9C1F5'}:st);
    return {on,by,bh}};
  tren(0,440,['E1','E2','Cr1']);const t2=tren(1,546,['E3','E4','Cr2']);
  const yb=t2.by,bh=t2.bh;
  ar(`M490 ${yb+bh/2}H508`);box(510,yb,100,bh,'Lavador','acumulador','');
  ar(`M560 ${yb}V${yb-12}H450V${yb-2}`,'#6250D6');lab(506,yb-17,'rebalse','#6250D6');
  ar(`M610 ${yb+bh/2}H638`);box(640,yb,134,bh,'Sulfato de cobre','producción del día',R.prod.registrado?nf(R.prod.kg)+' kg · '+nf(R.prod.sacos)+' sacos':'sin registro',{dark:1});
  ar(`M280 ${yb+bh}V688H800V361H712`,'#EB6834');lab(540,702,'REF SX → vuelve a piscina REF','#C0652F');
  return `<svg class="flow" viewBox="0 0 820 712" width="100%" role="img" aria-label="Diagrama de la planta con los datos del día"><defs><marker id="ar" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0 0L7 3.5L0 7z" fill="#8FA2C8"/></marker>
   <linearGradient id="gb" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#F6F9FF"/><stop offset="1" stop-color="#E9F0FC"/></linearGradient><linearGradient id="gn" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0A1A5C"/><stop offset="1" stop-color="#1E73D8"/></linearGradient></defs>${o}</svg>`;
}
const SL=[['t','Mineral chancado','t/día',0,600,5,0],['ley','Ley del mineral','%',0.1,2,0.01,2],['pls','Cobre en PLS','g/L',0.3,6,0.01,2],['flujo','Flujo a SX por tren','L/min',80,300,5,0],['ext','Extracción SX','%',40,100,0.5,1],['trenes','Trenes en operación','',1,2,1,0]];
function simulador(){
  const base=simBase();if(!SIM||SIM.dia!==DIA)SIM={dia:DIA,...base};
  $('#vSimulador').innerHTML=`<div class="sim"><div class="card" style="padding:10px 12px">${diagrama()}</div>
   <div style="display:grid;gap:16px">
    <div class="card"><h3>¿Qué pasa si…? <span><button class="btn g" id="simReset" style="padding:5px 10px;font-size:12px">Datos del día</button></span></h3>
     ${SL.map(([k,t,u,mi,ma,st])=>`<div class="sl"><label for="sl_${k}">${t}<b id="sv_${k}"></b></label><input type="range" id="sl_${k}" data-k="${k}" min="${mi}" max="${ma}" step="${st}" value="${SIM[k]}"><small id="sb_${k}"></small></div>`).join('')}
     <div class="res"><small>Sulfato esperado de SX</small><b id="rSx"></b><small id="rSx2"></small></div>
     <div class="res alt" style="margin-top:10px"><small>Sulfato que aporta el mineral chancado (recuperación ${REC*100}%)</small><b id="rMin"></b><small id="rMin2"></small></div></div>
    <div class="card"><h3>Balance real del día</h3><div id="bal"></div></div>
   </div></div>`;
  $('#vSimulador').querySelectorAll('input[type=range]').forEach(i=>i.addEventListener('input',()=>{SIM[i.dataset.k]=+i.value;simCalc()}));
  $('#simReset').addEventListener('click',()=>{SIM={dia:DIA,...simBase()};simulador()});
  simCalc();
  // balance real
  const s=R.sol,pls=s.PLS&&s.PLS.cu,ex=R.prod.extraccion,ent=pls?ex.filter(e=>e!=null).length*pls*R.flujo*1440/1000:null,xt=pls?ex.reduce((a,e)=>a+(e!=null?pls*R.flujo*1440/1000*e:0),0):null;
  $('#bal').innerHTML=`<div class="row"><span>Cobre que entra a SX</span><b>${nf(ent)} kg</b></div><div class="row"><span>Cobre extraído</span><b>${nf(xt)} kg</b></div>
   <div class="row"><span>Sulfato equivalente (×3,92×${nf(R.humedad,2)})</span><b>${nf(xt!=null?xt*SULF:null)} kg</b></div>
   <div class="row"><span>Producido real</span><b class="${R.prod.registrado&&xt&&R.prod.kg>=xt*SULF?'up':''}">${R.prod.registrado?nf(R.prod.kg)+' kg':'sin registro'}</b></div>
   <p class="note">Con ${ex.filter(e=>e!=null).length} ${ex.filter(e=>e!=null).length===1?'tren':'trenes'} en operación y ${R.flujo} L/min por tren.</p>`;
}
function simCalc(){
  const b=simBase(),S=SIM;
  SL.forEach(([k,t,u,,,,d])=>{$('#sv_'+k).textContent=nf(S[k],d)+(u?' '+u:'');$('#sb_'+k).textContent=S[k]!==b[k]?'dato del día: '+nf(b[k],d)+(u?' '+u:''):''});
  const cuDia=S.pls*S.flujo*1440/1000*S.ext/100*S.trenes,sx=cuDia*SULF,sxB=b.pls*b.flujo*1440/1000*b.ext/100*b.trenes*SULF,d=sx-sxB;
  $('#rSx').textContent=nf(sx)+' kg/día';
  $('#rSx2').textContent=nf(sx/25)+' sacos · '+nf(sx*30/1000,1)+' t al mes'+(Math.abs(d)>.5?' · '+(d>0?'+':'−')+nf(Math.abs(d))+' kg vs el día':'');
  const pot=S.t*S.ley/100*REC*SULF;   // t de sulfato que aportaría ese mineral en todo su ciclo de riego
  $('#rMin').textContent=nf(pot,1)+' t de sulfato';
  $('#rMin2').textContent=nf(S.t*S.ley/100*1000)+' kg de cobre fino'+(sx>0?' · equivale a '+nf(pot*1000/sx,1)+' días de producción al ritmo simulado':'');
}

/* ---------- REPORTES ---------- */
function reportes(){
  $('#vReportes').innerHTML=`<div class="g2c"><div class="card"><h3>Reporte diario de planta (PDF) <span class="tg b2" style="margin-left:auto">en preparación</span></h3>
   <p style="font-size:13.5px;line-height:1.6;margin:0">El diseño aprobado tiene tres páginas: indicadores y soluciones del día, mineral · ácido · chancado · petróleo, y pilas en riego. Se generará para el día que elijas desde este panel.</p>
   <p class="note">Mientras tanto, los mismos datos están en <b>Planta · control químico</b> y en el <b>Resumen</b>.</p></div>
   <div class="card"><h3>Otros documentos disponibles</h3><div class="row"><span>Petróleo entregado a externos (PDF)</span><b>Insumos → Petróleo</b></div></div></div>`;
}

/* ---------- USUARIOS ---------- */
async function usuarios(){
  const v=$('#vUsuarios');v.innerHTML='<p class="empty">Cargando…</p>';
  try{const d=await api('/panel/api/accesos'),ev={ingreso:'g2',salida:'b2','sesión vencida':'b2',rechazado:'r2',bloqueado:'r2','acceso revocado':'r2'};
   v.innerHTML=`<div class="g2c"><div class="card"><h3>Registro de accesos <span>últimos ${d.accesos.length} eventos desde el último reinicio del servidor</span></h3>
    ${d.accesos.length?`<table><tr><th>Fecha y hora</th><th style="text-align:left">Evento</th><th style="text-align:left">Persona</th><th>Dirección</th></tr>${d.accesos.map(a=>`<tr><td>${fh(a.hora)}</td><td style="text-align:left"><span class="tg ${ev[a.evento]||'b2'}">${esc(a.evento)}</span>${a.detalle?' <small style="color:var(--mut)">'+esc(a.detalle)+'</small>':''}</td><td style="text-align:left">${esc(a.nombre||a.correo||'—')}</td><td>${esc(a.ip)}</td></tr>`).join('')}</table>`:'<p class="empty">Sin eventos todavía.</p>'}
    <p class="note">El servidor gratuito de Render se reinicia al dormir; el historial completo queda en los registros (Logs) de Render, líneas que empiezan con «PANEL».</p></div>
    <div class="card"><h3>Usuarios autorizados <span>${d.usuarios.length}</span></h3><table><tr><th>Nombre</th><th style="text-align:left">Correo</th><th>Rol</th></tr>${d.usuarios.map(u=>`<tr><td>${esc(u.nombre)}</td><td style="text-align:left">${esc(u.correo)}</td><td><span class="tg ${u.rol==='admin'?'b2':'g2'}">${u.rol==='admin'?'Administrador':'Usuario'}</span></td></tr>`).join('')}</table>
    <p class="note">Para agregar o quitar personas se edita la variable PANEL_USUARIOS en Render. La sesión se cierra tras ${d.minutos} minutos sin uso.</p></div></div>`}
  catch(e){v.innerHTML='<p class="empty">No se pudo cargar el registro.</p>'}
}

/* ---------- inicio ---------- */
(async function(){
  try{YO=await api('/panel/api/yo')}catch(e){return}
  $('#uName').textContent=YO.nombre;$('#uRol').textContent=YO.rol==='admin'?'Administrador':'Usuario';
  $('#uAv').textContent=YO.nombre.split(/\s+/).map(w=>w[0]).slice(0,2).join('').toUpperCase();
  document.querySelectorAll('.adm').forEach(e=>e.hidden=YO.rol!=='admin');
  const h=location.hash.slice(1);ir(VISTAS[h]?h:'resumen');
  try{verEstado(await api('/panel/app/api/estado'))}catch(e){}
  try{await esperarApp()}catch(e){$('#loadTxt').textContent='No se pudieron cargar los datos. Recarga la página.';return}
  if(ESTADO&&ESTADO.cargando){$('#loadTxt').textContent='El servidor está descargando las planillas de Dropbox…';await esperarDescarga();await APP.recargar()}
  $('#loading').hidden=true;pintar();
})();
})();

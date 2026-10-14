const $=id=>document.getElementById(id);
const esc=s=>String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
// URL-sicher für CSS url('...') / style-Attribut: Quotes, Klammern, Backslash entfernen
const urlEsc=s=>String(s||"").replace(/['"()\\{}]/g,"");
const show=id=>$(id)&&$(id).classList.remove("H");
const hide=id=>$(id)&&$(id).classList.add("H");
const tog=(id,v)=>v?show(id):hide(id);

let S=null,myCode="",myPid="",myPName="",myPcode="";
let selT="item",selG="A",selSz="1",selMw=3;
let saSelT="item",saSelG="A",saSelSz="1";
let acTmr=null,pollTmr=null;
let superSecret="";

async function api(path,method="GET",body=null){
  const headers={"Content-Type":"application/json"};
  // M4: Secrets/Codes nur als Header senden — nie in Query/URL (Access-Logs, History, Referer).
  if(myCode) headers["X-SCLM-Code"]=myCode;
  if(superSecret) headers["X-SCLM-Secret"]=superSecret;
  const o={method,headers};
  if(body) o.body=JSON.stringify(body);
  try{const r=await fetch(path,o);return r.json();}catch(e){return{error:"Netzwerkfehler"};}
}

function cpText(txt){
  if(navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(txt).catch(()=>fbCopy(txt));
  } else fbCopy(txt);
}
function fbCopy(txt){
  const ta=document.createElement("textarea");ta.value=txt;ta.style="position:fixed;opacity:0";
  document.body.appendChild(ta);ta.focus();ta.select();
  try{document.execCommand("copy");alert("Kopiert: "+txt);}catch(e){alert("Code: "+txt);}
  document.body.removeChild(ta);
}

function pillsHTML(l){
  let h="";
  if(l.type&&l.type!=="item"){
    const c={MIL:"mil",STE:"ste",COM:"com",CIV:"civ",IND:"ind"}[l.type]||"gray";
    h+=`<span class="pill p-${c}">${esc(l.type)}</span>`;
  }
  if(l.grade) h+=`<span class="pill p-grade">GR-${esc(l.grade)}</span>`;
  if(l.size!=null&&l.size!=="")  h+=`<span class="pill p-size">S${esc(l.size)}</span>`;
  return h;
}
function initials(n){
  const k=n.match(/\(([^)]+)\)$/);
  if(k) return k[1].slice(0,2).toUpperCase();
  return (n.replace(/^\[[^\]]*\]/,"").trim()||n).slice(0,2).toUpperCase();
}
function fmtN(n,dec=0){const loc=getLang()==="en"?"en-GB":"de-DE";return n==null?"—":Number(n).toLocaleString(loc,{maximumFractionDigits:dec});}
function totalItems(s){return(s.loot||[]).filter(l=>!l.for_sale).reduce((a,l)=>a+l.qty,0);}
function totalWishes(s){return(s.participants||[]).reduce((a,p)=>a+(p.wishes||[]).length,0);}
function groupedChips(won){
  const map=new Map();
  for(const w of (won||[])){
    const k=`${w.name}||${w.type||''}||${w.grade||''}||${w.size||''}`;
    if(!map.has(k)) map.set(k,{w,n:0});
    map.get(k).n++;
  }
  return [...map.values()].map(({w,n})=>{
    let txt=`📦 ${esc(w.name)}`;
    if(w.type) txt+=` ${w.type}`;
    if(w.grade) txt+=` GR-${w.grade}`;
    if(w.size)  txt+=` S${w.size}`;
    if(n>1) txt+=` <strong style="color:var(--acc)">×${n}</strong>`;
    return`<span class="chip">${txt}</span>`;
  }).join('');
}

// ── HOME ──────────────────────────────────────────────────────────────────────
function showPage(pg){["pg-home","pg-admin","pg-part","pg-super","pg-ro","pg-about"].forEach(p=>hide(p));show(pg);}

async function loadHome(){
  showPage("pg-home");hide("spill");hide("btn-leave");stopPoll();
  clearNavState();
  // Load aggregate stats
  api("/api/stats").then(st=>{
    if(st.error){$("home-stats").innerHTML="";return;}
    $("home-stats").innerHTML=`
      <div class="stat" style="background:var(--bg2)">
        <div class="sv">${fmtN(st.session_count)}</div>
        <div class="sl">${t("stats.events")}</div>
      </div>
      <div class="stat" style="background:var(--bg2)">
        <div class="sv">${fmtN(st.total_loot_raffled)}</div>
        <div class="sl">${t("stats.raffled")}</div>
      </div>
      <div class="stat" style="background:var(--bg2)">
        <div class="sv">${fmtN(st.total_scu,1)}</div>
        <div class="sl">${t("stats.scu")}</div>
      </div>
      <div class="stat" style="background:var(--bg2)">
        <div class="sv">${st.total_revenue>0?fmtN(st.total_revenue)+" aUEC":"—"}</div>
        <div class="sl">${t("stats.revenue")}</div>
      </div>`;
  });
  const list=await api("/api/sessions");
  const el=$("event-list");
  if(!list.length){el.innerHTML=`<div class="empty">${t("home.events.empty")}</div>`;return;}
  el.innerHTML=list.map(s=>{
    const lk=s.locked?`<span class="pill p-grade">${t("home.ec.locked")}</span>`:'';
    const dn=s.raffle_done?`<span class="pill p-civ">${t("home.ec.raffled")}</span>`:'';
    const scu=s.commodity_scu!=null?fmtN(s.commodity_scu,1)+" SCU":t("misc.n_a");
    const rev=s.commodity_revenue?fmtN(s.commodity_revenue)+" aUEC":t("misc.n_a");
    const imgStyle=s.image_url
      ? `background:linear-gradient(to right,var(--bg2) 50%,rgba(18,26,34,.85) 55%,rgba(18,26,34,.4) 100%),url('${urlEsc(s.image_url)}') right/54% no-repeat;`
      : '';
    return `<div class="ec" style="${imgStyle}">
      <div class="ec-name">${esc(s.name)} ${lk} ${dn}</div>
      <div class="ec-meta"><span>${s.created}</span><span>👥 ${s.participant_count}</span><span>📦 ${s.loot_count}</span><span>🏷 ${scu}</span><span>💰 ${rev}</span></div>
      <div class="ec-actions">
        <button class="btn btn-xs" onclick="openRO('${s.join_code}')">${t("home.ec.view")}</button>
        ${getCreatorCode(s.id)?`<button class="btn btn-xs btn-gold" onclick="quickAdminLogin('${s.id}')">${t("home.ec.creator")}</button>`:""}
      </div>
    </div>`;
  }).join("");
}

// M7: Admin-Codes NUR im sessionStorage (per Tab, kein Überleben über den
// Browser-Neustart) und es wird nur der ZU EINEM ZEITPUNKT AKTIVE Code gehalten —
// nicht die ganze Map aller erstellten Events. Tradeoff: nach Wechsel auf ein
// anderes Event ist der "Als Ersteller"-Schnellzugriff für davor erstellte Events
// im selben Tab nicht mehr verfügbar.
function saveCreatorCode(sid,code){try{sessionStorage.setItem("sclm_creator",JSON.stringify({sid,code}));}catch(e){}}
function getCreatorCode(sid){try{const m=JSON.parse(sessionStorage.getItem("sclm_creator")||"{}");return(m&&m.sid===sid)?(m.code||null):null;}catch(e){return null;}}
function togCreatePanel(){$("create-panel").classList.toggle("H");}
function sMw(btn){$("mw-grp").querySelectorAll(".tgl").forEach(b=>b.className="tgl");btn.classList.add("st");selMw=+btn.dataset.v;}

async function createSession(){
  const name=$("new-name").value.trim();if(!name) return;
  const r=await api("/api/session/create","POST",{name,max_wishes:selMw});
  if(r.error){$("create-err").textContent=r.error;show("create-err");return;}
  hide("create-err");myCode=r.admin_code;S=await api(`/api/session/${r.admin_code}`);
  saveCreatorCode(S.id,r.admin_code);showAdminView();
}

async function importRH(inp){
  const file=inp.files[0];if(!file) return;
  let jd;try{jd=JSON.parse(await file.text());}catch(e){alert(t("err.invalid_json"));return;}
  const r=await api("/api/raidhelper/parse","POST",{json_data:jd});
  if(r.error){alert(r.error);return;}
  $("new-name").value=r.name;show("create-panel");
  const prev=r.participants.slice(0,8).join(", ")+(r.participants.length>8?"...":"");
  if(!confirm(t("confirm.create_session",{name:r.name,count:r.participants.length})+`\n\n${prev}`)) return;
  const cr=await api("/api/session/create","POST",{name:r.name,max_wishes:selMw,image_url:r.image_url||null});
  if(cr.error){alert(cr.error);return;}
  for(const nm of r.participants) await api(`/api/session/${cr.id}/participants`,"POST",{code:cr.admin_code,name:nm,added_by:"admin"});
  myCode=cr.admin_code;S=await api(`/api/session/${cr.admin_code}`);
  saveCreatorCode(S.id,cr.admin_code);showAdminView();
}

async function loginCode(){
  const code=$("code-inp").value.trim().toUpperCase();if(!code) return;
  const r=await api(`/api/session/${code}`);
  if(r.error){$("code-err").textContent=r.error;show("code-err");return;}
  hide("code-err");S=r;myCode=code;
  if(r.is_admin){if(r.admin_code)saveCreatorCode(r.id,r.admin_code);showAdminView();}else showPartView();
}
async function quickAdminLogin(sid){
  const code=getCreatorCode(sid);if(!code)return;
  const r=await api(`/api/session/${code}`);
  if(r.error){alert(t("err.code_invalid"));return;}
  S=r;myCode=code;showAdminView();
}
async function openRO(jc){
  const r=await api(`/api/session/${jc}`);
  if(r.error){alert(r.error);return;}
  S=r;myCode=jc;showROView();
}

function goHome(){myCode="";myPid="";myPName="";S=null;clearNavState();document.body.style.backgroundImage="";loadHome();}
async function goAdmin(){
  const sec=prompt(t("adm.prompt.secret"));
  if(!sec) return;
  const r=await api("/api/admin/verify","POST",{secret:sec});
  if(r.error){alert(t("adm.err.wrong_pw"));return;}
  superSecret=sec;loadSuperAdmin();
}
function leaveSess(){stopPoll();clearInterval(adminPollTmr);clearNavState();goHome();}

// ── READ-ONLY VIEW ────────────────────────────────────────────────────────────
function showROView(){
  showPage("pg-ro");hide("spill");hide("btn-leave");
  applySessionBg();
  saveNavState("ro",myCode,null,null);
  $("ro-title").textContent=S.name.toUpperCase();
  $("ro-sub").textContent=`${S.created} // ${S.locked?t("ro.status.locked"):t("ro.status.active")}`;
  // stats
  const n=S.participants.length;
  const ti=totalItems(S);
  const sum=S.commodity_summary||{};
  const roRawRev=sum.total_revenue!=null?sum.total_revenue:null;
  const roNetRev=roRawRev!=null?Math.round(roRawRev*0.995):null;
  const roPerRaw=roNetRev!=null&&n>0?Math.round(roNetRev/n):null;
  const roPerNet=roPerRaw!=null?Math.round(roPerRaw*0.995):null;
  $("ro-stats").innerHTML=`
    <div class="stat"><div class="sv">${n}</div><div class="sl">Teilnehmer</div></div>
    <div class="stat"><div class="sv">${ti}</div><div class="sl">Loot-Items</div></div>
    <div class="stat"><div class="sv">${fmtN(sum.total_scu,1)}</div><div class="sl">${t("ro.stat.scu")}</div></div>
    <div class="stat"><div class="sv">${roNetRev!=null?fmtN(roNetRev):"—"}</div><div class="sl">${t("co.sum.net")}</div></div>
    ${roPerNet!=null?`<div class="stat"><div class="sv">${fmtN(roPerNet)} aUEC</div><div class="sl">${t("co.sum.per")}</div></div>`:""}`;
  roTab("loot");
}

function roTab(t){
  ["loot","comm","res"].forEach(x=>{tog(`rot-${x}-c`,x===t);$(`rot-${x}`).classList.toggle("active",x===t);});
  if(t==="loot") renderROLoot();
  if(t==="comm") renderROComm();
  if(t==="res")  renderRORes();
}

function renderROLoot(){
  const el=$("ro-loot-list");
  const loot=[...S.loot].sort((a,b)=>a.name.localeCompare(b.name,"de"));
  if(!loot.length){el.innerHTML=`<div class="empty">${t("ro.loot.empty")}</div>`;return;}
  el.innerHTML=loot.map(l=>`
    <div class="ir ${l.for_sale?"sale":""}">
      <div class="im f1">
        <div class="in">${esc(l.name)} <span style="color:var(--t2);font-size:11px">×${l.qty}</span></div>
        <div class="pills">${pillsHTML(l)}${l.for_sale?`<span class="pill p-sale">${t("adm.loot.sale_badge")}</span>`:''}</div>
        ${l.wish_count?`<div class="is">${t("adm.loot.interest",{n:l.wish_count})}</div>`:""}</div>
    </div>`).join("");
}

function renderROComm(){
  const comms=S.commodities||[];
  const el=$("ro-comm-list");
  if(!comms.length){el.innerHTML=`<div class="empty">${t("ro.comm.empty")}</div>`;$("ro-co-sum").innerHTML="";return;}
  el.innerHTML=comms.map(c=>`<div class="ir"><div class="im f1"><div class="in">${esc(c.name)}</div><div class="is">${fmtN(c.scu,1)} SCU</div></div></div>`).join("");
  const sum=S.commodity_summary||{};
  const n=S.participants.length||1;
  const roRev=sum.total_revenue!=null?sum.total_revenue:null;
  const roRevFee=roRev!=null?Math.round(roRev*(1-0.005)):null;
  const roPer=roRevFee!=null?Math.round(Math.round(roRevFee/n)*(1-0.005)):null;
  $("ro-co-sum").innerHTML=`<div class="ct">${t("ro.sum.title")}</div><div class="stats">
    <div class="stat"><div class="sv">${fmtN(sum.total_scu,1)}</div><div class="sl">${t("ro.stat.scu")}</div></div>
    <div class="stat"><div class="sv">${roRevFee!=null?fmtN(roRevFee):"—"}</div><div class="sl">${t("co.sum.net")}</div></div>
    ${roPer!=null?`<div class="stat"><div class="sv">${fmtN(roPer)} aUEC</div><div class="sl">${t("co.sum.per")}</div></div>`:""}
  </div>`;
}

function renderRORes(){
  const el=$("ro-res");
  if(!S.raffle_done||!S.results.length){el.innerHTML=`<div class="empty">${t("ro.res.empty")}</div>`;return;}
  const winners=[...S.results].filter(r=>r.won.length).sort((a,b)=>a.participant_name.localeCompare(b.participant_name,"de"));
  const empty=[...S.results].filter(r=>!r.won.length);
  let html="";
  winners.forEach(r=>{
    const cls=r.won_by_wish?"rr-won":"rr-pool";
    const badge=r.won_by_wish?`<span class="pill p-mil" style="font-size:9px">${t("ra.badge.wish")}</span>`:`<span class="pill p-civ" style="font-size:9px">${t("ra.badge.pool")}</span>`;
    const nc=r.waived?"waiv":r.collected?"coll":"";
    const suf=r.waived?t("ra.status.waived"):"";
    const cstat=r.collected?`<span class="pill p-grade" style="font-size:9px">✓ ABGEHOLT</span>`:`<span class="pill p-gray" style="font-size:9px">○ AUSSTEHEND</span>`;
    const chips=groupedChips(r.won);
    html+=`<div class="rr ${cls} ${r.waived?"rr-waived":""}"><div class="rh">
      <div class="av" style="width:24px;height:24px;font-size:10px">${esc(initials(r.participant_name))}</div>
      <div class="rn ${nc}">${esc(r.participant_name)}${esc(suf)}</div>${badge} ${cstat}</div>
      <div class="rchips">${chips}</div></div>`;
  });
  if(empty.length){
    html+='<div class="divider"></div>';
    empty.forEach(r=>{html+=`<div class="rr rr-none"><div class="rh">
      <div class="av" style="width:24px;height:24px;font-size:10px;opacity:.4">${esc(initials(r.participant_name))}</div>
      <div class="rn" style="color:var(--t2)">${esc(r.participant_name)}</div>
      <span class="pill p-gray" style="font-size:9px">${t("ra.badge.none")}</span></div></div>`;});
  }
  el.innerHTML=html;
}

// ── ADMIN VIEW ────────────────────────────────────────────────────────────────
function applySessionBg(){
  if(S&&S.image_url){
    document.body.style.backgroundImage=`linear-gradient(180deg,rgba(8,12,16,.93) 0%,rgba(8,12,16,.99) 55%),url('${urlEsc(S.image_url)}')`;
    document.body.style.backgroundSize="cover";
    document.body.style.backgroundPosition="center top";
    document.body.style.backgroundAttachment="fixed";
  } else {
    document.body.style.backgroundImage="";
  }
}

function showAdminView(){
  showPage("pg-admin");show("spill");show("btn-leave");
  applySessionBg();
  saveNavState("admin",myCode,null,null);
  $("spill-name").textContent=S.name;
  $("adm-title").textContent=S.name.toUpperCase();
  $("dj").textContent=S.join_code;$("da").textContent=S.admin_code;
  updOvStats();updLockBtn();updMwAdm();updSubLockBtns();updRevDisplay();
  renderAP();renderAL();renderAC();renderRR();
  aTab("ov");
}

let adminPollTmr=null;
function aTab(t){
  ["ov","pa","lo","co","ra"].forEach(x=>{tog(`at-${x}-c`,x===t);$(`at-${x}`).classList.toggle("active",x===t);});
  if(t==="ra") renderRS();
  // Auto-refresh participants and raffle tabs
  clearInterval(adminPollTmr);
  if(t==="pa"||t==="ra"){
    adminPollTmr=setInterval(async()=>{
      await reloadS();
      if(t==="pa") renderAP();
      if(t==="ra"){ renderRS(); renderRR(); }
    },t==="pa"?4000:6000);
  }
}

function updOvStats(){
  $("ov-p").textContent=S.participants.length;
  $("ov-i").textContent=totalItems(S);
  $("ov-w").textContent=totalWishes(S);
  $("ov-m").textContent=S.max_wishes;
}
function updLockBtn(){
  const lb=$("lock-btn");lb.textContent=S.locked?t("adm.lock.locked"):t("adm.lock.open");
  lb.className=S.locked?"btn btn-sm btn-gold":"btn btn-sm";
}
function updMwAdm(){$("mw-adm").querySelectorAll(".tgl").forEach(b=>{b.className="tgl"+(+b.dataset.v===S.max_wishes?" st":"");});}

async function toggleLock(){
  if(S.locked){
    alert(t("err.event_locked"));
    return;
  }
  if(!confirm(t("confirm.lock"))) return;
  await api(`/api/session/${S.id}/settings`,"PATCH",{code:myCode,locked:true});
  await reloadS();showAdminView();
}
async function setMW(v){await api(`/api/session/${S.id}/settings`,"PATCH",{code:myCode,max_wishes:v});await reloadS();updOvStats();updMwAdm();}
async function reloadS(){S=await api(`/api/session/${myCode}`);}
async function regenCodes(){
  if(!confirm(t("confirm.regen"))) return;
  const r=await api(`/api/session/${S.id}/regenerate_codes`,"POST",{code:myCode});
  if(r.error){alert(r.error);return;}
  myCode=r.admin_code;
  await reloadS();
  saveNavState("admin",myCode,null,null);
  $("dj").textContent=S.join_code;$("da").textContent=S.admin_code;
}
function cpCode(w){cpText(w==="admin"?S.admin_code:S.join_code);}

// participants
function renderAP(){
  const el=$("adm-p-list");
  if(!S.participants.length){el.innerHTML=`<div class="empty">${t("pa.empty")}</div>`;return;}
  el.innerHTML=[...S.participants].sort((a,b)=>a.name.localeCompare(b.name,"de")).map(p=>{
    const wn=(p.wishes||[]).map(id=>{const l=S.loot.find(x=>x.id===id);return l?esc(l.name):null;}).filter(Boolean);
    const pc=p.pcode?`<button class="btn btn-xs" title="${t("pa.pcode_tip")}" onclick="copyPcode('${p.id}')">🔑</button>`:"";
    return `<div class="ir">
      <div class="av">${esc(initials(p.name))}</div>
      <div class="im f1"><div class="in">${esc(p.name)}</div>
        <div class="is">${wn.length?"🎯 "+wn.join(" · "):t("pa.no_wishes")}</div></div>
      ${pc}
      ${S.locked?"":
        `<button class="btn btn-xs btn-acc" onclick="openWishEdit('${p.id}')">${t("pa.btn.wishes")}</button>
         <button class="btn btn-xs btn-red" onclick="removeP('${p.id}')">✕</button>`}
    </div>`;
  }).join("");
}

async function addP(){
  const names=$("p-inp").value.split(",").map(n=>n.trim()).filter(Boolean);if(!names.length) return;
  for(const n of names) await api(`/api/session/${S.id}/participants`,"POST",{code:myCode,name:n,added_by:"admin"});
  $("p-inp").value="";acClose("p-ac");await reloadS();renderAP();updOvStats();
}
function copyPcode(pid){
  const p=S.participants.find(x=>x.id===pid);
  if(!p||!p.pcode) return;
  navigator.clipboard&&navigator.clipboard.writeText(p.pcode);
  alert(t("pa.pcode_copied",{name:p.name}));
}
async function removeP(pid){
  if(!confirm(t("pt.del_confirm"))) return;
  await api(`/api/session/${S.id}/participants/${pid}`,"DELETE");
  await reloadS();renderAP();updOvStats();
}
async function acP(q){
  if(!q){acClose("p-ac");return;}clearTimeout(acTmr);
  acTmr=setTimeout(async()=>{const r=await api(`/api/participants/search?q=${encodeURIComponent(q)}`);acRender("p-ac",r,n=>{$("p-inp").value=n;acClose("p-ac");});},180);
}

function openWishEdit(pid){
  const p=S.participants.find(x=>x.id===pid);if(!p) return;
  const sel=new Set(p.wishes||[]);
  const modal=document.createElement("div");
  modal.style.cssText="position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1000;display:flex;align-items:center;justify-content:center";
  const box=document.createElement("div");
  const _z=parseFloat(document.body.style.zoom||"1");
  box.style.cssText=`background:var(--bg2);border:1px solid var(--bdr2);border-radius:var(--r2);padding:20px;width:440px;max-width:96vw;max-height:${Math.floor(88/_z)}vh;overflow-y:auto;display:flex;flex-direction:column`;
  const lootAvail=[...S.loot].filter(l=>!l.for_sale).sort((a,b)=>a.name.localeCompare(b.name,"de"));
  box.innerHTML=`<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
    <div style="font-family:monospace;font-size:12px;font-weight:700;color:var(--acc)">${esc(p.name.toUpperCase())} — ${t("pa.btn.wishes").toUpperCase()}</div>
    <button class="btn btn-xs btn-red" id="close-we">✕</button></div>
  <div id="we-items">${lootAvail.length?lootAvail.map(l=>`
    <div class="wi ${sel.has(l.id)?"sel-w":""}" data-lid="${l.id}" onclick="weToggle(this,'${l.id}')">
      <input type="checkbox" class="wcb" ${sel.has(l.id)?"checked":""} onclick="event.stopPropagation();weToggle(this.closest('.wi'),'${l.id}')"/>
      <div><div style="font-weight:600;font-size:13px">${esc(l.name)} <span style="color:var(--t2);font-size:11px">×${l.qty}</span></div>
        <div class="pills">${pillsHTML(l)}</div></div></div>`).join("")
    :`<div class="empty">${t("we.no_loot")}</div>`}</div>
  <button class="btn btn-acc btn-full mt8" id="save-we">✓ Speichern</button>`;
  modal.appendChild(box);document.body.appendChild(modal);
  let cur=new Set(sel);
  window.weToggle=(el,lid)=>{
    if(cur.has(lid)){cur.delete(lid);el.classList.remove("sel-w");el.querySelector(".wcb").checked=false;}
    else{cur.add(lid);el.classList.add("sel-w");el.querySelector(".wcb").checked=true;}
  };
  const _iEl=box.querySelector("#we-items");const _sw=document.createElement("div");_sw.style.cssText="overflow-y:auto;flex:1;min-height:60px";box.insertBefore(_sw,_iEl);_sw.appendChild(_iEl);box.querySelector("#save-we").style.flexShrink="0";
  $("close-we").onclick=()=>modal.remove();
  $("save-we").onclick=async()=>{
    await api(`/api/session/${S.id}/wishes`,"POST",{code:myCode,participant_id:pid,loot_ids:[...cur],mode:"wish"});
    modal.remove();await reloadS();renderAP();
  };
}

function openInterestEdit(lid){
  const l=S.loot.find(x=>x.id===lid); if(!l) return;
  const interested=new Set(S.participants.filter(p=>(p.wishes||[]).includes(lid)).map(p=>p.id));
  const modal=document.createElement("div");
  modal.style.cssText="position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:1000;display:flex;align-items:center;justify-content:center";
  const box=document.createElement("div");
  box.style.cssText="background:var(--bg2);border:1px solid var(--bdr2);border-radius:var(--r2);padding:20px;width:440px;max-width:96vw;max-height:82vh;overflow-y:auto";
  box.innerHTML=`<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
    <div style="font-family:monospace;font-size:12px;font-weight:700;color:var(--acc)">${esc(l.name.toUpperCase())} — INTERESSE</div>
    <button class="btn btn-xs btn-red" id="close-ie">✕</button></div>
  <div class="alert a-info mb8" style="font-size:11px">${t("lo.btn.interest")} — wähle Teilnehmer</div>
  <div id="ie-items">${S.participants.length?[...S.participants].sort((a,b)=>a.name.localeCompare(b.name,"de")).map(p=>`
    <div class="wi ${interested.has(p.id)?"sel-w":""}" data-pid="${p.id}" onclick="ieToggle(this,'${p.id}')">
      <input type="checkbox" class="wcb" ${interested.has(p.id)?"checked":""} onclick="event.stopPropagation();ieToggle(this.closest('.wi'),'${p.id}')"/>
      <div style="font-weight:600;font-size:13px">${esc(p.name)}</div>
    </div>`).join("")
    :`<div class="empty">${t("sa.empty.participants")}</div>`}</div>
  <button class="btn btn-acc btn-full mt8" id="save-ie">✓ Speichern</button>`;
  modal.appendChild(box);document.body.appendChild(modal);
  let cur=new Set(interested);
  window.ieToggle=(el,pid)=>{
    if(cur.has(pid)){cur.delete(pid);el.classList.remove("sel-w");el.querySelector(".wcb").checked=false;}
    else{cur.add(pid);el.classList.add("sel-w");el.querySelector(".wcb").checked=true;}
  };
  $("close-ie").onclick=()=>modal.remove();
  $("save-ie").onclick=async()=>{
    // For each participant, update their wishes accordingly
    for(const p of S.participants){
      const wishes=new Set(p.wishes||[]);
      const hadIt=wishes.has(lid), wantsIt=cur.has(p.id);
      if(hadIt===wantsIt) continue;
      if(wantsIt) wishes.add(lid); else wishes.delete(lid);
      await api(`/api/session/${S.id}/wishes`,"POST",{code:myCode,participant_id:p.id,loot_ids:[...wishes],mode:"wish"});
    }
    modal.remove();await reloadS();renderAL();renderAP();
  };
}

// loot
let acItemsRaw=[], selCat="item", selWSz="1";
function sCat(btn){
  $("cat-grp").querySelectorAll(".tgl").forEach(b=>b.className="tgl");
  selCat=btn.dataset.v;
  btn.classList.add(selCat==="item"?"si":"st");
  tog("cat-weapon-f",selCat==="weapon"); tog("cat-comp-f",selCat==="comp");
}
function sWSz(btn){$("sw-sz-grp").querySelectorAll(".tgl").forEach(b=>b.className="tgl");selWSz=btn.dataset.v;btn.classList.add("ss");}
function sT(btn){$("ty-grp").querySelectorAll(".tgl").forEach(b=>b.className="tgl");selT=btn.dataset.v;btn.classList.add("st");}
function sG(btn){$("gr-grp").querySelectorAll(".tgl").forEach(b=>b.className="tgl");selG=btn.dataset.v;btn.classList.add("sg");}
function sS(btn){$("sz-grp").querySelectorAll(".tgl").forEach(b=>b.className="tgl");selSz=btn.dataset.v;btn.classList.add("ss");}

function renderAL(){
  const el=$("adm-l-list");
  if(!S.loot.length){el.innerHTML=`<div class="empty">${t("lo.empty")}</div>`;return;}
  el.innerHTML=[...S.loot].sort((a,b)=>a.name.localeCompare(b.name,"de")).map(l=>`
    <div class="ir ${l.for_sale?"sale":""}">
      <div class="im f1">
        <div class="in">${esc(l.name)} <span style="color:var(--t2);font-size:11px">×${l.qty}</span></div>
        <div class="pills">${pillsHTML(l)}${l.for_sale?`<span class="pill p-sale">${t("adm.loot.sale_badge")}</span>`:''}</div>
        ${l.wish_count&&!l.for_sale?`<div class="is">${t("adm.loot.interest",{n:l.wish_count})}</div>`:""}</div>
      <div style="display:flex;gap:3px;align-items:center;flex-wrap:wrap">
        ${S.locked?"":
          `<button class="btn btn-xs" onclick="chQty('${l.id}',-1)">−</button>
           <button class="btn btn-xs" onclick="chQty('${l.id}',1)">+</button>
           ${!l.for_sale?`<button class="btn btn-xs btn-acc" onclick="openInterestEdit('${l.id}')">${t("lo.btn.interest")}</button>`:""}
           <button class="btn btn-xs ${l.for_sale?"btn-grn":"btn-amb"}" onclick="togSale('${l.id}',${!l.for_sale})">${l.for_sale?t("lo.btn.unsale"):t("lo.btn.sale")}</button>
           ${l.for_sale?`<input type="number" placeholder="${t('co.rev.total.unit')}" value="${l.sale_revenue!=null?l.sale_revenue:""}" style="width:120px" onchange="updSaleRev('${l.id}',this.value)"/>`:""}
           <button class="btn btn-xs btn-red" onclick="removeL('${l.id}')">✕</button>`}
      </div>
    </div>`).join("");
}

async function addL(){
  const name=$("l-nm").value.trim();if(!name) return;
  const qty=Math.max(1,+$("l-qty").value||1);
  // Use stored DB properties if item is known; otherwise use form selection
  const dbItem=acItemsRaw.find(x=>x.name.toLowerCase()===name.toLowerCase());
  let typ,grade,size;
  if(dbItem){
    typ=dbItem.type||null;
    grade=dbItem.grade||null;
    size=dbItem.size!=null?String(dbItem.size):null;
  } else {
    if(selCat==="weapon"){typ=null;grade=null;size=selWSz;}
    else if(selCat==="comp"){typ=selT;grade=selG;size=selSz;}
    else{typ=null;grade=null;size=null;}
  }
  await api(`/api/session/${S.id}/loot`,"POST",{code:myCode,name,qty,type:typ,grade,size});
  $("l-nm").value="";$("l-qty").value="1";acClose("l-ac");
  await reloadS();renderAL();updOvStats();
}
async function chQty(lid,d){await api(`/api/session/${S.id}/loot/${lid}/qty`,"PATCH",{code:myCode,delta:d});await reloadS();renderAL();updOvStats();}
async function removeL(lid){await api(`/api/session/${S.id}/loot/${lid}`,"DELETE");await reloadS();renderAL();updOvStats();}
async function togSale(lid,fs){
  if(fs&&!confirm(t("confirm.sale"))) return;
  await api(`/api/session/${S.id}/loot/${lid}/sale`,"PATCH",{code:myCode,for_sale:fs});
  await reloadS();renderAL();updOvStats();renderAC();
}
async function updSaleRev(lid,val){
  await api(`/api/session/${S.id}/loot/${lid}/sale`,"PATCH",{code:myCode,sale_revenue:val===""?null:parseFloat(val)});
  await reloadS();renderCoSum();
}
async function acL(q){
  if(!q){acClose("l-ac");return;}clearTimeout(acTmr);
  acTmr=setTimeout(async()=>{
    acItemsRaw=await api(`/api/items/search?q=${encodeURIComponent(q)}`);
    acRender("l-ac",acItemsRaw.map(x=>x.name),async nm=>{
      // Just set name and submit — properties come from DB via addL()
      $("l-nm").value=nm;
      acClose("l-ac");
      await addL();
    });
  },180);
}

// commodities
function renderAC(){
  const el=$("adm-c-list");
  if(!S.commodities||!S.commodities.length){el.innerHTML=`<div class="empty">${t("co.empty")}</div>`;renderCoSum();return;}
  el.innerHTML='<div class="list">'+S.commodities.map(c=>`
    <div class="ir">
      <div class="im f1"><div class="in">${esc(c.name)}</div>
        <div class="is">${fmtN(c.scu,1)} SCU</div></div>
      ${S.locked?"":
        `<button class="btn btn-xs" onclick="chCom('${c.id}',-1)">−</button>
         <button class="btn btn-xs" onclick="chCom('${c.id}',1)">+</button>
         <input type="number" value="${c.scu}" step="0.1" min="0" style="width:80px" onchange="setCom('${c.id}',this.value)"/>
         <button class="btn btn-xs btn-red" onclick="delCom('${c.id}')">✕</button>`}
    </div>`).join("")+'</div>';
  // set revenue input
  const rv=S.total_revenue;
  // revenue display updated by updRevDisplay()
  renderCoSum();
}

function applyFee(v){ return Math.round(v*(1-0.005)); }
function renderCoSum(){
  const comms=S.commodities||[];
  const n=S.participants.length||1;
  const totalScu=comms.reduce((a,c)=>a+c.scu,0);
  const saleRev=(S.loot||[]).filter(l=>l.for_sale&&l.sale_revenue!=null).reduce((a,l)=>a+(l.sale_revenue||0),0);
  const baseRev=S.total_revenue||0;
  const totalRevBefore=baseRev+saleRev;
  const hasRev=baseRev>0||saleRev>0;
  const totalRevAfterFee=hasRev?applyFee(totalRevBefore):0;
  const saleRevAfterFee=saleRev>0?applyFee(saleRev):0;
  const perPerson=hasRev?applyFee(Math.round(totalRevAfterFee/n)):0;
  $("co-summary").innerHTML=`<div class="stats">
    <div class="stat"><div class="sv">${fmtN(totalScu,1)}</div><div class="sl">${t("ro.stat.scu")}</div></div>
    <div class="stat">
      <div class="sv">${hasRev?fmtN(totalRevAfterFee):"—"}</div>
      <div class="sl">${t("co.sum.net")}</div>
      ${hasRev?`<div style="font-family:monospace;font-size:9px;color:var(--t2);margin-top:2px">${t("co.rev.before_fee")}: ${fmtN(totalRevBefore)} · ${t("co.rev.fee")} = ${fmtN(totalRevBefore-totalRevAfterFee)}</div>`:""}
    </div>
    ${saleRev>0?`<div class="stat"><div class="sv">${fmtN(saleRevAfterFee)}</div><div class="sl">${t("co.sum.sale")}</div></div>`:""}
    <div class="stat">
      <div class="sv">${hasRev?fmtN(perPerson)+" aUEC":"—"}</div>
      <div class="sl">${t("co.sum.per")}</div>
    </div>
  </div>`;
}

async function addCom(){
  const name=$("co-nm").value.trim();if(!name) return;
  const scu=parseFloat($("co-scu").value)||0;
  await api(`/api/session/${S.id}/commodities`,"POST",{code:myCode,name,scu});
  $("co-nm").value="";$("co-scu").value="";acClose("co-ac");
  await reloadS();renderAC();
}
async function chCom(cid,d){await api(`/api/session/${S.id}/commodities/${cid}/qty`,"PATCH",{code:myCode,delta:d});await reloadS();renderAC();}
async function setCom(cid,val){await api(`/api/session/${S.id}/commodities/${cid}`,"PATCH",{code:myCode,scu:parseFloat(val)||0});await reloadS();renderAC();}
async function delCom(cid){await api(`/api/session/${S.id}/commodities/${cid}`,"DELETE");await reloadS();renderAC();}
async function acCo(q){
  if(!q){acClose("co-ac");return;}clearTimeout(acTmr);
  acTmr=setTimeout(async()=>{
    const r=await api(`/api/commodities/search?q=${encodeURIComponent(q)}`);
    acRender("co-ac",r,async n=>{$("co-nm").value=n;acClose("co-ac");await addCom();});
  },180);
}

// raffle
function renderRS(){
  $("r-p").textContent=S.participants.length;
  $("r-i").textContent=totalItems(S);
  $("r-w").textContent=totalWishes(S);
  const ti=totalItems(S),np=S.participants.length;
  const modeWarn=$("raffle-mode-info");
  if(ti>0&&np>0&&ti<np){
    modeWarn.textContent=t("pt.ni.inline",{items:ti,participants:np});
    show("raffle-mode-info");
  } else hide("raffle-mode-info");
}

async function runRaffle(){
  if(!confirm(t("confirm.raffle"))) return;
  const r=await api(`/api/session/${S.id}/raffle`,"POST",{code:myCode});
  if(r.error){alert(r.error);return;}
  await reloadS();renderRR();$("raffle-btn").textContent=t("ra.btn.restart");
}

function renderRR(){
  const el=$("raffle-res");
  if(!S.raffle_done||!S.results.length){el.innerHTML=`<div class="empty">${t("ra.empty")}</div>`;$("raffle-btn").textContent=t("ra.btn.start");return;}
  $("raffle-btn").textContent=t("ra.btn.restart");
  const winners=[...S.results].filter(r=>r.won.length).sort((a,b)=>a.participant_name.localeCompare(b.participant_name,"de"));
  const empty=[...S.results].filter(r=>!r.won.length).sort((a,b)=>a.participant_name.localeCompare(b.participant_name,"de"));
  let html="";
  winners.forEach(r=>{
    const cls=r.won_by_wish?"rr-won":"rr-pool";
    const badge=r.won_by_wish?`<span class="pill p-mil" style="font-size:9px">${t("ra.badge.wish")}</span>`:`<span class="pill p-civ" style="font-size:9px">${t("ra.badge.pool")}</span>`;
    const nc=r.waived?"waiv":r.collected?"coll":"";
    const suf=r.waived?t("ra.status.waived_short"):"";
    const chips=groupedChips(r.won);
    html+=`<div class="rr ${cls} ${r.waived?"rr-waived":""}"><div class="rh">
      <div class="av" style="width:24px;height:24px;font-size:10px">${esc(initials(r.participant_name))}</div>
      <div class="rn ${nc}">${esc(r.participant_name)}${esc(suf)}</div>${badge}
      ${S.locked?"":r.waived
        ?`<button class="btn btn-xs btn-acc" onclick="togWaive('${r.id}',false)">${t("ra.btn.unwaive")}</button>`
        :`<button class="btn btn-xs btn-red" onclick="togWaive('${r.id}',true)">${t("ra.btn.waive")}</button>`}
      ${S.locked||r.waived?"":r.collected
        ?`<button class="btn btn-xs btn-grn" onclick="togColl('${r.id}',false)">${t("ra.btn.collected")}</button>`
        :`<button class="btn btn-xs" onclick="togColl('${r.id}',true)">${t("ra.btn.uncollected")}</button>`}
    </div><div class="rchips">${chips}</div></div>`;
  });
  if(empty.length){
    html+='<div class="divider"></div>';
    empty.forEach(r=>{html+=`<div class="rr rr-none"><div class="rh">
      <div class="av" style="width:24px;height:24px;font-size:10px;opacity:.4">${esc(initials(r.participant_name))}</div>
      <div class="rn" style="color:var(--t2)">${esc(r.participant_name)}</div>
      <span class="pill p-gray" style="font-size:9px">${t("ra.badge.none")}</span></div></div>`;});
  }
  el.innerHTML=html;
}

async function togWaive(rid,v){await api(`/api/session/${S.id}/raffle/${rid}`,"PATCH",{code:myCode,waived:v});await reloadS();renderRR();}
async function togColl(rid,v){await api(`/api/session/${S.id}/raffle/${rid}`,"PATCH",{code:myCode,collected:v});await reloadS();renderRR();}

function exportTxt(){
  if(!S.results||!S.results.length){alert(t("ra.empty2"));return;}
  let txt=`SCLM — Star Citizen Loot Manager\n${S.name}\n${"-".repeat(40)}\n\n`;
  S.results.filter(r=>r.won.length).sort((a,b)=>a.participant_name.localeCompare(b.participant_name,"de")).forEach(r=>{
    txt+=`${r.participant_name}${r.waived?t("ra.export.waived"):""}:\n`;
    const wm=new Map();r.won.forEach(w=>{const k=`${w.name}||${w.type||''}||${w.grade||''}||${w.size||''}`;if(!wm.has(k))wm.set(k,{w,n:0});wm.get(k).n++;});wm.forEach(({w,n})=>{let d=w.name;if(w.type)d+=` | ${w.type}`;if(w.grade)d+=` GR-${w.grade}`;if(w.size)d+=` S${w.size}`;if(n>1)d+=` ×${n}`;txt+=`  • ${d}\n`;});
    txt+="\n";
  });
  const a=document.createElement("a");a.href="data:text/plain;charset=utf-8,"+encodeURIComponent(txt);a.download=`raffle_${S.name.replace(/\s+/g,"_")}.txt`;a.click();
}

// ── PARTICIPANT VIEW ──────────────────────────────────────────────────────────
// ── UI Scale ──────────────────────────────────────────────────────────────────
function setScale(v){
  v=Math.round(parseFloat(v)*100)/100;
  document.body.style.zoom=v;
  try{localStorage.setItem('scr_scale',v);}catch(e){}
}
// Restore saved scale on load
(function(){
  try{
    const s=localStorage.getItem('scr_scale');
    if(s){
      const v=parseFloat(s);
      document.body.style.zoom=v;
      // Slider may not exist yet at this point — set after DOM ready
      window.addEventListener('DOMContentLoaded',()=>{
        const sl=document.getElementById('scale-slider');
        if(sl) sl.value=v;
      });
    }
  }catch(e){}
})();

const SK=()=>`scr_pid_${S&&S.id}`;
function loadPcode(pid){try{const v=JSON.parse(localStorage.getItem(SK())||"{}");return (v&&v.pid===pid)?(v.pcode||""):"";}catch(e){return "";}}

function showPartView(){
  showPage("pg-part");show("spill");show("btn-leave");
  applySessionBg();
  saveNavState("part",myCode,myPid,myPName);
  $("spill-name").textContent=S.name;$("pt-title").textContent=S.name.toUpperCase();
  hide("pt-wish");hide("pt-wait");hide("pt-result");show("pt-sel");renderPtList();
  const saved=localStorage.getItem(SK());
  if(saved){try{const{pid,name,pcode}=JSON.parse(saved);const f=S.participants.find(p=>p.id===pid);if(f){selectParticipantById(pid,name,pcode);return;}}catch(e){}}
}

function renderPtList(){
  const el=$("pt-nm-list");
  if(!S.participants.length){el.innerHTML=`<div class="empty">${t("pt.sel.empty")}</div>`;return;}
  el.innerHTML=[...S.participants].sort((a,b)=>a.name.localeCompare(b.name,"de")).map(p=>`
    <div class="ir" style="cursor:pointer" data-pid="${esc(p.id)}" onclick="selectParticipant(this.dataset.pid)">
      <div class="av">${esc(initials(p.name))}</div>
      <div class="in f1">${esc(p.name)}</div>
      <span style="color:var(--t2);font-size:11px">→</span>
    </div>`).join("");
}

async function selfReg(){
  const name=$("pt-nm-inp").value.trim();if(!name) return;
  const r=await api(`/api/session/${S.id}/participants`,"POST",{code:myCode,name,added_by:"self"});
  if(r.error&&r.id){selectParticipantById(r.id,name);return;}
  if(r.error){const f=S.participants.find(p=>p.name.toLowerCase()===name.toLowerCase());if(f){selectParticipantById(f.id,f.name);return;}alert(r.error);return;}
  await reloadS();selectParticipantById(r.id,name,r.pcode);
}

function selectParticipantById(pid,name,pcode){
  myPid=pid;myPName=name;
  if(!pcode){
    // Legacy/Admin-angelegter Teilnehmer ohne gespeicherten Key: einmalig generieren
    // und lokal binden — der Server claimed pcode-NULL beim ersten Save (first-come).
    pcode=loadPcode(pid)||(crypto.randomUUID?crypto.randomUUID().replace(/-/g,""):Math.random().toString(36).slice(2)+Date.now().toString(36));
  }
  myPcode=pcode;
  localStorage.setItem(SK(),JSON.stringify({pid,name,pcode}));
  saveNavState("part",myCode,pid,name);
  hide("pt-sel");$("pt-id-bar").textContent=t("pt.logged_in_as",{name:name});
  if(S.raffle_done) showPtResult();
  else if(S.locked) showPtWaiting();
  else {
    // If participant already has wishes saved, go to waiting page
    const p=S.participants.find(x=>x.id===myPid);
    const hasWishes=p&&((p.wishes||[]).length>0||(p.no_interest||[]).length>0);
    if(hasWishes) showPtWaiting();
    else showPtWishes();
  }
}

function selectParticipant(pid){
  const p=S.participants.find(x=>x.id===pid);
  const savedPcode=loadPcode(pid);
  selectParticipantById(pid, p?p.name:pid, savedPcode);
}

function showPtWishes(){
  hide("pt-wait");hide("pt-result");show("pt-wish");renderPtWishes();
}

function renderPtWishes(){
  const p=S.participants.find(x=>x.id===myPid);
  const ti=totalItems(S),np=S.participants.length;
  const niMode=ti>0&&np>0&&ti<np;
  // In no-interest mode: selection = items you DON'T want
  const selIds=new Set(niMode?(p?p.no_interest||[]:[]):(p?p.wishes||[]:[]) );
  const maxW=S.max_wishes,used=selIds.size;

  tog("pt-lock-warn",S.locked);$("save-w-btn").disabled=!!S.locked;

  // mode info
  const mi=$("pt-mode-info");
  if(niMode){
    // Clear any wishes saved in wish-mode when switching to no-interest
    const _p2=S.participants.find(x=>x.id===myPid);
    if(_p2&&(_p2.wishes||[]).length>0){_p2.wishes=[];}
    mi.innerHTML=`<strong>${t("ni.warning.title")}</strong><br>${t("ni.warning.body",{items:totalItems(S),participants:S.participants.length})}`;
    mi.style.cssText="background:rgba(231,76,60,.15);border-color:rgba(231,76,60,.5);color:var(--red);padding:10px 13px;border-radius:4px;border:1px solid;font-size:12px;margin-bottom:10px;line-height:1.6";
    show("pt-mode-info");
  } else { hide("pt-mode-info"); mi.removeAttribute("style"); }

  // quota bar (only in wish mode)
  if(!niMode){
    let qhtml="";for(let i=0;i<maxW;i++) qhtml+='<div class="qpip '+(i<used?"used":"")+'" ></div>';
    qhtml+=`<span class="qtxt">${used}/${maxW} ${t("ra.stat.wishes")}</span>`;
    $("qbar").innerHTML=qhtml;show("qbar");
  } else {
    $("qbar").innerHTML=`<span class="qtxt">${t("pt.ni.inline",{items:used,participants:S.participants.length})}</span>`;
  }

  const el=$("pt-w-list");
  const lootAvail=[...S.loot].filter(l=>!l.for_sale).sort((a,b)=>a.name.localeCompare(b.name,"de"));
  if(!lootAvail.length){el.innerHTML=`<div class="empty">${t("pt.wish.empty")}</div>`;return;}
  el.innerHTML=lootAvail.map(l=>{
    const s=selIds.has(l.id);
    const cls=niMode?(s?"sel-ni":""):(s?"sel-w":"");
    const cbCls=niMode?"ni wcb":"wcb";
    const lbl=niMode?(s?t("pt.ni.no"):t("pt.ni.yes")):"";
    return `<div class="wi ${cls}" onclick="ptTogW('${l.id}',${maxW},${niMode})">
      <input type="checkbox" class="${cbCls}" ${s?"checked":""} onclick="event.stopPropagation();ptTogW('${l.id}',${maxW},${niMode})"/>
      <div style="flex:1"><div style="font-weight:600;font-size:13px">${esc(l.name)} <span style="color:var(--t2);font-size:11px">×${l.qty}</span></div>
        <div class="pills">${pillsHTML(l)}</div></div>
      ${niMode?`<span style="font-size:10px;color:${s?"var(--red)":"var(--grn)"};font-family:monospace">${lbl}</span>`:""}</div>`;
  }).join("");
}

function ptTogW(lid,maxW,niMode){
  const p=S.participants.find(x=>x.id===myPid);if(!p) return;
  if(niMode){
    if(!p.no_interest) p.no_interest=[];
    const idx=p.no_interest.indexOf(lid);
    if(idx>=0) p.no_interest.splice(idx,1);else p.no_interest.push(lid);
  } else {
    if(!p.wishes) p.wishes=[];
    const idx=p.wishes.indexOf(lid);
    if(idx>=0) p.wishes.splice(idx,1);
    else{if(p.wishes.length>=maxW){alert(`${t("pt.wish.save")} — max ${maxW}`);return;}p.wishes.push(lid);}
  }
  renderPtWishes();
}

async function saveWishes(){
  const p=S.participants.find(x=>x.id===myPid);
  const ti=totalItems(S),np=S.participants.length;
  const niMode=ti>0&&np>0&&ti<np;
  const lids=p?(niMode?(p.no_interest||[]):(p.wishes||[])):[];
  const r=await api(`/api/session/${S.id}/wishes`,"POST",{code:myCode,pcode:myPcode,participant_id:myPid,loot_ids:lids,mode:niMode?"no_interest":"wish"});
  if(r.error){alert(r.error);return;}
  await reloadS();showPtWaiting();
}

function showPtWaiting(){hide("pt-wish");hide("pt-result");show("pt-wait");renderWaitSelection();startPoll();}

function showPtResult(){
  hide("pt-wish");hide("pt-wait");show("pt-result");stopPoll();renderPtResult();
}

async function renderPtResult(){
  const r=await api(`/api/session/${S.id}/raffle/result_for/${myPid}`);
  if(!r.result){$("pt-res-content").innerHTML=`<div class="empty">${t("pt.result.empty2")}</div>`;return;}
  const res=r.result,won=res.won||[];
  if(!won.length){$("pt-res-content").innerHTML=`<div class="empty">${t("pt.result.empty")}</div>`;return;}
  const chips=groupedChips(won);
  const badge=res.won_by_wish?`<span class="pill p-mil">${t("pt.result.wish_badge")}</span>`:`<span class="pill p-civ">${t("pt.result.pool_badge")}</span>`;
  const coll=res.collected?`<span class="pill p-grade">${t("pt.result.collected_badge")}</span>`:`<span class="pill p-gray">${t("pt.result.pending_badge")}</span>`;
  const waiv=res.waived?`<span class="pill" style="background:var(--rdim);color:var(--red);border:1px solid rgba(231,76,60,.3)">${t("ra.status.waived_short").trim()}</span>`:"";
  // Self-action buttons (one-way — only set, not unset)
  const collBtn=(!res.collected&&!res.waived)?`<button class="btn btn-xs btn-grn mt8" onclick="ptSelfMark('${res.id}','collected')">${t("pt.result.btn.collect")}</button>`:"";
  const waivBtn=(!res.waived&&!res.collected)?`<button class="btn btn-xs btn-red mt8" style="margin-left:6px" onclick="ptSelfMarkWaive('${res.id}')">${t("pt.result.btn.waive")}</button>`:"";
  $("pt-res-content").innerHTML=`<div class="rr rr-won">
    <div class="rh">${badge} ${coll} ${waiv}</div>
    <div class="rchips mt8">${chips}</div>
    <div class="mt8">${collBtn}${waivBtn}</div>
  </div>`;
}

async function ptSelfMark(rid,field){
  const r=await api(`/api/session/${S.id}/raffle/${rid}`,"PATCH",{code:myCode,pcode:myPcode,[field]:true});
  if(r.error){alert(r.error);return;}
  await reloadS();renderPtResult();
}
async function ptSelfMarkWaive(rid){
  if(!confirm(t("confirm.waive"))) return;
  ptSelfMark(rid,"waived");
}
function ptReload(){reloadS().then(()=>{if(S.raffle_done)showPtResult();else renderPtWishes();});}
function startPoll(){stopPoll();pollTmr=setInterval(async()=>{await reloadS();if(S.raffle_done)showPtResult();else{renderPtWishes();renderWaitSelection();}},8000);}
function stopPoll(){clearInterval(pollTmr);pollTmr=null;}

async function acPt(q){
  if(!q){acClose("pt-nm-ac");return;}clearTimeout(acTmr);
  acTmr=setTimeout(async()=>{const r=await api(`/api/participants/search?q=${encodeURIComponent(q)}`);acRender("pt-nm-ac",r,n=>{$("pt-nm-inp").value=n;acClose("pt-nm-ac");});},180);
}

// ── SUPER ADMIN ───────────────────────────────────────────────────────────────
async function loadSuperAdmin(){
  // Always verify before showing — prevents direct URL hash access
  const r=await api("/api/admin/verify","POST",{secret:superSecret});
  if(r.error){
    superSecret="";
    alert(t("adm.err.access_denied"));
    clearNavState();loadHome();return;
  }
  showPage("pg-super");stopPoll();clearNavState();saveNavState("super","","","");saTab("ev");
}

function saTab(t){
  ["ev","it","pn","co","uex","set"].forEach(x=>{tog(`st-${x}-c`,x===t);$(`st-${x}`).classList.toggle("active",x===t);});
  if(t==="ev") loadSaEvents();
  if(t==="it") loadSaItems();
  if(t==="pn") loadSaPn();
  if(t==="co") loadSaCo();
}

async function loadSaEvents(){
  const list=await api("/api/sessions");
  const el=$("sa-ev-list");
  if(!list.length){el.innerHTML=`<div class="empty">${t("sa.empty.events")}</div>`;return;}
  el.innerHTML=list.map(s=>`<div class="ir" style="flex-wrap:wrap">
    <div class="im f1">
      <div class="in">${esc(s.name)} ${s.locked?'<span class="pill p-grade">🔒</span>':''} ${s.raffle_done?'<span class="pill p-civ">✓</span>':''}</div>
      <div class="is">${s.created} · 👥${s.participant_count} · 📦${s.loot_count}</div>
      <div class="is" style="margin-top:2px">${t("sa.ev.join_label")} <b style="color:var(--acc)">${s.join_code}</b> · Admin: <b style="color:var(--gold)">${s.admin_code||"—"}</b></div>
    </div>
    <div style="display:flex;gap:4px;flex-wrap:wrap">
      <button class="btn btn-xs btn-acc" onclick="saOpenAdmin('${s.admin_code}')">✎ Öffnen</button>
      <button class="btn btn-xs btn-gold" onclick="saTogLock('${s.id}','${s.admin_code}',${s.locked})">${s.locked?t("adm.btn.unlock"):t("adm.btn.lock_ev")}</button>
      <button class="btn btn-xs" onclick="openRO('${s.join_code}')">${t("home.ec.view")}</button>
      <button class="btn btn-xs btn-red" onclick="saDelEv('${s.id}')">✕</button>
    </div>
  </div>`).join("");
}

async function saOpenAdmin(ac){myCode=ac;S=await api(`/api/session/${ac}`);showAdminView();}
async function saTogLock(sid,ac,locked){await api(`/api/session/${sid}/settings`,"PATCH",{code:ac,locked:!locked,secret:superSecret});loadSaEvents();}
async function saDelEv(sid){if(!confirm(t("confirm.del_event"))) return;await api(`/api/session/${sid}`,"DELETE");loadSaEvents();}

let saItemsRaw=[];
let saSelCat="item", saSelWSz="1";
function saSCat(btn){
  $("sa-cat-grp").querySelectorAll(".tgl").forEach(b=>b.className="tgl");
  saSelCat=btn.dataset.v;
  const isIt=saSelCat==="item",isW=saSelCat==="weapon",isC=saSelCat==="comp";
  btn.classList.add(isIt?"si":"st");
  tog("sa-weapon-f",isW); tog("sa-comp-f",isC);
}
function saST(btn){$("sa-ty-grp").querySelectorAll(".tgl").forEach(b=>b.className="tgl");saSelT=btn.dataset.v;btn.classList.add("st");}
function saSG(btn){$("sa-gr-grp").querySelectorAll(".tgl").forEach(b=>b.className="tgl");saSelG=btn.dataset.v;btn.classList.add("sg");}
function saSS(btn){$("sa-sz-grp").querySelectorAll(".tgl").forEach(b=>b.className="tgl");saSelSz=btn.dataset.v;btn.classList.add("ss");}
function saSWSz(btn){$("sa-sw-sz-grp").querySelectorAll(".tgl").forEach(b=>b.className="tgl");saSelWSz=btn.dataset.v;btn.classList.add("ss");}

async function loadSaItems(){
  const r=await api("/api/admin/data");saItemsRaw=r.items||[];
  const el=$("sa-it-list");
  if(!saItemsRaw.length){el.innerHTML=`<div class="empty">${t("sa.empty.items")}</div>`;return;}
  el.innerHTML=saItemsRaw.sort((a,b)=>a.name.localeCompare(b.name,"de")).map((i,idx)=>`
    <div class="ir">
      <div class="im f1"><div class="in">${esc(i.name)}</div><div class="pills">${pillsHTML(i)}</div></div>
      <button class="btn btn-xs btn-acc" onclick="saEditItem(${idx})">✎</button>
      <button class="btn btn-xs btn-red" onclick="saDelItem(${idx})">✕</button>
    </div>`).join("");
}
async function saAddItem(){
  const name=$("sa-l-nm").value.trim();if(!name) return;
  let typ=null,grade=null,size=null;
  if(saSelCat==="weapon"){ size=saSelWSz; }
  else if(saSelCat==="comp"){ typ=saSelT; grade=saSelG; size=saSelSz; }
  const pending=saItemsRaw.find(x=>x._pendingDelete);
  if(pending){
    await api(`/api/admin/items/${encodeURIComponent(pending._pendingDelete)}`,"DELETE");
    delete pending._pendingDelete;
  }
  await api("/api/admin/items","POST",{secret:superSecret,name,type:typ,grade,size});
  $("sa-l-nm").value="";loadSaItems();
}
async function saDelItem(idx){
  const item=saItemsRaw[idx]; if(!item) return;
  if(!confirm(t("confirm.del_db_item",{name:item.name}))) return;
  const key=encodeURIComponent(item.loot_key);
  await api(`/api/admin/items/${key}`,"DELETE");
  loadSaItems();
}

function saEditItem(idx){
  const item=saItemsRaw[idx]; if(!item) return;
  $("sa-l-nm").value=item.name;
  const isW=!item.type&&!item.grade&&item.size!=null;
  const isC=!!(item.type||item.grade);
  const catVal=isW?"weapon":isC?"comp":"item";
  const catBtn=[...$("sa-cat-grp").querySelectorAll(".tgl")].find(x=>x.dataset.v===catVal);
  if(catBtn) saSCat(catBtn);
  if(catVal==="weapon"){
    const sz=String(item.size??1);
    const b=[...$("sa-sw-sz-grp").querySelectorAll(".tgl")].find(x=>x.dataset.v===sz);if(b)saSWSz(b);
  } else if(catVal==="comp"){
    if(item.type){const b=[...$("sa-ty-grp").querySelectorAll(".tgl")].find(x=>x.dataset.v===item.type);if(b)saST(b);}
    if(item.grade){const b=[...$("sa-gr-grp").querySelectorAll(".tgl")].find(x=>x.dataset.v===item.grade);if(b)saSG(b);}
    if(item.size!=null){const b=[...$("sa-sz-grp").querySelectorAll(".tgl")].find(x=>x.dataset.v===String(item.size));if(b)saSS(b);}
  }
  saItemsRaw[idx]._pendingDelete=item.loot_key;
  $("sa-l-nm").focus();
  $("sa-l-nm").scrollIntoView({behavior:"smooth"});
}

async function loadSaPn(){
  const r=await api("/api/admin/data");const names=r.participant_names||[];
  const el=$("sa-pn-list");
  if(!names.length){el.innerHTML=`<div class="empty">${t("sa.empty.names")}</div>`;return;}
  el.innerHTML=names.map(n=>`<div class="ir"><div class="in f1">${esc(n)}</div><button class="btn btn-xs btn-red" onclick="saDelPN('${encodeURIComponent(n)}')">✕</button></div>`).join("");
}
async function saAddPN(){const name=$("sa-pn-inp").value.trim();if(!name) return;await api("/api/admin/participants","POST",{secret:superSecret,name});$("sa-pn-inp").value="";loadSaPn();}
async function saDelPN(n){await api(`/api/admin/participants/${n}`,"DELETE");loadSaPn();}

async function loadSaCo(){
  const r=await api("/api/admin/data");const names=r.commodity_names||[];
  const el=$("sa-co-list");
  if(!names.length){el.innerHTML=`<div class="empty">${t("sa.empty.commodities")}</div>`;return;}
  el.innerHTML=names.map(n=>`<div class="ir"><div class="in f1">${esc(n)}</div><button class="btn btn-xs btn-red" onclick="saDelCo('${encodeURIComponent(n)}')">✕</button></div>`).join("");
}
async function saDelCo(n){await api(`/api/admin/commodities/${n}`,"DELETE");loadSaCo();}

async function runUex(){
  const btn=$("uex-btn"),res=$("uex-result");
  btn.disabled=true; btn.textContent=t("uex.running");

  // Category IDs relevant for ship components (79 removed - too much irrelevant data)
  // Cat 32 = ship weapons: size only, no Class/Grade, read size directly from items response
  const CAT_IDS=[19,21,22,23,32,83,86];  // 79=irrelevant, 82=not relevant
  const CAT_SIZE_ONLY=new Set([32]);  // categories where we skip attribute API calls
  const BASE="https://api.uexcorp.uk/2.0";

  // Map UEX attribute values to our internal format
  const TYPE_MAP={"military":"MIL","stealth":"STE","competition":"COM","civilian":"CIV","industrial":"IND"};
  const GRADE_MAP={"a":"A","b":"B","c":"C","d":"D","1":"A","2":"B","3":"C","4":"D"};

  function setStatus(msg,progress){
    res.innerHTML=`<div class="alert a-info" style="font-family:monospace;font-size:11px">
      ${esc(msg)}
      ${progress!=null?`<div style="background:var(--bg4);border-radius:3px;height:4px;margin-top:8px;overflow:hidden">
        <div style="background:var(--acc);height:100%;width:${progress}%;transition:width .3s"></div></div>`:""}
    </div>`;
  }

  try{
    // Step 1: fetch all items per category
    setStatus(t("uex.loading_categories",{n:9}), 0);
    let allItems=[];
    for(let i=0;i<CAT_IDS.length;i++){
      const catId=CAT_IDS[i];
      setStatus(t("uex.loading_category",{i:i+1,n:CAT_IDS.length,id:catId}), Math.round((i/CAT_IDS.length)*40));
      const r=await fetch(`${BASE}/items?id_category=${catId}`);
      if(!r.ok) throw new Error(`Kategorie ${catId}: HTTP ${r.status}`);
      const d=await r.json();
      const items=(d.data||[]).filter(x=>x.id&&x.name);
      allItems=allItems.concat(items.map(x=>({...x,catId})));
      // Small delay to be polite to the API
      await new Promise(r=>setTimeout(r,120));
    }
    setStatus(`${allItems.length} Komponenten gefunden. Lade Details...`, 40);

    // Step 2: fetch attributes for each item
    const results=[];
    for(let i=0;i<allItems.length;i++){
      const item=allItems[i];
      if(i%10===0) setStatus(`Detail ${i+1}/${allItems.length}: ${item.name}`, 40+Math.round((i/allItems.length)*55));
      try{
        // Size is available directly on item object for all categories
        const rawSize=String(item.size||"").trim();
        const itemSize=rawSize.match(/^\d+$/)?rawSize:null;  // "0" is valid

        // For size-only categories (e.g. weapons), skip attribute API calls
        if(CAT_SIZE_ONLY.has(item.catId)){
          results.push({name:item.name,type:null,grade:null,size:itemSize});
          continue;
        }

        const r=await fetch(`${BASE}/items_attributes?id_item=${item.id}`);
        if(!r.ok){ results.push({name:item.name,size:itemSize}); continue; }
        const d=await r.json();
        const attrs=d.data||[];

        // attribute_name variants: t("lo.comp.grade.label")/"Grade Letter", "Class", "Size"
        let type=null, grade=null, size=itemSize;
        for(const a of attrs){
          const attrName=(a.attribute_name||"").trim();
          const val=String(a.value||"").trim();
          if(!val) continue;  // skip empty values

          // Class / type
          if(attrName==="Class"){
            type=TYPE_MAP[val.toLowerCase()]||null;
          }
          // Grade — accept "Grade", "Grade Letter" (not "Grade Numeric")
          if((attrName==="Grade"||attrName==="Grade Letter")&&!attrName.includes("Numeric")){
            if(["A","B","C","D"].includes(val.toUpperCase()))
              grade=val.toUpperCase();
          }
          // Size from attributes (overrides item-level size if present)
          // "0" is a valid SC component size
          if(attrName==="Size"){
            if(/^\d+$/.test(val)) size=val;
          }
        }
        results.push({name:item.name,type,grade,size});
      }catch(e){
        results.push({name:item.name,size:itemSize||null});
      }
      await new Promise(r=>setTimeout(r,80));
    }

    setStatus(t("uex.saving"), 97);
    const r=await api("/api/admin/uex_import","POST",{secret:superSecret,items:results});
    if(r.error) throw new Error(r.error);
    res.innerHTML=`<div class="alert a-ok">${t("uex.done")}<br>
      <span style="font-family:monospace;font-size:11px">
      ${r.added} neu/aktualisiert · ${r.skipped} unverändert · ${r.total} gesamt verarbeitet
      </span></div>`;
  }catch(e){
    res.innerHTML=`<div class="alert a-err">${t("uex.error")}: ${esc(e.message)}<br>
      <span style="font-family:monospace;font-size:10px;color:var(--t2)">
      ${t("sa.uex.network_hint")}
      </span></div>`;
  }
  btn.disabled=false; btn.textContent=t("sa.uex.btn");
}

// ── autocomplete ──────────────────────────────────────────────────────────────
function acRender(dropId,items,onSel){
  const d=$(dropId);if(!d) return;
  if(!items.length){d.classList.remove("open");return;}
  d.innerHTML=items.map(n=>`<div class="aci">${esc(n)}</div>`).join("");
  d.classList.add("open");
  d.querySelectorAll(".aci").forEach((el,i)=>el.addEventListener("mousedown",e=>{e.preventDefault();onSel(items[i]);}));
}
function acClose(id){const d=$(id);if(d)d.classList.remove("open");}
document.addEventListener("click",e=>{if(!e.target.closest(".acw"))["p-ac","l-ac","pt-nm-ac","co-ac"].forEach(acClose);});

// ── session persistence ──────────────────────────────────────────────────────
const SSTATE_KEY="scr_session_state";
function saveNavState(page,code,pid,name){
  sessionStorage.setItem(SSTATE_KEY,JSON.stringify({page,code,pid,name}));
}
function clearNavState(){sessionStorage.removeItem(SSTATE_KEY);}

// ── Change admin password ────────────────────────────────────────────────────
async function changePw(){
  const cur=$("pw-current").value.trim();
  const nw=$("pw-new").value.trim();
  const rep=$("pw-repeat").value.trim();
  const res=$("pw-result");
  if(!cur||!nw||!rep){res.innerHTML='<div class="alert a-err">Alle Felder ausfüllen.</div>';return;}
  if(nw!==rep){res.innerHTML='<div class="alert a-err">Kennwörter stimmen nicht überein.</div>';return;}
  if(nw.length<8){res.innerHTML='<div class="alert a-err">Mindestens 8 Zeichen.</div>';return;}
  const r=await api("/api/admin/change_secret","POST",{secret:cur,new_secret:nw});
  if(r.error){res.innerHTML=`<div class="alert a-err">${esc(r.error)}</div>`;return;}
  superSecret=nw;
  // M4: Secret NIE wieder in die URL schreiben. Nur im JS-Speicher halten.
  $("pw-current").value="";$("pw-new").value="";$("pw-repeat").value="";
  res.innerHTML='<div class="alert a-ok">✓ Kennwort erfolgreich geändert.</div>';
}

// ── About ────────────────────────────────────────────────────────────────────
function showAbout(){
  ["pg-home","pg-admin","pg-part","pg-super","pg-ro"].forEach(p=>{const e=document.getElementById(p);if(e)e.classList.add("H");});
  document.getElementById("pg-about").classList.remove("H");
}

// ── Revenue add/reset ─────────────────────────────────────────────────────────
async function addRevenue(){
  const v=parseFloat(document.getElementById("rev-add-inp").value);
  if(!v||v<=0) return;
  const current=S.total_revenue||0;
  const r=await api(`/api/session/${S.id}/settings`,"PATCH",{code:myCode,total_revenue:current+v});
  if(r.error){alert(r.error);return;}
  document.getElementById("rev-add-inp").value="";
  await reloadS();renderAC();
}
async function resetRevenue(){
  if(!confirm(t("co.rev.btn.reset") + "?")) return;
  await api(`/api/session/${S.id}/settings`,"PATCH",{code:myCode,total_revenue:null});
  await reloadS();renderAC();
}
function updRevDisplay(){
  const el=document.getElementById("rev-total-display");
  if(el) el.textContent=S.total_revenue!=null?fmtN(S.total_revenue):"—";
}

// ── Raffle/Comm lock ──────────────────────────────────────────────────────────
async function toggleRaffleLock(){
  const locked=S.raffle_locked;
  if(!locked&&!confirm(t("confirm.raffle_lock"))) return;
  if(locked&&!confirm(t("confirm.raffle_unlock"))) return;
  await api(`/api/session/${S.id}/settings`,"PATCH",{code:myCode,raffle_locked:!locked});
  await reloadS();showAdminView();
}
async function toggleCommLock(){
  const locked=S.commodities_locked;
  if(!locked&&!confirm(t("confirm.comm_lock"))) return;
  if(locked&&!confirm(t("confirm.comm_unlock"))) return;
  await api(`/api/session/${S.id}/settings`,"PATCH",{code:myCode,commodities_locked:!locked});
  await reloadS();showAdminView();
}
function updSubLockBtns(){
  const rb=document.getElementById("raffle-lock-btn");
  const cb=document.getElementById("comm-lock-btn");
  if(rb){
    rb.classList.toggle("H",!S.raffle_done);
    if(S.raffle_done){
      rb.textContent=S.raffle_locked?t("adm.raffle.locked"):t("adm.raffle.open");
      rb.className=S.raffle_locked?"btn btn-sm btn-gold":"btn btn-sm btn-grn";
    }
  }
  if(cb){
    const hasComm=(S.commodities||[]).length>0||(S.total_revenue!=null);
    cb.classList.toggle("H",!hasComm);
    if(hasComm){
      cb.textContent=S.commodities_locked?t("adm.comm.locked"):t("adm.comm.open");
      cb.className=S.commodities_locked?"btn btn-sm btn-gold":"btn btn-sm btn-grn";
    }
  }
}

// ── Waiting page selection display ────────────────────────────────────────────
function renderWaitSelection(){
  const identEl=document.getElementById("pt-wait-identity");
  if(identEl) identEl.textContent=t("pt.wait.identity",{name:myPName});
  const el=document.getElementById("pt-wait-sel-content");
  if(!el) return;
  const p=S.participants.find(x=>x.id===myPid);
  const ti=totalItems(S),np=S.participants.length;
  const niMode=ti>0&&np>0&&ti<np;
  const selIds=new Set(niMode?(p?p.no_interest||[]:[]):(p?p.wishes||[]:[]) );
  if(!selIds.size){el.innerHTML=`<div class="empty" style="padding:12px">${t("pt.wait.sel.empty")}</div>`;return;}
  const lootItems=S.loot.filter(l=>selIds.has(l.id)&&!l.for_sale).sort((a,b)=>a.name.localeCompare(b.name,"de"));
  if(!lootItems.length){el.innerHTML='<div class="empty" style="padding:12px">Keine Auswahl getroffen.</div>';return;}
  el.innerHTML=lootItems.map(l=>`
    <div class="ir">
      <div class="im f1">
        <div class="in">${esc(l.name)}</div>
        <div class="pills">${pillsHTML(l)}</div>
      </div>
      <span class="pill ${niMode?"p-noint":"p-civ"}" style="font-size:9px">${niMode?t("ni.badge.no"):t("ra.badge.wish")}</span>
    </div>`).join("");
}

// ── i18n integration ──────────────────────────────────────────────────────────

// ── Palette (MFD) ─────────────────────────────────────────────────────────────
// Dezent in der Einstellungs-Ecke (Header); Auswahl persistiert (sclm_palette).
const PALS = ['cargo', 'ion', 'uplink'];
function setPalette(name) {
  if (PALS.indexOf(name) < 0) name = 'ion';
  document.documentElement.setAttribute('data-palette', name);
  try { localStorage.setItem('sclm_palette', name); } catch (_) {}
  const sel = document.getElementById('palette-select');
  if (sel) sel.value = name;
}
function initPalette() {
  let saved = null;
  try { saved = localStorage.getItem('sclm_palette'); } catch (_) {}
  setPalette(saved || 'ion');
  const sel = document.getElementById('palette-select');
  if (sel) {
    const label = (typeof t === 'function') ? t('ui.palette') : 'Farbschema';
    sel.setAttribute('aria-label', label);
    const wrap = document.getElementById('pal-sw-wrap');
    if (wrap) wrap.setAttribute('title', label);
    // Option-Labels aus den i18n-Keys (ui.palette.*) einlesen.
    for (let i = 0; i < sel.options.length; i++) {
      const v = sel.options[i].value;
      if (typeof t === 'function' && PALS.indexOf(v) >= 0) {
        sel.options[i].text = t('ui.palette.' + v);
      }
    }
  }
}

// Called by i18n.js when user switches language — re-renders active page.
function onLangChange(lang) {
  const sel = document.getElementById('palette-select');
  if (sel) sel.setAttribute('aria-label', t('ui.palette'));
  const pages = {
    'pg-home':  () => { if (typeof loadHome === 'function') loadHome(); },
    'pg-admin': () => {
      if (!S) return;
      // Update dynamic sub-header
      const sub = document.getElementById('adm-sub');
      if (sub) sub.textContent = t('adm.sub');
      updOvStats && updOvStats();
      updLockBtn && updLockBtn();
      updSubLockBtns && updSubLockBtns();
      updMwAdm && updMwAdm();
      renderAP && renderAP();
      renderAL && renderAL();
      renderAC && renderAC();
      renderCoSum && renderCoSum();
      renderRS && renderRS();
      renderRR && renderRR();
    },
    'pg-part':  () => {
      if (!S) return;
      renderPtList && renderPtList();
      renderPtWishes && renderPtWishes();
      renderWaitSelection && renderWaitSelection();
      // Update identity bar
      const bar = document.getElementById('pt-id-bar');
      if (bar && myPName) bar.textContent = t('pt.logged_in_as', {name: myPName});
      // Re-render result if visible
      if (!document.getElementById('pt-result').classList.contains('H')) {
        renderPtResult && renderPtResult();
      }
    },
    'pg-ro':    () => { showROView && showROView(); },
    'pg-super': () => { loadSuperAdmin && loadSuperAdmin(); },
    'pg-about': () => {},
  };
  for (const [id, fn] of Object.entries(pages)) {
    const el = document.getElementById(id);
    if (el && !el.classList.contains('H')) { fn(); break; }
  }
}

// ── Boot ──────────────────────────────────────────────────────────────────────
// i18n.js must be loaded before app.js. initLang() returns a Promise.

// M4: Ein eingehender Admin-Link der Form #admin?secret=... wird beim Start
// ausgewertet und das Secret SOFORT aus der URL entfernt (history.replaceState),
// damit es nie in Browser-History/Referer bleibt. Gehalten wird es nur im
// JS-Speicher (superSecret).
function tryHandleAdminHash(){
  const m=location.hash.match(/^#admin\?secret=([^&]+)/);
  if(!m) return false;
  const sec=decodeURIComponent(m[1]);
  history.replaceState(null,"",location.pathname+location.search);
  superSecret=sec;
  loadSuperAdmin();
  return true;
}

initLang().then(() => {
  initPalette();
  if (tryHandleAdminHash()) return;   // Admin-Link hat Vorrang vor Nav-State
  const saved = sessionStorage.getItem(SSTATE_KEY);
  if (saved) {
    try {
      const st = JSON.parse(saved);
      if (st.code) {
        (async () => {
          const r = await api(`/api/session/${st.code}`);
          if (!r.error) {
            S = r; myCode = st.code;
            if      (st.page === 'admin' && r.is_admin) showAdminView();
            else if (st.page === 'ro')                  showROView();
            else if (st.page === 'part') {
              if (st.pid) { myPid = st.pid; myPName = st.name || ''; }
              showPartView();
            } else loadHome();
          } else loadHome();
        })();
        return;
      }
    } catch (_) {}
  }
  loadHome();
});

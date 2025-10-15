const API = "http://127.0.0.1:3070";
const $ = s => document.querySelector(s);
const el = (tag, props={}, ...kids) => {
  const x = document.createElement(tag);
  Object.assign(x, props); kids.forEach(k=>x.append(k)); return x;
};
async function jget(u, o){ const r=await fetch(u,o); const t=await r.text(); try{return JSON.parse(t)}catch{throw new Error(t)} }

async function loadProfiles(){
  const list = await jget(`${API}/api/profiles`);
  const tb = $("#profilesTbl tbody"); tb.innerHTML="";
  list.forEach(p=>{
    const running = (window._running||[]).includes(String(p.id));
    tb.append(el("tr",{},
      el("td",{}, p.name || p.id),
      el("td",{}, running ? "Активен" : "Неактивен"),
      el("td",{}, p.os || "Windows 10"),
      el("td",{}, p.proxy?.server || "—"),
      el("td",{},
        el("button",{onclick:()=>launch(p.id)}, "▶"),
        el("button",{onclick:()=>stop(p.id), style:"margin-left:6px"},"■"),
        el("button",{onclick:()=>delProfile(p.id), style:"margin-left:6px", title:"Удалить"},"🗑")
      )
    ));
  });
}
async function health(){
  const h = await jget(`${API}/api/health`); window._running = h.running||[]; $("#healthBox").textContent = JSON.stringify(h,null,2);
  await loadProfiles();
}
async function createProfile(){
  const id = prompt("ID профиля (латиницей):","us1"); if(!id) return;
  const name = prompt("Название:","Профиль "+id);
  const proxy = prompt("Прокси (например http://user:pass@ip:port, можно пусто):");
  let proxyObj=null;
  if (proxy && proxy.trim()){
    try {
      const u = new URL(proxy);
      proxyObj = { server: `${u.protocol}//${u.host}`, username: u.username||undefined, password: u.password||undefined };
    } catch {}
  }
  const body = { id, name, locale:"ru-RU", timezone:"Europe/Moscow", viewport:{width:1280,height:800}, proxy: proxyObj };
  await jget(`${API}/api/profiles`, { method:"POST", headers:{ "Content-Type":"application/json" }, body: JSON.stringify(body) });
  await loadProfiles();
}
async function launch(id){
  const out = await jget(`${API}/api/profiles/${id}/launch`, { method:"POST" });
  await health();
}
async function stop(id){
  const out = await jget(`${API}/api/profiles/${id}/stop`, { method:"POST" });
  await health();
}
async function delProfile(id){
  if (!confirm("Удалить профиль "+id+" ?")) return;
  await jget(`${API}/api/profiles/${id}`, { method:"DELETE" }); await loadProfiles();
}

$("#btnHealth").onclick = health;
$("#btnCreate").onclick = createProfile;

// навигация
document.querySelectorAll(".side .nav").forEach(b=>{
  b.onclick = ()=>{
    document.querySelectorAll(".nav").forEach(x=>x.classList.remove("active"));
    b.classList.add("active");
    const id = b.id.replace("nav","page");
    document.querySelectorAll(".page").forEach(p=>p.classList.remove("active"));
    $("#"+id).classList.add("active");
  };
});

health().catch(console.error);
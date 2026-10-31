// Auth guard: app pages need a session
if(!_l("vp_session",null))location.replace("login.html");
// Shared app shell: sidebar + top bar, injected on every page
const NAV=[["index.html","🏠","Dashboard"],["pantry.html","🥕","Pantry"],["recipes.html","📖","Recipes"],["planner.html","📅","Meal planner"],["shopping.html","🛒","Shopping list"],["health.html","⚖️","Health & BMI"],["profile.html","👤","Profile"],["settings.html","⚙️","Settings"]];
function updateShellAvatar(){
  const avatar=document.getElementById("shellAvatar");
  if(!avatar)return;
  const picture=VP.user.profilePicture;
  if(picture){
    const image=document.createElement("img");
    image.src=picture; image.alt="Profile picture"; image.width=38; image.height=38;
    image.style.cssText="width:100%;height:100%;object-fit:cover;border-radius:50%";
    avatar.replaceChildren(image);
  }else avatar.textContent=(VP.user.name||"?")[0].toUpperCase();
}
function updateShellName(name){
  const nameElement=document.querySelector(".user-card b");
  if(nameElement)nameElement.textContent=name;
}
function buildShell(){
  const page=document.body.dataset.page, title=document.body.dataset.title||"";
  const links=NAV.map(([h,i,t])=>`<a href="${h}" ${h===page?'aria-current="page"':''}><span aria-hidden="true">${i}</span>${t}</a>`).join("");
  const u=VP.user;
  document.body.insertAdjacentHTML("afterbegin",`
  <aside class="sidebar" id="sidebar"><button class="pin-btn" id="pinBtn" aria-pressed="false">📌 Pin</button><div class="brand"><img src="assets/logo.jpeg" alt="VitaPlate - Nourish. Plan. Thrive."></div>
  <nav class="nav" aria-label="Main">${links}</nav>
  <div class="user-card"><div class="avatar" id="shellAvatar"></div><div><a href="settings.html" ${page==="settings.html"?'aria-current="page"':''}><b>${u.name}</b></a><div class="muted" style="font-size:.8rem">Goal: ${u.goalKcal} kcal/day</div></div></div><button class="btn btn-ghost btn-sm" id="logout">Log out</button></aside>
  <div class="scrim" id="scrim"></div>`);
  const main=document.querySelector(".main");
  main.insertAdjacentHTML("afterbegin",`<header class="topbar"><button class="btn btn-ghost btn-sm menu-btn" id="menuBtn" aria-label="Open menu">☰</button><span class="muted" style="margin-left:auto">${title}</span></header>`);
  const pinBtn=document.getElementById("pinBtn");
  const pinned=_l("vp_nav_pinned",false);
  const updatePin=()=>{document.body.classList.toggle("nav-pinned",pinnedState);pinBtn.setAttribute("aria-pressed",pinnedState);pinBtn.textContent=pinnedState?"📌 Pinned":"📌 Pin"};
  let pinnedState=pinned;
  const toggle=()=>{if(!pinnedState)document.body.classList.toggle("nav-open")};
  document.getElementById("menuBtn").onclick=toggle;
  pinBtn.onclick=()=>{pinnedState=!pinnedState;_s("vp_nav_pinned",pinnedState);if(pinnedState)document.body.classList.add("nav-open");updatePin()};
  document.getElementById("scrim").onclick=toggle;
  document.getElementById("logout").onclick=()=>{localStorage.removeItem("vp_session");location.href="login.html"};
  updateShellAvatar();
  updatePin();
}
function setRing(el,value,goal){
  const c=2*Math.PI*76, pct=Math.min(value/goal,1);
  el.querySelector(".fill").style.strokeDasharray=c;
  el.querySelector(".fill").style.strokeDashoffset=c*(1-pct);
}
document.addEventListener("DOMContentLoaded",buildShell);

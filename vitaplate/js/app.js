// Shared app shell: sidebar + top bar, injected on every page
const NAV=[["index.html","🏠","Dashboard"],["pantry.html","🥕","Pantry"],["recipes.html","📖","Recipes"],["planner.html","📅","Meal planner"],["shopping.html","🛒","Shopping list"],["health.html","⚖️","Health & BMI"],["profile.html","👤","Profile"]];
function buildShell(){
  const page=document.body.dataset.page, title=document.body.dataset.title||"";
  const links=NAV.map(([h,i,t])=>`<a href="${h}" ${h===page?'aria-current="page"':''}><span aria-hidden="true">${i}</span>${t}</a>`).join("");
  const u=VP.user;
  document.body.insertAdjacentHTML("afterbegin",`
  <aside class="sidebar" id="sidebar"><div class="brand"><img src="assets/logo.jpeg" alt="VitaPlate - Nourish. Plan. Thrive."></div>
  <nav class="nav" aria-label="Main">${links}</nav>
  <div class="user-card"><div class="avatar">${u.name[0]}</div><div><b>${u.name}</b><div class="muted" style="font-size:.8rem">Goal: ${u.goalKcal} kcal/day</div></div></div></aside>
  <div class="scrim" id="scrim"></div>`);
  const main=document.querySelector(".main");
  main.insertAdjacentHTML("afterbegin",`<header class="topbar"><button class="btn btn-ghost btn-sm menu-btn" id="menuBtn" aria-label="Open menu">☰</button><input class="input search" type="search" placeholder="Search recipes or pantry" aria-label="Search"><span class="muted" style="margin-left:auto">${title}</span></header>`);
  const toggle=()=>document.body.classList.toggle("nav-open");
  document.getElementById("menuBtn").onclick=toggle;
  document.getElementById("scrim").onclick=toggle;
}
function setRing(el,value,goal){
  const c=2*Math.PI*76, pct=Math.min(value/goal,1);
  el.querySelector(".fill").style.strokeDasharray=c;
  el.querySelector(".fill").style.strokeDashoffset=c*(1-pct);
}
document.addEventListener("DOMContentLoaded",buildShell);

// Shared app shell: sidebar + top bar, injected on every page
const THEME_STORAGE_KEY="vp_theme";
const ACTIVE_ACCOUNT_STORAGE_KEY="vp_active_account";
const storedTheme=VP.safeStorage.getString(THEME_STORAGE_KEY,"light",value=>value==="light"||value==="dark");
document.documentElement.dataset.theme=storedTheme==="dark"?"dark":"light";
const NAV=[["index.html","🏠","Dashboard"],["pantry.html","🥕","Pantry"],["recipes.html","📖","Recipes"],["planner.html","📅","Meal planner"],["shopping.html","🛒","Shopping list"],["health.html","⚖️","Health & BMI"],["profile.html","👤","Profile"],["settings.html","⚙️","Settings"]];
function initializeThemeToggle(){
  const button=document.createElement("button");
  button.type="button";
  button.className="theme-toggle";
  button.innerHTML='<svg class="sun-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"></path></svg><svg class="moon-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20.9 13A9 9 0 0 1 11 3.1 9 9 0 1 0 20.9 13Z"></path></svg><span class="theme-toggle-text"></span>';
  const updateButton=()=>{
    const isDark=document.documentElement.dataset.theme==="dark";
    const label=isDark?"Switch to light mode":"Switch to dark mode";
    button.setAttribute("aria-label",label);
    button.setAttribute("aria-pressed",String(isDark));
    button.title=label;
    button.querySelector(".theme-toggle-text").textContent=isDark?"Light mode":"Dark mode";
  };
  button.addEventListener("click",()=>{
    const nextTheme=document.documentElement.dataset.theme==="dark"?"light":"dark";
    document.documentElement.dataset.theme=nextTheme;
    VP.safeStorage.setString(THEME_STORAGE_KEY,nextTheme,value=>value==="light"||value==="dark");
    updateButton();
  });
  const topbar=document.querySelector(".topbar");
  if(topbar)topbar.append(button);
  else document.body.append(button);
  updateButton();
}
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
function updateShellGoal(goalKcal){
  const goalElement=document.getElementById("shellGoal");
  if(goalElement)goalElement.textContent=`Goal: ${goalKcal} kcal/day`;
}
function showAccountError(message){
  const show=()=>{
    let banner=document.getElementById("accountApiError");
    if(!banner){
      banner=document.createElement("p");
      banner.id="accountApiError";
      banner.setAttribute("role","alert");
      banner.style.cssText="margin:12px auto;padding:10px 14px;max-width:900px;border-radius:10px;background:#fff0ee;color:#8b2f24";
      document.querySelector(".content")?.prepend(banner);
    }
    banner.textContent=message;
  };
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",show,{once:true});
  else show();
}
function buildShell(){
  if(!document.body.dataset.page)return;
  const page=document.body.dataset.page, title=document.body.dataset.title||"";
  const links=NAV.map(([h,i,t])=>`<a href="${h}" ${h===page?'aria-current="page"':''}><span aria-hidden="true">${i}</span>${t}</a>`).join("");
  const u=VP.user;
  document.body.insertAdjacentHTML("afterbegin",`
  <aside class="sidebar" id="sidebar"><button class="pin-btn" id="pinBtn" aria-pressed="false">📌 Pin</button><div class="brand"><img src="assets/logo.jpeg" alt="VitaPlate - Nourish. Plan. Thrive."></div>
  <nav class="nav" aria-label="Main">${links}</nav>
  <div class="user-card"><div class="avatar" id="shellAvatar"></div><div><a href="settings.html" ${page==="settings.html"?'aria-current="page"':''}><b>${VP.escapeHtml(u.name)}</b></a><div class="muted" id="shellGoal" style="font-size:.8rem">Goal: ${u.goalKcal} kcal/day</div></div></div><button class="btn btn-ghost btn-sm" id="logout">Log out</button></aside>
  <div class="scrim" id="scrim"></div>`);
  const main=document.querySelector(".main");
  main.insertAdjacentHTML("afterbegin",`<header class="topbar"><button class="btn btn-ghost btn-sm menu-btn" id="menuBtn" aria-label="Open menu">☰</button><span class="muted" style="margin-left:auto">${title}</span></header>`);
  const pinBtn=document.getElementById("pinBtn");
  const pinned=_l("vp_nav_pinned",false,value=>typeof value==="boolean");
  const updatePin=()=>{document.body.classList.toggle("nav-pinned",pinnedState);pinBtn.setAttribute("aria-pressed",pinnedState);pinBtn.textContent=pinnedState?"📌 Pinned":"📌 Pin"};
  let pinnedState=pinned;
  const toggle=()=>{if(!pinnedState)document.body.classList.toggle("nav-open")};
  document.getElementById("menuBtn").onclick=toggle;
  pinBtn.onclick=()=>{pinnedState=!pinnedState;_s("vp_nav_pinned",pinnedState);if(pinnedState)document.body.classList.add("nav-open");updatePin()};
  document.getElementById("scrim").onclick=toggle;
  document.getElementById("logout").onclick=async()=>{
    try{
      const response=await fetch("/api/logout",{method:"POST",credentials:"same-origin"});
      if(!response.ok)throw new Error("Could not log out. Please try again.");
      resetAccountState();
      VP.safeStorage.remove(ACTIVE_ACCOUNT_STORAGE_KEY);
      location.replace("login.html");
    }catch(error){alert(error.message||"Could not log out. Please try again.")}
  };
  updateShellAvatar();
  updatePin();
}
function setRing(el,value,goal){
  const c=2*Math.PI*76, pct=Math.min(value/goal,1);
  el.querySelector(".fill").style.strokeDasharray=c;
  el.querySelector(".fill").style.strokeDashoffset=c*(1-pct);
}
document.addEventListener("DOMContentLoaded",()=>{
  buildShell();
  initializeThemeToggle();
});

async function accountRequest(path){
  const response=await fetch(path,{credentials:"same-origin"});
  const data=await response.json().catch(()=>({}));
  if(response.status===401){
    resetAccountState();
    VP.safeStorage.remove(ACTIVE_ACCOUNT_STORAGE_KEY);
    location.replace("login.html");
    return null
  }
  if(!response.ok)throw new Error(data.error||"Could not load your account data.");
  return data;
}

async function loadAccountData(){
  const current=await accountRequest("/api/me");
  if(!current)return;
  const accountId=current.user.id;
  if(VP.accountId!==accountId)resetAccountState(current.user);
  VP.safeStorage.setString(ACTIVE_ACCOUNT_STORAGE_KEY,String(accountId),value=>/^[1-9]\d*$/.test(value));
  VP.user.name=current.user.name;
  const [profile,settings,pantry,dietary]=await Promise.all([
    accountRequest("/api/profile"),
    accountRequest("/api/settings"),
    accountRequest("/api/pantry"),
    accountRequest("/api/dietary")
  ]);
  if(!profile||!settings||!pantry||!dietary)return;
  const verified=await accountRequest("/api/me");
  if(!verified||String(verified.user.id)!==String(accountId))return;
  VP.user.goalKcal=profile.calorie_goal||1800;
  VP.user.profilePicture=settings.picture_url||"";
  VP.profile=profile;
  VP.dietary=dietary;
  VP.pantry=pantry.items;
  VP.diets=dietary.diets;
  updateShellAvatar();
  updateShellName(VP.user.name);
  updateShellGoal(VP.user.goalKcal);
  window.dispatchEvent(new Event("vp-data-ready"));
}

window.addEventListener("storage",event=>{
  if(event.key!==ACTIVE_ACCOUNT_STORAGE_KEY)return;
  if(event.newValue!==null&&!/^[1-9]\d*$/.test(event.newValue)){
    resetAccountState();
    document.documentElement.style.visibility="hidden";
    location.replace("login.html");
    return;
  }
  if(event.newValue===String(VP.accountId))return;
  resetAccountState();
  document.documentElement.style.visibility="hidden";
  location.replace("login.html");
});

window.addEventListener("pageshow",event=>{
  if(event.persisted&&document.body.dataset.page)loadAccountData().catch(error=>{
    showAccountError(error.message||"Could not reload your account data.");
  });
});

if(document.body.dataset.page){
  VP.ready=loadAccountData().catch(error=>{
    VP.apiError=error.message||"Could not load your account data.";
    console.error("Could not load account data:",error);
    showAccountError(VP.apiError);
  });
}

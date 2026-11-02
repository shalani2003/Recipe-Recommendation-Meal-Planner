// Pantry page, connected to the backend (/api/pantry, /api/dietary).
// Pantry and dietary data belong to the signed-in account on the server.
const CATS={Vegetables:"🥕",Fruits:"🍎",Grains:"🌾",Protein:"🍗",Dairy:"🥛","Spices & sauces":"🌶️",Other:"🥫"};
const QUICK=[["Rice","Grains"],["Dhal","Grains"],["Coconut","Fruits"],["Eggs","Protein"],["Onion","Vegetables"],["Tomato","Vegetables"],["Chicken","Protein"],["Curry powder","Spices & sauces"]];
const DIETS=["Vegetarian","Vegan","Gluten-free","Dairy-free","Nut-free","Halal","Low sugar"];
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let items=[],diets=[],summary={items:0,use_soon:0,expired:0},loaded=false;

// The browser's own date, so "expires today" is right in every time zone.
const localToday=()=>{const d=new Date();return d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"+String(d.getDate()).padStart(2,"0")};

function toast(msg){
  let t=$("pantryToast");
  if(!t){t=document.createElement("div");t.id="pantryToast";t.setAttribute("role","alert");
   t.style.cssText="position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#1b4d2b;color:#fff;padding:10px 18px;border-radius:10px;z-index:99;max-width:90vw;font-weight:600";document.body.appendChild(t)}
  t.textContent=msg;t.style.display="block";clearTimeout(t._h);t._h=setTimeout(()=>t.style.display="none",3500);
}
async function call(path,method="GET",payload){
  try{
    const r=await fetch(path,{method,credentials:"same-origin",headers:{"Content-Type":"application/json"},body:payload===undefined?undefined:JSON.stringify(payload)});
    const d=await r.json().catch(()=>({}));
    if(r.status===401)location.replace("login.html")
    return{ok:r.ok,status:r.status,data:d};
  }catch{return{ok:false,status:0,data:{error:"Cannot reach the server. Start the backend and open http://127.0.0.1:5000"}}}
}
async function refresh(){
  const [p,d]=await Promise.all([call("/api/pantry?today="+localToday()),call("/api/dietary")]);
  if(!p.ok)toast(p.data.error||"Could not load your pantry.");
  else{items=p.data.items;summary=p.data.summary;loaded=true;VP.pantry=items}
  if(d.ok){diets=d.data.diets;VP.diets=diets}
  if(p.ok&&d.ok)window.dispatchEvent(new Event("vp-data-ready"));
  render();
}
function render(){
  const q=$("filter").value.toLowerCase();
  const shown=items.filter(i=>i.name.toLowerCase().includes(q));
  $("sItems").textContent=summary.items;$("sSoon").textContent=summary.use_soon;$("sDiet").textContent=diets.length;
  $("groups").innerHTML=!shown.length?`<div class="empty"><div class="big">🧺</div><h3>${!loaded?"Loading your pantry...":items.length?"No match":"Your pantry is empty"}</h3><p>${!loaded?"":items.length?"Try a different name.":"Add what you have at home and we will suggest recipes."}</p></div>`:
  Object.keys(CATS).map(c=>{const g=shown.filter(i=>i.cat===c);if(!g.length)return"";
   return `<section class="cat"><h3><span>${CATS[c]}</span>${c}<small>${g.length}</small></h3><div class="items">${g.map(card).join("")}</div></section>`}).join("");
  $("diets").innerHTML=DIETS.map(d=>`<button class="chip" aria-pressed="${diets.includes(d)}" data-d="${d}">${d}</button>`).join("");
}
function card(i){
  const d=i.days_left;const s={expired:"exp",today:"soon",soon:"soon",ok:"ok",none:""}[i.state];
  const n=i.name.toLowerCase();
  const photo=(/chicken|egg|fish|salmon|protein/.test(n))?"assets/food/chicken-quinoa.jpg":(/tomato|avocado|fruit|banana|apple|vegetable|broccoli|carrot|onion|salad/.test(n))?"assets/food/salad-bowl.jpg":(/dhal|lentil|rice|grain|coconut|milk|dairy|soup/.test(n))?"assets/food/lentil-soup.jpg":"assets/food/hero-healthy-bowl.jpg";
  const t=d===null?"No expiry date":d<0?"Expired "+(-d)+" day(s) ago":d===0?"Expires today":d<=3?"Expires in "+d+" day(s)":"Fresh for "+d+" days";
  return `<article class="item ${s}"><div class="item-top"><img class="pantry-item-photo" src="${photo}" alt="${esc(i.name)}" loading="lazy"><b>${esc(i.name)}</b><button class="rm" data-ed="${i.id}" aria-label="Edit ${esc(i.name)}">✎</button><button class="rm" data-rm="${i.id}" aria-label="Remove ${esc(i.name)}">✕</button></div>
 <div class="qty"><button data-m="${i.id}" aria-label="Less">−</button><span>${i.qty} ${esc(i.unit)}</span><button data-p="${i.id}" aria-label="More">+</button></div><span class="tag ${s}">${t}</span></article>`;
}
async function add(name,cat,qty=1,unit="pcs",exp=""){
  if(!name.trim())return toast("Enter an item name.");
  const r=await call("/api/pantry","POST",{name,category:cat,quantity:qty===""?1:qty,unit,expiry_date:exp});
  if(!r.ok)return toast(r.data.error||"Could not add the item.");
  if(r.data.merged)toast("Added to the amount you already have.");
  await refresh();
}
async function edit(id){
  const i=items.find(x=>x.id==id);if(!i)return;
  const qty=prompt("Amount ("+i.unit+")",i.qty);if(qty===null)return;
  const exp=prompt("Expiry date (YYYY-MM-DD). Leave empty for none.",i.exp||"");if(exp===null)return;
  const r=await call("/api/pantry/"+id,"PUT",{quantity:qty,expiry_date:exp});
  if(!r.ok)return toast(r.data.error||"Could not save the change.");
  await refresh();
}
document.addEventListener("DOMContentLoaded",()=>{
 $("cat").innerHTML=Object.keys(CATS).map(c=>`<option>${c}</option>`).join("");
 $("quick").innerHTML=QUICK.map(([n,c])=>`<button type="button" class="chip pick" data-q="${n}|${c}">+ ${n}</button>`).join("");
 $("addForm").onsubmit=async e=>{e.preventDefault();await add($("name").value,$("cat").value,$("qty").value,$("unit").value,$("exp").value);e.target.reset();$("qty").value=1;$("name").focus()};
 $("quick").onclick=e=>{const b=e.target.closest("[data-q]");if(b){const[n,c]=b.dataset.q.split("|");add(n,c)}};
 $("diets").onclick=async e=>{const b=e.target.closest("[data-d]");if(!b)return;const d=b.dataset.d;
  const next=diets.includes(d)?diets.filter(x=>x!==d):[...diets,d];
  const r=await call("/api/dietary","PUT",{diets:next});
  if(!r.ok)return toast(r.data.error||"Could not save your diets.");
  diets=r.data.diets;render()};
 $("groups").onclick=async e=>{
  const t=e.target;let r;
  if(t.dataset.ed){return edit(t.dataset.ed)}
  if(t.dataset.rm)r=await call("/api/pantry/"+t.dataset.rm,"DELETE");
  else if(t.dataset.p)r=await call("/api/pantry/"+t.dataset.p+"/quantity","PATCH",{delta:1});
  else if(t.dataset.m)r=await call("/api/pantry/"+t.dataset.m+"/quantity","PATCH",{delta:-1});
  else return;
  if(!r.ok)toast(r.data.error||"Could not update the item.");
  await refresh()};
 $("filter").oninput=render;
 $("clear").onclick=async()=>{if(confirm("Remove all pantry items?")){const r=await call("/api/pantry","DELETE");if(!r.ok)toast(r.data.error||"Could not clear the pantry.");await refresh()}};
 render();refresh();
});

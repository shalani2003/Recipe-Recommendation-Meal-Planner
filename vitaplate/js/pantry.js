// Pantry page. Items are stored in the database through /api/pantry (see api.js).
const CATS={Vegetables:"🥕",Fruits:"🍎",Grains:"🌾",Protein:"🍗",Dairy:"🥛","Spices & sauces":"🌶️",Other:"🥫"};
const QUICK=[["Rice","Grains"],["Dhal","Grains"],["Coconut","Fruits"],["Eggs","Protein"],["Onion","Vegetables"],["Tomato","Vegetables"],["Chicken","Protein"],["Curry powder","Spices & sauces"]];
const DIETS=["Vegetarian","Vegan","Gluten-free","Dairy-free","Nut-free","Halal","Low sugar"];
const load=(k,d)=>{try{return JSON.parse(localStorage.getItem(k))||d}catch{return d}};
let items=[];            // filled from the server
let loading=true;        // true until the first load finishes
let loaded=false;        // true once the server copy has been received
let editingId=null;      // id of the item being edited, or null
let diets=load("vp_diets",[]);
const days=e=>e?Math.ceil((new Date(e)-new Date(new Date().toDateString()))/864e5):null;
const saveDiets=()=>localStorage.setItem("vp_diets",JSON.stringify(diets));
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

// ---- talking to the server -------------------------------------------------
// Requests run one after another so quick clicks on + / − arrive in order.
let queue=Promise.resolve();
function run(task){const result=queue.then(task);queue=result.catch(()=>{});return result}
// For changes already shown on screen: if the server refuses, show why and reload the real data.
function optimistic(task){run(task).catch(e=>{flash(e.message,true);run(reload).catch(()=>{})})}
async function reload(){items=await VPApi.pantry.load();loaded=true;render()}
function flash(text,isError){
  const el=$("pantryMsg");el.textContent=text;el.style.color=isError?"var(--danger)":"";
  clearTimeout(flash.t);if(text)flash.t=setTimeout(()=>{el.textContent=""},isError?7000:3000);
}
function upsert(item){const k=items.findIndex(i=>i.id===item.id);if(k>=0)items[k]=item;else items.push(item);render()}

function render(){
  const q=$("filter").value.toLowerCase();
  const shown=items.filter(i=>i.name.toLowerCase().includes(q));
  const exp=items.filter(i=>days(i.exp)!==null&&days(i.exp)<=3).length;
  $("sItems").textContent=items.length;$("sSoon").textContent=exp;$("sDiet").textContent=diets.length;
  $("groups").innerHTML=!shown.length?`<div class="empty"><div class="big">🧺</div><h3>${loading?"Loading your pantry…":items.length?"No match":"Your pantry is empty"}</h3><p>${loading?"One moment.":items.length?"Try a different name.":"Add what you have at home and we will suggest recipes."}</p></div>`:
  Object.keys(CATS).map(c=>{const g=shown.filter(i=>i.cat===c);if(!g.length)return"";
   return `<section class="cat"><h3><span>${CATS[c]}</span>${c}<small>${g.length}</small></h3><div class="items">${g.map(card).join("")}</div></section>`}).join("");
  $("diets").innerHTML=DIETS.map(d=>`<button class="chip" aria-pressed="${diets.includes(d)}" data-d="${d}">${d}</button>`).join("");
  saveDiets();
  // keep the browser copy (used by the Recipes page) in step - but never overwrite it before the first load
  if(loaded)VPApi.pantry.cache(items);
}
function card(i){const d=days(i.exp);const s=d===null?"":d<0?"exp":d<=3?"soon":"ok"; const n=i.name.toLowerCase(); const photo=(/chicken|egg|fish|salmon|protein/.test(n))?"assets/food/chicken-quinoa.jpg":(/tomato|avocado|fruit|banana|apple|vegetable|broccoli|carrot|onion|salad/.test(n))?"assets/food/salad-bowl.jpg":(/dhal|lentil|rice|grain|coconut|milk|dairy|soup/.test(n))?"assets/food/lentil-soup.jpg":"assets/food/hero-healthy-bowl.jpg";
 const t=d===null?"No expiry date":d<0?"Expired "+(-d)+" day(s) ago":d===0?"Expires today":d<=3?"Expires in "+d+" day(s)":"Fresh for "+d+" days";
 const name=esc(i.name);
 return `<article class="item ${s}"><div class="item-top"><img class="pantry-item-photo" src="${photo}" alt="${name}" loading="lazy"><b>${name}</b><button class="rm" data-ed="${i.id}" aria-label="Edit ${name}">✎</button><button class="rm" data-rm="${i.id}" aria-label="Remove ${name}">✕</button></div>
 <div class="qty"><button data-m="${i.id}" aria-label="Less">−</button><span>${i.qty} ${i.unit}</span><button data-p="${i.id}" aria-label="More">+</button></div><span class="tag ${s}">${t}</span></article>`}

// ---- add / edit ---------------------------------------------------------
async function add(item){
  item.name=item.name.trim();if(!item.name)return false;
  try{
    const {item:saved,merged}=await run(()=>VPApi.pantry.add(item));
    upsert(saved);flash(merged?`Added more ${saved.name}`:`Added ${saved.name}`);return true;
  }catch(e){flash(e.message,true);return false}
}
async function saveEdit(id,fields){
  try{
    const saved=await run(()=>VPApi.pantry.update(id,fields));
    upsert(saved);flash(`Saved ${saved.name}`);return true;
  }catch(e){flash(e.message,true);return false}
}
function setEditing(item){
  editingId=item?item.id:null;
  const form=$("addForm");
  form.querySelector("[type=submit]").textContent=item?"Save changes":"Add to pantry";
  $("cancelEdit").style.display=item?"":"none";
  if(item){$("name").value=item.name;$("cat").value=item.cat;$("qty").value=item.qty;$("unit").value=item.unit;$("exp").value=item.exp||"";
   form.scrollIntoView({behavior:"smooth",block:"center"});}
  else{form.reset();$("qty").value=1}
  $("name").focus();
}

document.addEventListener("DOMContentLoaded",()=>{
 // message line above the ingredient list
 const msg=document.createElement("p");msg.id="pantryMsg";msg.className="muted";msg.setAttribute("role","status");msg.style.minHeight="1.4em";
 $("groups").parentNode.insertBefore(msg,$("groups"));
 // allow amounts like 0.5 kg
 $("qty").min="0.01";$("qty").step="any";
 // cancel button for edit mode
 const cancel=document.createElement("button");cancel.type="button";cancel.id="cancelEdit";cancel.className="btn btn-ghost full";cancel.textContent="Cancel";cancel.style.display="none";
 $("addForm").appendChild(cancel);cancel.onclick=()=>setEditing(null);

 $("cat").innerHTML=Object.keys(CATS).map(c=>`<option>${c}</option>`).join("");
 $("quick").innerHTML=QUICK.map(([n,c])=>`<button type="button" class="chip pick" data-q="${n}|${c}">+ ${n}</button>`).join("");
 $("addForm").onsubmit=async e=>{e.preventDefault();
  const fields={name:$("name").value.trim(),cat:$("cat").value,qty:+$("qty").value,unit:$("unit").value,exp:$("exp").value};
  if(!fields.name)return;
  const ok=editingId!==null?await saveEdit(editingId,fields):await add(fields);
  if(ok)setEditing(null)};
 $("quick").onclick=e=>{const b=e.target.closest("[data-q]");if(b){const[n,c]=b.dataset.q.split("|");add({name:n,cat:c,qty:1,unit:"pcs",exp:""})}};
 $("diets").onclick=e=>{const b=e.target.closest("[data-d]");if(!b)return;const d=b.dataset.d;diets=diets.includes(d)?diets.filter(x=>x!==d):[...diets,d];render()};
 $("groups").onclick=e=>{const b=e.target.closest("button");if(!b)return;
  const d=b.dataset,find=id=>items.find(i=>i.id==id);
  const removeItem=id=>{items=items.filter(i=>i.id!=id);if(editingId==id)setEditing(null);render();optimistic(()=>VPApi.pantry.remove(id))};
  const setQty=(i,q)=>{i.qty=q;render();optimistic(()=>VPApi.pantry.update(i.id,{qty:q}))};
  if(d.rm)removeItem(d.rm);
  else if(d.p){const i=find(d.p);if(i)setQty(i,Math.round((i.qty+1)*1000)/1000)}
  else if(d.m){const i=find(d.m);if(i){if(i.qty-1<=0)removeItem(i.id);else setQty(i,Math.round((i.qty-1)*1000)/1000)}}
  else if(d.ed){const i=find(d.ed);if(i)setEditing(i)}};
 $("filter").oninput=render;
 $("clear").onclick=()=>{if(confirm("Remove all pantry items?")){items=[];setEditing(null);render();optimistic(()=>VPApi.pantry.clear())}};
 render();
 // first load from the server
 VPApi.pantry.load()
  .then(list=>{items=list;loaded=true})
  .catch(e=>{items=load("vp_pantry",[]);flash(`${e.message} Showing the last saved copy - changes can't be saved right now.`,true)})
  .finally(()=>{loading=false;render()});
});

const CATS={Vegetables:"🥕",Fruits:"🍎",Grains:"🌾",Protein:"🍗",Dairy:"🥛","Spices & sauces":"🌶️",Other:"🥫"};
const QUICK=[["Rice","Grains"],["Dhal","Grains"],["Coconut","Fruits"],["Eggs","Protein"],["Onion","Vegetables"],["Tomato","Vegetables"],["Chicken","Protein"],["Curry powder","Spices & sauces"]];
const DIETS=["Vegetarian","Vegan","Gluten-free","Dairy-free","Nut-free","Halal","Low sugar"];
const load=(k,d)=>{try{return JSON.parse(localStorage.getItem(k))||d}catch{return d}};
let items=load("vp_pantry",[
 {id:1,name:"Basmati rice",cat:"Grains",qty:2,unit:"kg",exp:""},
 {id:2,name:"Carrots",cat:"Vegetables",qty:6,unit:"pcs",exp:soon(2)},
 {id:3,name:"Milk",cat:"Dairy",qty:1,unit:"l",exp:soon(-1)},
 {id:4,name:"Eggs",cat:"Protein",qty:10,unit:"pcs",exp:soon(9)}]);
let diets=load("vp_diets",[]);
function soon(n){const d=new Date();d.setDate(d.getDate()+n);return d.toISOString().slice(0,10)}
const days=e=>e?Math.ceil((new Date(e)-new Date(new Date().toDateString()))/864e5):null;
const save=()=>{localStorage.setItem("vp_pantry",JSON.stringify(items));localStorage.setItem("vp_diets",JSON.stringify(diets))};
const $=id=>document.getElementById(id);
function render(){
  const q=$("filter").value.toLowerCase();
  const shown=items.filter(i=>i.name.toLowerCase().includes(q));
  const exp=items.filter(i=>days(i.exp)!==null&&days(i.exp)<=3).length;
  $("sItems").textContent=items.length;$("sSoon").textContent=exp;$("sDiet").textContent=diets.length;
  $("groups").innerHTML=!shown.length?`<div class="empty"><div class="big">🧺</div><h3>${items.length?"No match":"Your pantry is empty"}</h3><p>${items.length?"Try a different name.":"Add what you have at home and we will suggest recipes."}</p></div>`:
  Object.keys(CATS).map(c=>{const g=shown.filter(i=>i.cat===c);if(!g.length)return"";
   return `<section class="cat"><h3><span>${CATS[c]}</span>${c}<small>${g.length}</small></h3><div class="items">${g.map(card).join("")}</div></section>`}).join("");
  $("diets").innerHTML=DIETS.map(d=>`<button class="chip" aria-pressed="${diets.includes(d)}" data-d="${d}">${d}</button>`).join("");
  save();
}
function card(i){const d=days(i.exp);const s=d===null?"":d<0?"exp":d<=3?"soon":"ok"; const n=i.name.toLowerCase(); const photo=(/chicken|egg|fish|salmon|protein/.test(n))?"assets/food/chicken-quinoa.jpg":(/tomato|avocado|fruit|banana|apple|vegetable|broccoli|carrot|onion|salad/.test(n))?"assets/food/salad-bowl.jpg":(/dhal|lentil|rice|grain|coconut|milk|dairy|soup/.test(n))?"assets/food/lentil-soup.jpg":"assets/food/hero-healthy-bowl.jpg";
 const t=d===null?"No expiry date":d<0?"Expired "+(-d)+" day(s) ago":d===0?"Expires today":d<=3?"Expires in "+d+" day(s)":"Fresh for "+d+" days";
 return `<article class="item ${s}"><div class="item-top"><img class="pantry-item-photo" src="${photo}" alt="${i.name}" loading="lazy"><b>${i.name}</b><button class="rm" data-rm="${i.id}" aria-label="Remove ${i.name}">✕</button></div>
 <div class="qty"><button data-m="${i.id}" aria-label="Less">−</button><span>${i.qty} ${i.unit}</span><button data-p="${i.id}" aria-label="More">+</button></div><span class="tag ${s}">${t}</span></article>`}
function add(name,cat,qty=1,unit="pcs",exp=""){if(!name.trim())return;
 const ex=items.find(i=>i.name.toLowerCase()===name.trim().toLowerCase());
 if(ex){ex.qty+=+qty}else items.push({id:Date.now()+Math.random(),name:name.trim(),cat,qty:+qty,unit,exp});render()}
document.addEventListener("DOMContentLoaded",()=>{
 $("cat").innerHTML=Object.keys(CATS).map(c=>`<option>${c}</option>`).join("");
 $("quick").innerHTML=QUICK.map(([n,c])=>`<button type="button" class="chip pick" data-q="${n}|${c}">+ ${n}</button>`).join("");
 $("addForm").onsubmit=e=>{e.preventDefault();add($("name").value,$("cat").value,$("qty").value,$("unit").value,$("exp").value);e.target.reset();$("qty").value=1;$("name").focus()};
 $("quick").onclick=e=>{const b=e.target.closest("[data-q]");if(b){const[n,c]=b.dataset.q.split("|");add(n,c)}};
 $("diets").onclick=e=>{const b=e.target.closest("[data-d]");if(!b)return;const d=b.dataset.d;diets=diets.includes(d)?diets.filter(x=>x!==d):[...diets,d];render()};
 $("groups").onclick=e=>{const g=a=>items.find(i=>i.id==e.target.dataset[a]);
  if(e.target.dataset.rm){items=items.filter(i=>i.id!=e.target.dataset.rm)}
  else if(e.target.dataset.p){g("p").qty++}
  else if(e.target.dataset.m){const i=g("m");if(--i.qty<=0)items=items.filter(x=>x!==i)}else return;render()};
 $("filter").oninput=render;
 $("clear").onclick=()=>{if(confirm("Remove all pantry items?")){items=[];render()}};
 render();
});

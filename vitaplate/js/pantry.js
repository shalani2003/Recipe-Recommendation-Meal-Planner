const CATS={Vegetables:"🥕",Fruits:"🍎",Grains:"🌾",Protein:"🍗",Dairy:"🥛","Spices & sauces":"🌶️",Other:"🥫"};
const QUICK=[["Rice","Grains"],["Dhal","Grains"],["Coconut","Fruits"],["Eggs","Protein"],["Onion","Vegetables"],["Tomato","Vegetables"],["Chicken","Protein"],["Curry powder","Spices & sauces"]];
const DIETS=["Vegetarian","Vegan","Gluten-free","Dairy-free","Nut-free","Halal","Low sugar"];
const MAX_QUANTITY=99999;
const UNITS={pcs:{whole:true},g:{whole:false},kg:{whole:false},ml:{whole:false},l:{whole:false},cups:{whole:false}};
const load=(k,d)=>{try{return JSON.parse(localStorage.getItem(k))||d}catch{return d}};
function soon(n){const d=new Date();d.setDate(d.getDate()+n);return `${d.getFullYear()}-${("0"+(d.getMonth()+1)).slice(-2)}-${("0"+d.getDate()).slice(-2)}`}
function sampleItems(){return[
 {id:Date.now()+1,name:"Basmati rice",cat:"Grains",qty:2,unit:"kg",exp:""},
 {id:Date.now()+2,name:"Carrots",cat:"Vegetables",qty:6,unit:"pcs",exp:soon(2)},
 {id:Date.now()+3,name:"Milk",cat:"Dairy",qty:1,unit:"l",exp:soon(-1)},
 {id:Date.now()+4,name:"Eggs",cat:"Protein",qty:10,unit:"pcs",exp:soon(9)}]}
const storedPantry=localStorage.getItem("vp_pantry");
let items=storedPantry===null?sampleItems():load("vp_pantry",[]);
let diets=load("vp_diets",[]);
function dateOrdinal(value){
 const match=/^(\d{4})-(\d{2})-(\d{2})$/.exec(value||"");
 if(!match)return null;
 const [year,month,day]=match.slice(1).map(Number);
 const date=new Date(0);
 date.setUTCHours(0,0,0,0);
 date.setUTCFullYear(year,month-1,day);
 if(date.getUTCFullYear()!==year||date.getUTCMonth()+1!==month||date.getUTCDate()!==day)return null;
 return Math.floor(date.getTime()/864e5);
}
function localDateString(date){
 return `${date.getFullYear()}-${("0"+(date.getMonth()+1)).slice(-2)}-${("0"+date.getDate()).slice(-2)}`;
}
function daysUntil(expiryDate,todayDate){
 const expiry=dateOrdinal(expiryDate),today=dateOrdinal(todayDate);
 return expiry===null||today===null?null:expiry-today;
}
function expiryStatus(expiryDate,todayDate){
 const remaining=expiryDate?daysUntil(expiryDate,todayDate||localDateString(new Date())):null;
 if(remaining===null)return{days:null,state:"",label:"No expiry date"};
 if(remaining<0)return{days:remaining,state:"exp",label:"Expired"};
 if(remaining===0)return{days:remaining,state:"soon",label:"Expiring Today"};
 if(remaining===1)return{days:remaining,state:"soon",label:"Expiring Tomorrow"};
 if(remaining<=3)return{days:remaining,state:"soon",label:"Expiring Soon"};
 return{days:remaining,state:"ok",label:"Fresh"};
}
function validateAmount(rawAmount,rawUnit){
 const unit=String(rawUnit||"").trim().toLowerCase();
 const amount=typeof rawAmount==="number"?rawAmount:Number(String(rawAmount===null||rawAmount===undefined?"":rawAmount).trim());
 if(!Object.prototype.hasOwnProperty.call(UNITS,unit))return{error:"Select a supported unit."};
 if(!Number.isFinite(amount)||amount<=0)return{error:"Enter an amount greater than zero."};
 if(amount>MAX_QUANTITY)return{error:`Amount cannot exceed ${MAX_QUANTITY}.`};
 if(UNITS[unit].whole&&!Number.isInteger(amount))return{error:"Use a whole number for pieces (pcs)."};
 if(!UNITS[unit].whole&&Math.abs(amount*100-Math.round(amount*100))>1e-8)return{error:"Use no more than two decimal places."};
 return{amount,unit};
}
const save=()=>{localStorage.setItem("vp_pantry",JSON.stringify(items));localStorage.setItem("vp_diets",JSON.stringify(diets))};
const $=id=>document.getElementById(id);
function showAmountError(message=""){
 const input=$("qty"),error=$("quantityError");
 if(input.setCustomValidity)input.setCustomValidity(message);
 if(error)error.textContent=message;
}
function render(){
  const q=$("filter").value.toLowerCase();
  const today=localDateString(new Date());
  const shown=items.filter(i=>i.name.toLowerCase().includes(q));
  const statuses=items.map(i=>expiryStatus(i.exp,today));
  const expired=statuses.filter(status=>status.state==="exp").length;
  const expiringSoon=statuses.filter(status=>status.state==="soon").length;
  $("sItems").textContent=items.length;$("sExpired").textContent=expired;$("sSoon").textContent=expiringSoon;
  $("groups").innerHTML=!shown.length?`<div class="empty"><div class="big">🧺</div><h3>${items.length?"No match":"Your pantry is empty"}</h3><p>${items.length?"Try a different name.":"Add what you have at home and we will suggest recipes."}</p></div>`:
  Object.keys(CATS).map(c=>{const g=shown.filter(i=>i.cat===c);if(!g.length)return"";
   return `<section class="cat"><h3><span>${CATS[c]}</span>${c}<small>${g.length}</small></h3><div class="items">${g.map(i=>card(i,today)).join("")}</div></section>`}).join("");
  $("diets").innerHTML=DIETS.map(d=>`<button class="chip" aria-pressed="${diets.includes(d)}" data-d="${d}">${d}</button>`).join("");
}
function card(i,today){const status=expiryStatus(i.exp,today);const s=status.state; const n=i.name.toLowerCase(); const photo=(/chicken|egg|fish|salmon|protein/.test(n))?"assets/food/chicken-quinoa.jpg":(/tomato|avocado|fruit|banana|apple|vegetable|broccoli|carrot|onion|salad/.test(n))?"assets/food/salad-bowl.jpg":(/dhal|lentil|rice|grain|coconut|milk|dairy|soup/.test(n))?"assets/food/lentil-soup.jpg":"assets/food/hero-healthy-bowl.jpg";
 const t=status.label;
 return `<article class="item ${s}"><div class="item-top"><img class="pantry-item-photo" src="${photo}" alt="${i.name}" loading="lazy"><b>${i.name}</b><button class="rm" data-rm="${i.id}" aria-label="Remove ${i.name}">✕</button></div>
 <div class="qty"><button data-m="${i.id}" aria-label="Less">−</button><span>${i.qty} ${i.unit}</span><button data-p="${i.id}" aria-label="More">+</button></div><span class="tag ${s}">${t}</span></article>`}
function add(name,cat,qty=1,unit="pcs",exp=""){
 const validated=validateAmount(qty,unit);
 if(validated.error){showAmountError(validated.error);return false}
 if(!String(name||"").trim())return false;
 const ex=items.find(i=>i.name.trim().toLowerCase()===name.trim().toLowerCase()&&i.cat===cat&&i.unit.trim().toLowerCase()===validated.unit&&i.exp===exp);
 if(ex){
  const merged=validateAmount(ex.qty+validated.amount,validated.unit);
  if(merged.error){showAmountError(`Combined amount cannot exceed ${MAX_QUANTITY} ${validated.unit}.`);return false}
  ex.qty=merged.amount;
 }else items.push({id:Date.now()+Math.random(),name:name.trim(),cat,qty:validated.amount,unit:validated.unit,exp});
 showAmountError();save();render();return true;
}
document.addEventListener("DOMContentLoaded",()=>{
 $("cat").innerHTML=Object.keys(CATS).map(c=>`<option>${c}</option>`).join("");
 $("quick").innerHTML=QUICK.map(([n,c])=>`<button type="button" class="chip pick" data-q="${n}|${c}">+ ${n}</button>`).join("");
 const qtyInput=$("qty"),unitInput=$("unit");
 const updateQuantityConstraints=()=>{const unit=UNITS[unitInput.value];qtyInput.step=unit&&unit.whole?"1":"0.01";qtyInput.min=unit&&unit.whole?"1":"0.01"};
 unitInput.onchange=()=>{updateQuantityConstraints();showAmountError()};
 qtyInput.oninput=()=>showAmountError();
 updateQuantityConstraints();
 $("addForm").onsubmit=e=>{e.preventDefault();if(add($("name").value,$("cat").value,qtyInput.value,unitInput.value,$("exp").value)){e.target.reset();qtyInput.value=1;unitInput.value="pcs";updateQuantityConstraints();$("name").focus()}};
 $("quick").onclick=e=>{const b=e.target.closest("[data-q]");if(b){const[n,c]=b.dataset.q.split("|");add(n,c)}};
 $("diets").onclick=e=>{const b=e.target.closest("[data-d]");if(!b)return;const d=b.dataset.d;diets=diets.includes(d)?diets.filter(x=>x!==d):[...diets,d];save();render()};
 $("groups").onclick=e=>{const g=a=>items.find(i=>i.id==e.target.dataset[a]);
  if(e.target.dataset.rm){items=items.filter(i=>i.id!=e.target.dataset.rm)}
  else if(e.target.dataset.p){const item=g("p"),updated=validateAmount(item.qty+1,item.unit);if(updated.error){showAmountError(updated.error);return}item.qty=updated.amount}
  else if(e.target.dataset.m){const i=g("m");if(--i.qty<=0)items=items.filter(x=>x!==i)}else return;showAmountError();save();render()};
 $("filter").oninput=render;
 $("clear").onclick=()=>{if(confirm("Remove all pantry items?")){items=[];save();render()}};
 window.addEventListener("storage",e=>{if(e.key==="vp_pantry"){items=load("vp_pantry",[]);render()}});
 if(storedPantry===null)save();
 render();
});

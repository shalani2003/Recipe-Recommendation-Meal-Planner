// Demo-only auth: accounts live in this browser's localStorage (no server).
async function hash(s){try{const b=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(s));return[...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,"0")).join("")}catch{return btoa(unescape(encodeURIComponent(s)))}}
const $=id=>document.getElementById(id);
const users=()=>_l("vp_users",[]);
function fieldErr(id,msg){const el=$(id);el.classList.toggle("bad",!!msg);$(id+"Err").textContent=msg||"";return !msg}
function showAlert(m){const a=$("alert");a.textContent=m;a.classList.add("show")}
function startSession(u){_s("vp_session",{email:u.email});_s("vp_user",{..._l("vp_user",{}),name:u.name});location.href="index.html"}
document.querySelectorAll("[data-pw]").forEach(b=>b.onclick=()=>{const i=$(b.dataset.pw),s=i.type==="password";i.type=s?"text":"password";b.textContent=s?"Hide":"Show"});
const emailOk=e=>/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e);
if(_l("vp_session",null))location.replace("index.html");
if($("loginForm"))$("loginForm").onsubmit=async e=>{e.preventDefault();$("alert").classList.remove("show");
 const em=$("email").value.trim().toLowerCase(),pw=$("pw").value;
 const a=fieldErr("email",emailOk(em)?"":"Enter a valid email"),b=fieldErr("pw",pw?"":"Enter your password");if(!(a&&b))return;
 const u=users().find(x=>x.email===em);
 if(!u||u.hash!==await hash(pw))return showAlert("Email or password is incorrect.");
 startSession(u)};
if($("regForm"))$("regForm").onsubmit=async e=>{e.preventDefault();$("alert").classList.remove("show");
 const n=$("name").value.trim(),em=$("email").value.trim().toLowerCase(),pw=$("pw").value,c=$("pw2").value;
 const ok=[fieldErr("name",n.length>=2?"":"Enter your name"),fieldErr("email",emailOk(em)?"":"Enter a valid email"),
  fieldErr("pw",pw.length>=8&&/\d/.test(pw)?"":"Use 8+ characters with at least one number"),fieldErr("pw2",c===pw?"":"Passwords do not match")];
 if(!$("terms").checked){showAlert("Please accept the terms to continue.");return}
 if(ok.includes(false))return;
 if(users().some(x=>x.email===em))return showAlert("An account with this email already exists. Try logging in.");
 const u={name:n,email:em,hash:await hash(pw)};_s("vp_users",[...users(),u]);startSession(u)};

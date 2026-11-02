// Auth with Flask backend (SQLite). Talks to /api/* on the same server.
const $=id=>document.getElementById(id);
async function api(path,payload,method="POST"){
 try{
  const r=await fetch(path,{method,headers:{"Content-Type":"application/json"},credentials:"same-origin",body:method==="GET"?undefined:JSON.stringify(payload||{})});
  const d=await r.json().catch(()=>({}));
  return{ok:r.ok,status:r.status,data:d};
 }catch{
  return{ok:false,status:0,data:{error:"Cannot reach the server. Start the Flask backend and open http://127.0.0.1:5000/login.html"}};
 }
}
function fieldErr(id,msg){const el=$(id);el.classList.toggle("bad",!!msg);$(id+"Err").textContent=msg||"";return !msg}
function showAlert(m,ok){const a=$("alert");a.textContent=m;a.classList.add("show")}
const ACCOUNT_KEYS=["vp_pantry","vp_diets","vp_plan","vp_shop","vp_fav","vp_rate","vp_health","vp_profile","vp_settings","vp_water","vp_diet_profiles"];
// Browser-stored data is shared by every account in this browser, so it is cleared when a different account logs in.
function clearOtherAccountData(email){const prev=_l("vp_session",null);if(prev&&prev.email&&prev.email!==email)ACCOUNT_KEYS.forEach(k=>localStorage.removeItem(k))}
async function startSession(u,go=true){
 clearOtherAccountData(u.email);
 const d=await api("/api/dietary",null,"GET");
 const diet=d.ok?d.data:{diets:[],allergies:[],onboarding_completed:false};
 const profiles=_l("vp_diet_profiles",{});profiles[u.email]={...(profiles[u.email]||{}),completed:!!diet.onboarding_completed};
 _s("vp_diet_profiles",profiles);_s("vp_session",{email:u.email});_s("vp_user",{..._l("vp_user",{}),name:u.name});_s("vp_diets",diet.diets||[]);
 if(go)location.href=diet.onboarding_completed?"index.html":"onboarding.html";
}
document.querySelectorAll("[data-pw]").forEach(b=>b.onclick=()=>{const i=$(b.dataset.pw),s=i.type==="password";i.type=s?"text":"password";b.textContent=s?"Hide":"Show"});
const emailOk=e=>/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e);
const slideshow=document.querySelector(".auth-slideshow");
if(slideshow){const slides=slideshow.querySelectorAll("img");let current=0;
 setInterval(()=>{slides[current].classList.remove("active");current=(current+1)%slides.length;slides[current].classList.add("active")},4000)}

// Already logged in (and the server agrees)? Go to the dashboard.
if(_l("vp_session",null)){
 fetch("/api/me",{credentials:"same-origin"}).then(async r=>{
  if(r.ok){const d=await r.json().catch(()=>({}));if(d.user)startSession(d.user)}
  else if(r.status===401){localStorage.removeItem("vp_session")}
 }).catch(()=>{});
}

if($("loginForm"))$("loginForm").onsubmit=async e=>{e.preventDefault();$("alert").classList.remove("show");
 const em=$("email").value.trim().toLowerCase(),pw=$("pw").value;
 const a=fieldErr("email",emailOk(em)?"":"Enter a valid email"),b=fieldErr("pw",pw?"":"Enter your password");if(!(a&&b))return;
 const r=await api("/api/login",{email:em,password:pw});
 if(!r.ok)return showAlert(r.data.error||"Login failed. Please try again.");
 startSession(r.data.user)};
if($("loginForm")&&new URLSearchParams(location.search).has("registered"))showAlert("Account created. Log in to continue.");

if($("regForm"))$("regForm").onsubmit=async e=>{e.preventDefault();$("alert").classList.remove("show");
 const n=$("name").value.trim(),em=$("email").value.trim().toLowerCase(),pw=$("pw").value,c=$("pw2").value;
 const ok=[fieldErr("name",n.length>=2?"":"Enter your name"),fieldErr("email",emailOk(em)?"":"Enter a valid email"),
  fieldErr("pw",pw.length>=8&&/\d/.test(pw)?"":"Use 8+ characters with at least one number"),fieldErr("pw2",c===pw?"":"Passwords do not match")];
 if(!$("terms").checked){showAlert("Please accept the terms to continue.");return}
 if(ok.includes(false))return;
 const r=await api("/api/register",{name:n,email:em,password:pw});
 if(!r.ok)return showAlert(r.data.error||"Registration failed. Please try again.");
 // The recovery code is shown once. It is needed to reset a forgotten password.
 window.prompt("Your recovery code (copy it and keep it safe). You need it to reset your password:",r.data.recovery_code);
 await api("/api/logout");localStorage.removeItem("vp_session");location.href="login.html?registered=1"};

if($("resetForm"))$("resetForm").onsubmit=async e=>{e.preventDefault();$("alert").classList.remove("show");
 const em=$("email").value.trim().toLowerCase(),code=$("code").value.trim(),pw=$("pw").value,c=$("pw2").value;
 const ok=[fieldErr("email",emailOk(em)?"":"Enter a valid email"),fieldErr("code",code?"":"Enter your recovery code"),
  fieldErr("pw",pw.length>=8&&/\d/.test(pw)?"":"Use 8+ characters with at least one number"),
  fieldErr("pw2",c===pw?"":"Passwords do not match")];
 if(ok.includes(false))return;
 const step1=await api("/api/forgot-password",{email:em,recovery_code:code});
 if(!step1.ok)return showAlert(step1.data.error||"Could not verify your details.");
 const r=await api("/api/reset-password",{token:step1.data.reset_token,password:pw});
 if(!r.ok)return showAlert(r.data.error||"Could not reset the password.");
 window.prompt("Password changed. This is your NEW recovery code (copy it; the old one no longer works):",r.data.recovery_code);
 showAlert("Your password has been reset. You can now log in.");
 $("resetForm").reset();
 setTimeout(()=>location.href="login.html",1200)};

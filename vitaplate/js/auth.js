// Auth with Flask backend (SQLite). Talks to /api/* on the same server.
const $=id=>document.getElementById(id);
async function api(path,payload){
 try{
  const r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},credentials:"same-origin",body:JSON.stringify(payload||{})});
  const d=await r.json().catch(()=>({}));
  return{ok:r.ok,status:r.status,data:d};
 }catch{
  return{ok:false,status:0,data:{error:"Cannot reach the server. Start the Flask backend and open http://127.0.0.1:5000/login.html"}};
 }
}
function fieldErr(id,msg){const el=$(id);el.classList.toggle("bad",!!msg);$(id+"Err").textContent=msg||"";return !msg}
function showAlert(m,ok){const a=$("alert");a.textContent=m;a.classList.add("show")}
function startSession(u){const profile=_l("vp_diet_profiles",{})[u.email];_s("vp_session",{email:u.email});_s("vp_user",{..._l("vp_user",{}),name:u.name});_s("vp_diets",profile?.diet==="Vegetarian"?["Vegetarian"]:[]);location.href=profile?.completed?"index.html":"onboarding.html"}
document.querySelectorAll("[data-pw]").forEach(b=>b.onclick=()=>{const i=$(b.dataset.pw),s=i.type==="password";i.type=s?"text":"password";b.textContent=s?"Hide":"Show"});
const emailOk=e=>/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e);
const slideshow=document.querySelector(".auth-slideshow");
if(slideshow){const slides=slideshow.querySelectorAll("img");let current=0;
 setInterval(()=>{slides[current].classList.remove("active");current=(current+1)%slides.length;slides[current].classList.add("active")},4000)}

// Already logged in (and the server agrees)? Go to the dashboard.
if(_l("vp_session",null)){
 fetch("/api/me",{credentials:"same-origin"}).then(async r=>{
    if(r.ok){const d=await r.json().catch(()=>({}));const u=d.user||{};const email=u.email||_l("vp_session",{}).email;const profile=_l("vp_diet_profiles",{})[email];if(u.email)_s("vp_session",{email:u.email});if(u.name)_s("vp_user",{..._l("vp_user",{}),name:u.name});_s("vp_diets",profile?.diet==="Vegetarian"?["Vegetarian"]:[]);location.replace(profile?.completed?"index.html":"onboarding.html")}
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
 location.href="login.html?registered=1"};

if($("resetForm"))$("resetForm").onsubmit=async e=>{e.preventDefault();$("alert").classList.remove("show");
 const em=$("email").value.trim().toLowerCase(),pw=$("pw").value,c=$("pw2").value;
 const ok=[fieldErr("email",emailOk(em)?"":"Enter a valid email"),
  fieldErr("pw",pw.length>=8&&/\d/.test(pw)?"":"Use 8+ characters with at least one number"),
  fieldErr("pw2",c===pw?"":"Passwords do not match")];
 if(ok.includes(false))return;
 const r=await api("/api/reset-password",{email:em,password:pw});
 if(!r.ok)return showAlert(r.data.error||"Could not reset the password.");
 showAlert("Your password has been reset. You can now log in.");
 $("resetForm").reset();
 setTimeout(()=>location.href="login.html",1200)};

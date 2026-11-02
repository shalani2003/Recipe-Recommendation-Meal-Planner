const $=id=>document.getElementById(id);
let user={name:"Friend"};
let currentStep=0;
const steps=[...document.querySelectorAll(".onboarding-step")];
const dots=[...document.querySelectorAll(".step-dots span")];
const dietInputs=[...document.querySelectorAll('input[name="diet"]')];
const allergyInputs=[...document.querySelectorAll('input[name="allergy"]')];
const conditionInputs=[...document.querySelectorAll('input[name="condition"]')];
async function api(path,method="GET",payload){
  try{
    const response=await fetch(path,{method,credentials:"same-origin",
      headers:payload===undefined?{}:{"Content-Type":"application/json"},
      body:payload===undefined?undefined:JSON.stringify(payload)});
    const data=await response.json().catch(()=>({}));
    if(response.status===401){location.replace("login.html");return{ok:false,data:{error:"Please log in again."}}}
    return{ok:response.ok,data};
  }catch(error){
    return{ok:false,data:{error:"Cannot reach the server. Start the backend and try again."}};
  }
}

function setExclusiveNone(inputs){
  inputs.forEach(input=>input.addEventListener("change",()=>{
    if(input.checked&&input.value==="None")inputs.filter(item=>item!==input).forEach(item=>item.checked=false);
    if(input.checked&&input.value!=="None"){const noneInput=inputs.find(item=>item.value==="None");if(noneInput)noneInput.checked=false}
  }));
}
setExclusiveNone(allergyInputs);
setExclusiveNone(conditionInputs);

function selected(inputs){return inputs.filter(input=>input.checked&&input.value!=="None").map(input=>input.value)}
function getAnswers(){
  const allergies=selected(allergyInputs);
  const conditions=selected(conditionInputs);
  const extraAllergy=$("allergyOther").value.trim();
  const extraCondition=$("conditionOther").value.trim();
  if(extraAllergy)allergies.push(extraAllergy);
  if(extraCondition)conditions.push(extraCondition);
  return{diet:dietInputs.find(input=>input.checked)?.value||"balanced",allergies,conditions};
}
function renderWelcome(){
  const answers=getAnswers();
  $("welcomeTitle").textContent=`Welcome, ${user.name}!`;
  const savedDetails=[answers.allergies.length?"allergy notes":null,answers.conditions.length?"health considerations":null].filter(Boolean);
  const detailsText=savedDetails.length?` We’ve saved your ${savedDetails.join(" and ")} with your profile.`:" Your profile is ready for a more personal experience.";
  $("welcomeCopy").textContent=`Your ${answers.diet.toLowerCase()} meal journey starts here.${detailsText} Your dashboard is ready.`;
  const summary=[];
  summary.push(answers.allergies.length?`Allergies noted: ${answers.allergies.join(", ")}.`:"No food allergies added.");
  summary.push(answers.conditions.length?`Health considerations noted: ${answers.conditions.join(", ")}.`:"No health conditions added.");
  $("welcomeSummary").textContent=summary.join(" ");
}
function showError(message){
  $("saveError").textContent=message;
  $("dietError").textContent=message;
}
function showStep(index){
  currentStep=index;
  steps.forEach((step,i)=>step.hidden=i!==index);
  dots.forEach((dot,i)=>dot.classList.toggle("is-current",i===index));
  $("progressLabel").textContent=`Step ${index+1} of ${steps.length}`;
  $("progressBar").style.width=`${((index+1)/steps.length)*100}%`;
  $("backButton").hidden=index===0;
  $("nextButton").textContent=index===steps.length-1?"Go to dashboard":"Continue";
}
async function saveProfile(){
  const answers=getAnswers();
  const diets=answers.diet==="Vegetarian"?["Vegetarian"]:[];
  $("nextButton").disabled=true;
  showError("");
  const dietary=await api("/api/dietary","PUT",{diets,allergies:answers.allergies,onboarding_completed:true});
  if(!dietary.ok){
    showError(dietary.data.error||"Could not save your dietary preferences.");
    $("nextButton").disabled=false;
    return;
  }
  const profile=await api("/api/profile","PUT",{health_notes:answers.conditions.join(", ")});
  if(!profile.ok){
    showError(profile.data.error||"Could not save your health considerations.");
    $("nextButton").disabled=false;
    return;
  }
  location.href="index.html";
}

$("backButton").addEventListener("click",()=>showStep(Math.max(0,currentStep-1)));
$("nextButton").addEventListener("click",()=>{
  if(currentStep===0&&!dietInputs.some(input=>input.checked)){
    $("dietError").textContent="Choose an eating style to continue.";
    return;
  }
  $("dietError").textContent="";
  if(currentStep===steps.length-1){saveProfile();return}
  if(currentStep===steps.length-2)renderWelcome();
  showStep(currentStep+1);
});
async function initialize(){
  $("nextButton").disabled=true;
  const [me,dietary,profile]=await Promise.all([
    api("/api/me"),
    api("/api/dietary"),
    api("/api/profile")
  ]);
  if(!me.ok||!dietary.ok||!profile.ok){
    showError(me.data.error||dietary.data.error||profile.data.error||"Could not load your profile.");
    return;
  }
  user=me.data.user;
  VP.user.name=user.name;
  if(dietary.data.onboarding_completed){location.replace("index.html");return}
  const dietRadio=dietInputs.find(input=>input.value==="Vegetarian");
  if(dietRadio&&dietary.data.diets.includes("Vegetarian"))dietRadio.checked=true;
  const selectedAllergies=new Set(dietary.data.allergies.map(value=>value.toLowerCase()));
  allergyInputs.forEach(input=>{input.checked=selectedAllergies.has(input.value.toLowerCase())});
  const knownAllergies=new Set(allergyInputs.map(input=>input.value.toLowerCase()));
  $("allergyOther").value=dietary.data.allergies.filter(value=>!knownAllergies.has(value.toLowerCase())).join(", ");
  const notes=(profile.data.health_notes||"").split(",").map(value=>value.trim()).filter(Boolean);
  conditionInputs.forEach(input=>{input.checked=notes.includes(input.value)});
  const knownConditions=new Set(conditionInputs.map(input=>input.value));
  $("conditionOther").value=notes.filter(value=>!knownConditions.has(value)).join(", ");
  $("nextButton").disabled=false;
  showStep(0);
}
showStep(0);
initialize();
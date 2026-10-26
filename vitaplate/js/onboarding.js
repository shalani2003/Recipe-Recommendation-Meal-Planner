const $=id=>document.getElementById(id);
const session=_l("vp_session",null);
const users=_l("vp_users",[]);
const user=users.find(item=>item.email===session?.email);
const profiles=_l("vp_diet_profiles",{});
if(!session||!user)location.replace("login.html");
else if(profiles[user.email]?.completed)location.replace("index.html");

let currentStep=0;
const steps=[...document.querySelectorAll(".onboarding-step")];
const dots=[...document.querySelectorAll(".step-dots span")];
const dietInputs=[...document.querySelectorAll('input[name="diet"]')];
const allergyInputs=[...document.querySelectorAll('input[name="allergy"]')];
const conditionInputs=[...document.querySelectorAll('input[name="condition"]')];

function setExclusiveNone(inputs){
  inputs.forEach(input=>input.addEventListener("change",()=>{
    const none=input.value==="None";
    if(input.checked&&none)inputs.filter(item=>item!==input).forEach(item=>item.checked=false);
    if(input.checked&&!none){const noneInput=inputs.find(item=>item.value==="None");if(noneInput)noneInput.checked=false}
  }));
}
setExclusiveNone(allergyInputs);
setExclusiveNone(conditionInputs);

function selected(inputs){return inputs.filter(input=>input.checked&&input.value!=="None").map(input=>input.value)}
function renderWelcome(){
  const diet=dietInputs.find(input=>input.checked)?.value||"balanced";
  const allergies=selected(allergyInputs);
  const conditions=selected(conditionInputs);
  const extraAllergy=$("allergyOther").value.trim();
  const extraCondition=$("conditionOther").value.trim();
  if(extraAllergy)allergies.push(extraAllergy);
  if(extraCondition)conditions.push(extraCondition);
  $("welcomeTitle").textContent=`Welcome, ${user.name}!`;
  const savedDetails=[allergies.length?"allergy notes":null,conditions.length?"health considerations":null].filter(Boolean);
  const detailsText=savedDetails.length?` We’ve saved your ${savedDetails.join(" and ")} with your profile.`:" Your profile is ready for a more personal experience.";
  $("welcomeCopy").textContent=`Your ${diet.toLowerCase()} meal journey starts here.${detailsText} Your dashboard is ready.`;
  const summary=[];
  summary.push(allergies.length?`Allergies noted: ${allergies.join(", ")}.`:"No food allergies added.");
  summary.push(conditions.length?`Health considerations noted: ${conditions.join(", ")}.`:"No health conditions added.");
  $("welcomeSummary").textContent=summary.join(" ");
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
function saveProfile(){
  const diet=dietInputs.find(input=>input.checked).value;
  const allergies=selected(allergyInputs);
  const conditions=selected(conditionInputs);
  const allergyOther=$("allergyOther").value.trim();
  const conditionOther=$("conditionOther").value.trim();
  if(allergyOther)allergies.push(allergyOther);
  if(conditionOther)conditions.push(conditionOther);
  profiles[user.email]={diet,allergies,conditions,completed:true};
  _s("vp_diet_profiles",profiles);
  _s("vp_diets",diet==="Vegetarian"?["Vegetarian"]:[]);
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
showStep(0);
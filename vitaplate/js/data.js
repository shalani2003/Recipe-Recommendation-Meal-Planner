// Shared sample catalog and helpers; account state is hydrated from the API.
const isRecord=value=>value!==null&&typeof value==="object"&&!Array.isArray(value);
const isStringArray=value=>Array.isArray(value)&&value.every(item=>typeof item==="string");
const isFiniteNumber=value=>typeof value==="number"&&Number.isFinite(value);
const isPantryStorage=value=>Array.isArray(value)&&value.every(item=>
  isRecord(item)&&typeof item.name==="string"&&item.name.trim().length>0&&
  (item.category===undefined||typeof item.category==="string")&&
  (item.quantity===undefined||isFiniteNumber(item.quantity))&&
  (item.qty===undefined||isFiniteNumber(item.qty))&&
  (item.unit===undefined||typeof item.unit==="string")
);
const isShoppingStorage=value=>Array.isArray(value)&&value.every(item=>
  isRecord(item)&&typeof item.name==="string"&&item.name.trim().length>0&&
  (item.done===undefined||typeof item.done==="boolean")&&
  (item.quantity===undefined||item.quantity===null||isFiniteNumber(item.quantity))&&
  (item.unit===undefined||item.unit===null||typeof item.unit==="string")
);
const STORAGE_DAYS=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"];
const STORAGE_MEALS=["Breakfast","Lunch","Dinner"];
const isMealPlanStorage=value=>isRecord(value)&&Object.keys(value).every(day=>
  STORAGE_DAYS.includes(day)&&isRecord(value[day])&&Object.keys(value[day]).every(meal=>
    STORAGE_MEALS.includes(meal)&&
    (typeof value[day][meal]==="string"||isFiniteNumber(value[day][meal]))
  )
);
const isRatingsStorage=value=>isRecord(value)&&Object.keys(value).every(name=>
  isFiniteNumber(value[name])&&value[name]>=0&&value[name]<=5
);
const safeStorage={
  getJSON(key,fallback,validate){
    try{
      const raw=localStorage.getItem(key);
      if(raw===null)return fallback;
      const value=JSON.parse(raw);
      return typeof validate==="function"&&!validate(value)?fallback:value;
    }catch(error){return fallback}
  },
  setJSON(key,value,validate){
    try{
      if(typeof validate==="function"&&!validate(value))return false;
      const serialized=JSON.stringify(value);
      if(serialized===undefined)return false;
      localStorage.setItem(key,serialized);
      return true;
    }catch(error){return false}
  },
  getString(key,fallback,validate){
    try{
      const value=localStorage.getItem(key);
      return typeof value==="string"&&(!validate||validate(value))?value:fallback;
    }catch(error){return fallback}
  },
  setString(key,value,validate){
    try{
      if(typeof value!=="string"||(validate&&!validate(value)))return false;
      localStorage.setItem(key,value);
      return true;
    }catch(error){return false}
  },
  remove(key){
    try{localStorage.removeItem(key);return true}catch(error){return false}
  }
};
const _l=(k,d,validate)=>safeStorage.getJSON(k,d,validate);
const _s=(k,v,validate)=>safeStorage.setJSON(k,v,validate);
const HEALTH_LIMITS={height:{min:100,max:230},weight:{min:25,max:250},bmi:{min:18.5,max:40}};
const PANTRY_CATEGORIES=["Vegetables","Fruits","Grains","Protein","Dairy","Spices & sauces","Other"];
const normalizePantryCategory=value=>{
  if(typeof value!=="string")return "";
  return PANTRY_CATEGORIES.find(category=>category.toLowerCase()===value.trim().toLowerCase())||"";
};
const escapeHtml=value=>String(value==null?"":value).replace(/[&<>"']/g,character=>({
  "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
})[character]);
window.VP={
  user:{name:"Friend",goalKcal:1800,profilePicture:"",macros:{protein:[62,90],carbs:[140,210],fat:[38,60]}},
  accountId:null,
  pantry:[],
  pantryCategories:PANTRY_CATEGORIES,
  normalizePantryCategory,
  escapeHtml,
  safeStorage,
  storageValidators:{
    isRecord,
    isStringArray,
    isPantryStorage,
    isShoppingStorage,
    isMealPlanStorage,
    isRatingsStorage
  },
  diets:[],
  today:[{meal:"Breakfast",name:"Coconut roti & pol sambol",emoji:"🥥",kcal:420},{meal:"Lunch",name:"Rice, dhal & gotukola sallad",emoji:"🍛",kcal:610},{meal:"Snack",name:"Banana & peanuts",emoji:"🍌",kcal:180}],
  picks:[{name:"Chicken & broccoli bowl",emoji:"🥦",match:92,kcal:480},{name:"Pumpkin curry",emoji:"🎃",match:85,kcal:390},{name:"Egg fried rice",emoji:"🍳",match:78,kcal:520}]
};
function resetAccountState(user){
  VP.accountId=user&&user.id!==undefined?user.id:null;
  VP.user={
    name:user&&user.name||"Friend",
    goalKcal:1800,
    profilePicture:"",
    macros:{protein:[62,90],carbs:[140,210],fat:[38,60]}
  };
  VP.pantry=[];
  VP.diets=[];
  VP.today=[
    {meal:"Breakfast",name:"Coconut roti & pol sambol",emoji:"🥥",kcal:420},
    {meal:"Lunch",name:"Rice, dhal & gotukola sallad",emoji:"🍛",kcal:610},
    {meal:"Snack",name:"Banana & peanuts",emoji:"🍌",kcal:180}
  ];
  VP.picks=[
    {name:"Chicken & broccoli bowl",emoji:"🥦",match:92,kcal:480},
    {name:"Pumpkin curry",emoji:"🎃",match:85,kcal:390},
    {name:"Egg fried rice",emoji:"🍳",match:78,kcal:520}
  ];
  ["profile","dietary","pantrySummary","apiError"].forEach(key=>delete VP[key]);
}
const V="Vegetarian",VG="Vegan",GF="Gluten-free",DF="Dairy-free",H="Halal";
const R=[
 {id:1,name:"Chicken & broccoli bowl",kind:"broccoli",time:25,kcal:480,p:38,c:40,f:16,diets:[H,DF,GF],ing:["Chicken","Broccoli","Rice"]},
 {id:2,name:"Pumpkin dhal curry",kind:"carrot",time:30,kcal:390,p:16,c:58,f:10,diets:[V,VG,GF,DF,H],ing:["Pumpkin","Dhal","Coconut","Rice"]},
 {id:3,name:"Egg fried rice",kind:"egg",time:15,kcal:520,p:18,c:70,f:18,diets:[V,DF,H],ing:["Eggs","Rice","Onion"]},
 {id:4,name:"Tomato omelette",kind:"tomato",time:10,kcal:310,p:20,c:8,f:22,diets:[V,GF,H,DF],ing:["Eggs","Tomato","Onion"]},
 {id:5,name:"Avocado toast",kind:"avocado",time:10,kcal:340,p:9,c:32,f:20,diets:[V,VG,DF,H],ing:["Avocado","Bread","Tomato"]},
 {id:6,name:"Coconut roti & sambol",kind:"bowl",time:20,kcal:420,p:9,c:60,f:15,diets:[V,VG,DF,H],ing:["Coconut","Flour","Onion"]},
 {id:7,name:"Carrot & lentil soup",kind:"carrot",time:35,kcal:280,p:15,c:40,f:5,diets:[V,VG,GF,DF,H],ing:["Carrot","Dhal","Onion"]},
 {id:8,name:"Creamy chicken curry",kind:"bowl",time:40,kcal:560,p:42,c:22,f:32,diets:[GF,H],ing:["Chicken","Coconut","Onion","Curry powder"]}
];
const DAYS=["Mon","Tue","Wed","Thu","Fri","Sat","Sun"],MEALS=["Breakfast","Lunch","Dinner"];
const INGREDIENT_ALIASES={
  eggs:"egg", tomatoes:"tomato", onions:"onion", carrots:"carrot", lentils:"lentil", chickpeas:"chickpea",
  peanuts:"peanut", almonds:"almond", cashews:"cashew", walnuts:"walnut", mushrooms:"mushroom",
  potatoes:"potato", apples:"apple", bananas:"banana", peppers:"pepper"
};
const INGREDIENT_DESCRIPTORS=/^(basmati|samba|jasmine|white|brown|red|green|fresh|frozen|baby|boneless|skinless|large|small|medium|can|tin|pack|bunch)\s+|\s+(breast|thigh|fillet|minced|ground|diced|chopped|sliced)$/g;
function normalizeIngredient(value){
  let text=String(value||"").toLowerCase().replace(/[\u00a0\u2013\u2014]/g," ").replace(/[^a-z0-9\s]/g," ");
  text=text.replace(/^\s*(?:\d+(?:\.\d+)?|\d+\/\d+)\s*(?:g|kg|ml|l|oz|lb|lbs|cup|cups|tbsp|tsp|teaspoons?|tablespoons?|pieces?|pcs|cloves?)?\s*/," ");
  text=text.replace(/\s+/g," ").trim();
  text=text.replace(/\b(eggs|tomatoes|onions|carrots|lentils|chickpeas|peanuts|almonds|cashews|walnuts|mushrooms|potatoes|apples|bananas|peppers)\b/g,word=>INGREDIENT_ALIASES[word]||word);
  text=text.replace(/\b(\w+)s\b/g,"$1");
  return text.replace(INGREDIENT_DESCRIPTORS," ").trim();
}
const ingredientMatches=(pantryIngredient,recipeIngredient)=>{
  const pantry=normalizeIngredient(pantryIngredient), recipe=normalizeIngredient(recipeIngredient);
  if(!pantry||!recipe)return false;
  return pantry===recipe;
};
const haveIng=ing=>VP.pantry.some(item=>ingredientMatches(item?.name,ing));
const matchPct=r=>{
  const ingredients=r.ing||r.ingredients||[];
  return ingredients.length?Math.round(ingredients.filter(haveIng).length/ingredients.length*100):0;
};
function savedFoodRestrictions(){
  const allergies=[];
  const add=value=>String(value||"").split(",").map(item=>item.trim()).filter(item=>item&&item.toLowerCase()!=="none").forEach(item=>allergies.push(item));
  const profile=VP.profile||{};
  const dietary=VP.dietary||{};
  add(profile.allergies); add(profile.health_notes); (dietary.allergies||[]).forEach(add);
  return [...new Set(allergies.map(item=>item.toLowerCase()))];
}
const allergyIngredients={
  peanuts:["peanut"],"tree nuts":["almond","cashew","walnut","nut"],milk:["milk","yogurt","cheese","butter","cream","dairy"],
  eggs:["egg"],soy:["soy","tofu"],wheat:["wheat","flour","bread","pasta"],fish:["fish","salmon","tuna"],shellfish:["shrimp","prawn","shellfish"]
};
function restrictionTerms(restriction){
  const key=normalizeIngredient(restriction);
  if(key.includes("peanut"))return allergyIngredients.peanuts;
  if(key.includes("tree nut")||key.includes("nut"))return ["almond","cashew","walnut","peanut"];
  if(key.includes("milk")||key.includes("dairy")||key.includes("lactose"))return allergyIngredients.milk;
  if(key.includes("egg"))return allergyIngredients.eggs;
  if(key.includes("soy"))return allergyIngredients.soy;
  if(key.includes("wheat")||key.includes("gluten")||key.includes("celiac"))return allergyIngredients.wheat;
  if(key.includes("fish"))return allergyIngredients.fish;
  if(key.includes("shellfish")||key.includes("prawn")||key.includes("shrimp"))return allergyIngredients.shellfish;
  if(key.includes("diabet")||key.includes("low sugar"))return ["sugar","honey"];
  return [key];
}
function ingredientConflicts(ingredient,restriction){
  const normalized=normalizeIngredient(ingredient);
  return restrictionTerms(restriction).some(term=>ingredientMatches(normalized,term));
}
function recipeHasConflict(recipe){
  return savedFoodRestrictions().some(restriction=>{
    return (recipe.ing||[]).concat(recipe.ingredients||[]).some(ingredient=>ingredientConflicts(ingredient,restriction));
  });
}
function inferredDietOk(recipe,diet){
  const ingredients=recipe.ing||recipe.ingredients||[];
  const has=terms=>ingredients.some(ingredient=>terms.some(term=>ingredientConflicts(ingredient,term)));
  if(diet==="Vegetarian")return !has(["chicken","beef","pork","fish","salmon","tuna","shrimp","prawn"]);
  if(diet==="Vegan")return !has(["chicken","beef","pork","fish","salmon","tuna","shrimp","prawn","egg","milk","yogurt","cheese","butter","cream","honey"]);
  if(diet==="Gluten-free")return !has(["wheat","flour","bread","pasta"]);
  if(diet==="Dairy-free")return !has(["milk","yogurt","cheese","butter","cream","dairy"]);
  if(diet==="Nut-free")return !has(["peanut","almond","cashew","walnut","nut"]);
  if(diet==="Halal")return !has(["pork","ham","bacon","alcohol"]);
  if(diet==="Low sugar")return !has(["sugar","honey"]);
  return true;
}
const dietOk=r=>(VP.diets||[]).every(d=>inferredDietOk(r,d))&&!recipeHasConflict(r);
// Cartoon food characters (inline SVG)
function char(kind,size=90){
  const B={
   tomato:['<circle cx="50" cy="56" r="38" fill="#ef5a45"/><path d="M50 20q-14-4-18 6 10 0 18-2 8 2 18 2-4-10-18-6z" fill="#4c9a3b"/>',55],
   egg:['<ellipse cx="50" cy="55" rx="32" ry="38" fill="#fffaf0" stroke="#e8dcc0" stroke-width="3"/><circle cx="50" cy="72" r="0"/>',55],
   avocado:['<ellipse cx="50" cy="55" rx="33" ry="40" fill="#5a9a3f"/><ellipse cx="50" cy="60" rx="25" ry="31" fill="#d9ec9c"/>',55],
   carrot:['<path d="M28 30q22-12 44 0-6 40-22 64-16-24-22-64z" fill="#f28c28"/><path d="M50 30q-12-16-4-22 6 8 4 22 2-14 12-20 4 8-12 20z" fill="#4c9a3b"/>',52],
   broccoli:['<rect x="42" y="58" width="16" height="36" rx="6" fill="#9fd07a"/><circle cx="30" cy="44" r="20" fill="#3f9a45"/><circle cx="70" cy="44" r="20" fill="#3f9a45"/><circle cx="50" cy="30" r="22" fill="#3f9a45"/>',46],
   bowl:['<path d="M10 52h80a40 40 0 0 1-80 0z" fill="#f7d4c2" stroke="#e0a58a" stroke-width="3"/><path d="M20 52q30-38 60 0z" fill="#6aa84f"/>',68]
  }[kind]||[];const y=B[1]||55;
  return `<svg class="char" viewBox="0 0 100 100" width="${size}" height="${size}" aria-hidden="true">${B[0]}<circle cx="38" cy="${y}" r="4" fill="#2a2d26"/><circle cx="62" cy="${y}" r="4" fill="#2a2d26"/><path d="M42 ${y+10}q8 8 16 0" stroke="#2a2d26" stroke-width="3" fill="none" stroke-linecap="round"/><circle cx="30" cy="${y+8}" r="5" fill="#ff8f80" opacity=".55"/><circle cx="70" cy="${y+8}" r="5" fill="#ff8f80" opacity=".55"/></svg>`}

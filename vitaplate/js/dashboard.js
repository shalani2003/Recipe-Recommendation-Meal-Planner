const dashboardRequest = async (path, method = "GET", data) => {
  const response = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: data === undefined ? {} : {"Content-Type": "application/json"},
    body: data === undefined ? undefined : JSON.stringify(data)
  });
  const result = await response.json().catch(() => ({}));
  if (response.status === 401) {
    location.replace("login.html");
    throw new Error("Please sign in again.");
  }
  if (!response.ok) throw new Error(result.error || "Could not load dashboard data.");
  return result;
};

const localDay = () => {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
};

function recommendationCard(recipe) {
  const card = document.createElement("article");
  card.className = "recipe-card";
  const image = document.createElement("img");
  image.className = "recipe-photo";
  image.src = recipe.image || "assets/food/hero-healthy-bowl.jpg";
  image.alt = recipe.name;
  image.loading = "lazy";
  const body = document.createElement("div");
  body.className = "recipe-body";
  const title = document.createElement("h3");
  title.textContent = recipe.name;
  const meta = document.createElement("div");
  meta.className = "recipe-meta";
  meta.textContent = recipe.time_min ? `${recipe.time_min} min` : "Recipe";
  const link = document.createElement("a");
  link.className = "recipe-button";
  link.href = "recipes.html";
  link.textContent = "View recipes";
  body.append(title, meta, link);
  card.append(image, body);
  return card;
}

async function loadRecommendations() {
  const container = document.getElementById("recommendations");
  renderState(container, "loading", "Loading recommendations");
  try {
    const data = await dashboardRequest("/api/recommendations");
    const recommendations = data.recommendations || [];
    if (!recommendations.length) {
      renderState(container, "empty", "No recipes are available yet. Add recipes to get recommendations.");
      return;
    }
    container.replaceChildren(...recommendations.map(recommendationCard));
  } catch (error) {
    renderState(container, "error", error.message, loadRecommendations);
  }
}

async function loadMealPlan() {
  const container = document.getElementById("mealPlanList");
  renderState(container, "loading", "Loading today's meal plan");
  try {
    const data = await dashboardRequest("/api/meal-plan");
    const today = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][new Date().getDay()];
    const meals = (data.meals || []).filter(item => item.day === today);
    if (!meals.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.append("Nothing planned for today. ");
      const link = document.createElement("a");
      link.href = "planner.html";
      link.textContent = "Plan meals";
      empty.append(link);
      container.replaceChildren(empty);
      return;
    }
    container.replaceChildren(...meals.map(item => {
      const row = document.createElement("div");
      row.className = "meal-row";
      const details = document.createElement("div");
      const name = document.createElement("div");
      name.className = "meal-name";
      name.textContent = item.meal;
      const recipe = document.createElement("small");
      recipe.textContent = item.recipe_name;
      details.append(name, recipe);
      row.append(details);
      return row;
    }));
  } catch (error) {
    renderState(container, "error", error.message, loadMealPlan);
  }
}

let waterGlasses = 0;
async function saveWater(next) {
  try {
    const data = await dashboardRequest("/api/water", "PUT", {day: localDay(), glasses: next});
    waterGlasses = data.glasses;
    updateWater();
  } catch (error) {
    const status = document.getElementById("waterStatus");
    status.textContent = error.message;
  }
}

function updateWater() {
  document.getElementById("waterCount").textContent = waterGlasses;
  document.getElementById("waterBar").style.width = `${Math.min(waterGlasses / 8 * 100, 100)}%`;
  document.getElementById("waterMinus").disabled = waterGlasses === 0;
  document.getElementById("waterPlus").disabled = waterGlasses === 8;
}

async function loadWater() {
  try {
    const data = await dashboardRequest(`/api/water?day=${encodeURIComponent(localDay())}`);
    waterGlasses = data.glasses;
    updateWater();
  } catch (error) {
    document.getElementById("waterStatus").textContent = error.message;
  }
}

document.getElementById("waterPlus").addEventListener("click", () => saveWater(Math.min(8, waterGlasses + 1)));
document.getElementById("waterMinus").addEventListener("click", () => saveWater(Math.max(0, waterGlasses - 1)));

VP.ready.then(() => {
  const greeting = new Date().getHours() < 12 ? "Good morning" :
    new Date().getHours() < 18 ? "Good afternoon" : "Good evening";
  document.getElementById("hello").textContent = `${greeting}, ${VP.user.name}!`;
  loadRecommendations();
  loadMealPlan();
  loadWater();
}).catch(error => {
  renderState(document.getElementById("recommendations"), "error", error.message, () => VP.ready.then(loadRecommendations));
  renderState(document.getElementById("mealPlanList"), "error", error.message, loadMealPlan);
});

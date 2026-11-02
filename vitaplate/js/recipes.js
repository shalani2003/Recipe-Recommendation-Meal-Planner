// Recipes page. Recipes, favourites and ratings come from the database through /api/recipes
// (see api.js). The pantry match, diet filter, meal plan and shopping list still use the
// browser data they used before (helpers from data.js).
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

let recipes = [];     // everything the server sent
let mode = "all";     // all | now | fav
let loading = true;
let loadError = "";

// data.js helpers (matchPct, dietOk) read `ing`
const prepare = r => Object.assign(r, { ing: r.ingredients });

// ---- talking to the server -------------------------------------------------
// Requests run one after another so quick clicks arrive in order.
let queue = Promise.resolve();
function run(task) {
  const result = queue.then(task);
  queue = result.catch(() => {});
  return result;
}
function flash(text, isError) {
  const el = $("recipes-msg");
  el.textContent = text;
  el.style.color = isError ? "var(--danger)" : "";
  clearTimeout(flash.t);
  if (text) flash.t = setTimeout(() => { el.textContent = ""; }, isError ? 7000 : 3000);
}
// A change shown on screen was refused by the server: say why and show the real data again.
async function recover(error) {
  flash(error.message, true);
  try {
    recipes = (await run(() => VPApi.recipes.list())).map(prepare);
    draw();
  } catch {
    // still offline - keep what is on screen
  }
}

// ---- drawing ---------------------------------------------------------------
const message = (title, text) => `
  <div class="card recipe-empty" style="grid-column: 1 / -1; text-align: center;">
    <img src="assets/food/salad-bowl.jpg" alt="Fresh healthy salad">
    <h3>${esc(title)}</h3>
    <p class="muted">${esc(text)}</p>
  </div>`;

function draw() {
  const grid = $("grid");
  if (loading) { grid.innerHTML = message("Loading recipes…", "One moment."); return; }
  if (loadError) { grid.innerHTML = message("Could not load recipes", loadError); return; }

  const q = $("q").value.trim().toLowerCase();
  const list = recipes
    .filter(r =>
      dietOk(r) &&
      (!q || r.name.toLowerCase().includes(q) || r.ing.some(i => i.toLowerCase().includes(q))) &&
      (mode === "all" || (mode === "fav" && r.is_favorite) || (mode === "now" && matchPct(r) >= 60)))
    .sort((a, b) => matchPct(b) - matchPct(a) || a.id - b.id);

  if (!list.length) {
    grid.innerHTML = message("Nothing here yet", "Try another filter or add items to your pantry.");
    return;
  }
  grid.innerHTML = list.map(card).join("");
}

function card(r) {
  const missing = r.ing.filter(i => !haveIng(i));
  const stars = [1, 2, 3, 4, 5]
    .map(n => `<button class="${n <= r.my_rating ? "on" : ""}" data-r="${r.id}:${n}" aria-label="${n} stars">★</button>`)
    .join("");
  const hasMacros = [r.protein, r.carbs, r.fat].some(v => v !== null);
  const average = r.rating_count
    ? `★ ${r.avg_rating.toFixed(1)} average · ${r.rating_count} rating${r.rating_count > 1 ? "s" : ""}`
    : "No ratings yet";
  return `
    <article class="rcard">
      <div class="recipe-photo-wrap">
        <img class="recipe-photo" src="${esc(r.image || "assets/food/salad-bowl.jpg")}" alt="${esc(r.name)}" loading="lazy">
        <span class="photo-label">🌿 Nourishing pick</span>
        <button class="heart" data-f="${r.id}" aria-pressed="${r.is_favorite}" aria-label="Favourite">${r.is_favorite ? "❤️" : "🤍"}</button>
      </div>
      <div class="recipe-card-body">
        <h3>${esc(r.name)}</h3>
        <div class="meta">
          <span class="chip">${matchPct(r)}% in pantry</span>
          ${r.kcal !== null ? `<span class="chip warn">${r.kcal} kcal</span>` : `<span class="chip is-off">Nutrition not added</span>`}
          ${r.time !== null ? `<span class="chip is-off">${r.time} min</span>` : ""}
        </div>
        ${hasMacros ? `<div class="muted" style="font-size: .85rem">P ${r.protein ?? "–"}g · C ${r.carbs ?? "–"}g · F ${r.fat ?? "–"}g</div>` : ""}
        ${r.diets.length ? `<div class="muted" style="font-size: .78rem">${r.diets.map(esc).join(" · ")}</div>` : ""}
        <div class="muted recipe-ingredients" style="font-size: .8rem">${missing.length ? `Missing: ${esc(missing.join(", "))}` : "Ready to cook"}</div>
        ${r.instructions ? `<details style="font-size: .85rem"><summary>How to make it</summary><p class="muted" style="margin: 6px 0 0; white-space: pre-line">${esc(r.instructions)}</p></details>` : ""}
        <div class="muted" style="font-size: .8rem">${average}</div>
        <div class="stars">${stars}</div>
        <div class="row recipe-actions">
          <button class="btn btn-primary btn-sm" data-plan="${r.id}">Add to plan</button>
          <button class="btn btn-ghost btn-sm" data-shop="${r.id}">Missing to list</button>
        </div>
      </div>
    </article>`;
}

// ---- clicks ----------------------------------------------------------------
const find = id => recipes.find(r => r.id == id);

document.addEventListener("click", e => {
  const b = e.target.closest("button");
  if (!b) return;
  const d = b.dataset;

  if (d.m) {
    mode = d.m;
    document.querySelectorAll(".tab").forEach(t => t.setAttribute("aria-pressed", t.dataset.m === mode));
    draw();
  } else if (d.f) {
    const r = find(d.f);
    if (!r) return;
    r.is_favorite = !r.is_favorite;
    draw();
    const wanted = r.is_favorite;
    run(() => VPApi.recipes.favorite(r.id, wanted)).catch(recover);
  } else if (d.r) {
    const [id, n] = d.r.split(":");
    const r = find(id);
    if (!r) return;
    const stars = r.my_rating == n ? 0 : +n;      // tapping your own rating again clears it
    r.my_rating = stars;
    draw();
    run(() => VPApi.recipes.rate(r.id, stars))
      .then(summary => { r.avg_rating = summary.avg_rating; r.rating_count = summary.rating_count; draw(); })
      .catch(recover);
  } else if (d.plan) {
    const p = _l("vp_plan", {});
    let added = false;
    outer: for (const dy of DAYS) {
      for (const m of MEALS) {
        p[dy] = p[dy] || {};
        if (!p[dy][m]) {
          p[dy][m] = +d.plan;
          added = true;
          break outer;
        }
      }
    }
    _s("vp_plan", p);
    if (added) {
      b.textContent = "Added ✓";
      window.location.href = "planner.html";
    } else {
      b.textContent = "Plan full";
    }
  } else if (d.shop) {
    const r = find(d.shop);
    if (!r) return;
    const s = _l("vp_shop", []);
    r.ing.filter(i => !haveIng(i)).forEach(i => {
      if (!s.some(x => x.name === i)) s.push({ id: Math.random(), name: i, done: false });
    });
    _s("vp_shop", s);
    b.textContent = "Listed ✓";
  }
});

$("q").oninput = draw;

// ---- add a recipe -----------------------------------------------------------
$("add-recipe-form").addEventListener("submit", async e => {
  e.preventDefault();
  const form = e.currentTarget;
  const status = $("add-recipe-status");
  const button = form.querySelector('[type="submit"]');
  button.disabled = true;
  status.textContent = "Saving…";
  try {
    const recipe = prepare(await VPApi.recipes.create(new FormData(form)));
    recipes.push(recipe);
    VPApi.recipes.cache(recipes);        // so the Planner can use it straight away
    mode = "all";
    document.querySelectorAll(".tab").forEach(t => t.setAttribute("aria-pressed", t.dataset.m === mode));
    $("q").value = "";
    form.reset();
    draw();
    status.textContent = `${recipe.name} was added to your recipes.`;
  } catch (error) {
    status.textContent = error.message;
  } finally {
    button.disabled = false;
  }
});

// ---- first load ---------------------------------------------------------------
(async () => {
  const msg = document.createElement("p");
  msg.id = "recipes-msg";
  msg.className = "muted";
  msg.setAttribute("role", "status");
  msg.style.minHeight = "1.4em";
  $("grid").parentNode.insertBefore(msg, $("grid"));
  draw();
  try {
    // favourites/ratings that older versions saved in this browser move to the database once
    await VPApi.recipes.importOldBrowserData().catch(error => { if (error.status === 401) throw error; });
    recipes = (await VPApi.recipes.list()).map(prepare);
  } catch (error) {
    loadError = error.message;
  }
  loading = false;
  draw();
})();

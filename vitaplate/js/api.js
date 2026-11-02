// Talks to the Flask API on the same server (cookie session, JSON bodies).
//
// Pantry and recipe data live in the database. The browser keeps copies in localStorage because
// some pages still read them directly:
//   "vp_pantry"  - Recipes page ("% in pantry"); the Shopping page also writes bought items into it
//   "vp_recipes" - Planner page (names + nutrition of the recipes you can plan)
// This file keeps those copies in step with the server.
const VPApi = (() => {
  class ApiError extends Error {
    constructor(message, status) {
      super(message);
      this.status = status;
    }
  }

  // data: undefined (no body), a FormData (file upload) or anything JSON-able
  async function request(method, url, data) {
    const options = { method, credentials: "same-origin", headers: {} };
    if (data instanceof FormData) {
      options.body = data;
    } else if (data !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(data);
    }
    let res;
    try {
      res = await fetch(url, options);
    } catch {
      throw new ApiError("Can't reach the server. Is it running?", 0);
    }
    if (res.status === 401) {
      // Server session is gone (expired, logged out, database reset): log in again.
      localStorage.removeItem("vp_session");
      location.replace("login.html");
      throw new ApiError("Please log in again.", 401);
    }
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) throw new ApiError(payload.error || "Something went wrong. Please try again.", res.status);
    return payload;
  }

  // ---- pantry -----------------------------------------------------------
  // The pages use {id, name, cat, qty, unit, exp}; the API uses
  // {id, name, category, quantity, unit, expiry_date}.
  const toLocal = i => ({ id: i.id, name: i.name, cat: i.category, qty: i.quantity, unit: i.unit, exp: i.expiry_date || "" });
  const toApi = i => ({ name: i.name, category: i.cat, quantity: i.qty, unit: i.unit, expiry_date: i.exp || null });
  const FIELD_NAMES = { name: "name", cat: "category", qty: "quantity", unit: "unit", exp: "expiry_date" };

  const readCache = () => {
    try {
      const items = JSON.parse(localStorage.getItem("vp_pantry"));
      return Array.isArray(items) ? items : [];
    } catch {
      return [];
    }
  };
  const writeCache = (items, userId) => {
    localStorage.setItem("vp_pantry", JSON.stringify(items));
    if (userId !== undefined) localStorage.setItem("vp_pantry_owner", String(userId));
  };
  // What the page would show, ignoring ids (used to decide if a reload is needed).
  const signature = items => items.map(i => [i.name, i.cat, i.qty, i.unit, i.exp || ""].join("|")).sort().join("\n");

  const pantry = {
    cache: writeCache,

    // Fetch the pantry from the server and refresh the browser copy.
    // Items that other pages saved only in the browser (they have decimal ids,
    // server ids are whole numbers) are uploaded first, so nothing is lost.
    async load() {
      let { items, user_id: userId } = await request("GET", "/api/pantry");
      const owner = localStorage.getItem("vp_pantry_owner");
      const cacheIsMine = owner === null || owner === String(userId);
      const pending = cacheIsMine ? readCache().filter(i => !Number.isInteger(i.id)) : [];
      if (pending.length) {
        await request("POST", "/api/pantry/import", { items: pending.map(toApi) });
        ({ items } = await request("GET", "/api/pantry"));
      }
      const local = items.map(toLocal);
      writeCache(local, userId);
      return local;
    },

    async add(item) {
      const { item: saved, merged } = await request("POST", "/api/pantry", toApi(item));
      return { item: toLocal(saved), merged };
    },

    // changes uses page field names, e.g. {qty: 3} or {name, cat, qty, unit, exp}
    async update(id, changes) {
      const body = {};
      for (const [key, value] of Object.entries(changes)) {
        body[FIELD_NAMES[key]] = key === "exp" ? value || null : value;
      }
      const { item } = await request("PUT", `/api/pantry/${id}`, body);
      return toLocal(item);
    },

    remove: id => request("DELETE", `/api/pantry/${id}`),
    clear: () => request("DELETE", "/api/pantry"),
  };

  // ---- recipes ----------------------------------------------------------
  // The Planner page reads recipes in this older shape (see js/data.js).
  const toPlannerShape = r => ({
    id: r.id, name: r.name, kind: "bowl", time: r.time || 0, kcal: r.kcal || 0,
    p: r.protein || 0, c: r.carbs || 0, f: r.fat || 0, diets: r.diets, ing: r.ingredients,
  });
  const readRecipeCache = () => {
    try {
      const list = JSON.parse(localStorage.getItem("vp_recipes"));
      return Array.isArray(list) ? list : [];
    } catch {
      return [];
    }
  };

  const recipes = {
    // All recipes (with this user's favourites and ratings); refreshes the Planner's copy.
    async list() {
      const { recipes: list } = await request("GET", "/api/recipes");
      recipes.cache(list);
      return list;
    },
    cache: list => localStorage.setItem("vp_recipes", JSON.stringify(list.map(toPlannerShape))),

    // form: a FormData with name, ingredients, instructions, imageFile (+ optional fields)
    async create(form) {
      const { recipe } = await request("POST", "/api/recipes", form);
      return recipe;
    },

    favorite: (id, on) => request(on ? "PUT" : "DELETE", `/api/recipes/${id}/favorite`),
    // stars 1-5 sets the rating, 0 removes it. Resolves with {avg_rating, rating_count, my_rating}.
    rate: (id, stars) =>
      stars ? request("PUT", `/api/recipes/${id}/rating`, { stars }) : request("DELETE", `/api/recipes/${id}/rating`),

    // Favourites and ratings used to be saved in the browser ("vp_fav", "vp_rate").
    // Upload them once, then forget them. Resolves true if anything was moved.
    async importOldBrowserData() {
      const read = (key, fallback) => {
        try {
          return JSON.parse(localStorage.getItem(key)) || fallback;
        } catch {
          return fallback;
        }
      };
      const favs = read("vp_fav", []);
      const ratings = read("vp_rate", {});
      const hasRatings = Object.values(ratings).some(Boolean);
      if (favs.length) await request("POST", "/api/favorites/import", { recipe_ids: favs });
      if (hasRatings) await request("POST", "/api/ratings/import", { ratings });
      localStorage.removeItem("vp_fav");
      localStorage.removeItem("vp_rate");
      return favs.length > 0 || hasRatings;
    },
  };

  // ---- keep the browser copies fresh on pages that only read them ----------
  const PAGE_NEEDS = {
    "recipes.html": ["pantry"],
    "shopping.html": ["pantry"],
    "planner.html": ["recipes"],
  };

  async function refreshOtherPages() {
    const needs = PAGE_NEEDS[document.body.dataset.page] || [];
    if (!needs.length) return;
    const pantryBefore = signature(readCache());
    const recipesBefore = JSON.stringify(readRecipeCache());
    try {
      let changed = false;
      if (needs.includes("pantry")) changed = signature(await pantry.load()) !== pantryBefore;
      if (needs.includes("recipes")) {
        const list = await recipes.list();
        changed = changed || JSON.stringify(list.map(toPlannerShape)) !== recipesBefore;
      }
      const lastReload = +sessionStorage.getItem("vp_sync_reload") || 0;
      if (changed && Date.now() - lastReload > 5000) {
        sessionStorage.setItem("vp_sync_reload", String(Date.now()));
        location.reload();
      }
    } catch {
      // Server unreachable: keep working with the copies the browser already has.
    }
  }
  document.addEventListener("DOMContentLoaded", refreshOtherPages);

  return { request, ApiError, pantry, recipes };
})();

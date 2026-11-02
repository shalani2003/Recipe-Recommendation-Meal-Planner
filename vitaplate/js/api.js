// Talks to the Flask API on the same server (cookie session, JSON bodies).
//
// Pantry data now lives in the database. The browser keeps a copy in
// localStorage ("vp_pantry") because the Recipes page still reads it to work out
// "% in pantry", and the Shopping page still writes bought items into it.
// VPApi.pantry.load() keeps that copy in step with the server.
const VPApi = (() => {
  class ApiError extends Error {
    constructor(message, status) {
      super(message);
      this.status = status;
    }
  }

  async function request(method, url, data) {
    const options = { method, credentials: "same-origin", headers: {} };
    if (data !== undefined) {
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

  // Pages other than Pantry (Recipes, Shopping) only read the browser copy, so
  // refresh it once when they open and reload the page if it was out of date.
  async function refreshOtherPages() {
    if (document.body.dataset.page === "pantry.html") return;
    const before = signature(readCache());
    try {
      const fresh = await pantry.load();
      const lastReload = +sessionStorage.getItem("vp_sync_reload") || 0;
      if (signature(fresh) !== before && Date.now() - lastReload > 5000) {
        sessionStorage.setItem("vp_sync_reload", String(Date.now()));
        location.reload();
      }
    } catch {
      // Server unreachable: keep working with the copy the browser already has.
    }
  }
  document.addEventListener("DOMContentLoaded", refreshOtherPages);

  return { request, ApiError, pantry };
})();

const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

const source = fs.readFileSync(`${__dirname}\\data.js`, "utf8");
const helperStart = source.indexOf("const isRecord=");
const helperEnd = source.indexOf("\nconst _l=", helperStart);
assert(helperStart >= 0 && helperEnd > helperStart, "safe storage helpers exist");

const values = new Map();
const storage = {
  getItem(key) { return values.has(key) ? values.get(key) : null; },
  setItem(key, value) { values.set(key, String(value)); },
  removeItem(key) { values.delete(key); }
};
const context = { localStorage: storage };
vm.runInNewContext(
  `${source.slice(helperStart, helperEnd)}\nthis.testStorage=safeStorage;this.testValidators={isRecord,isStringArray,isPantryStorage,isShoppingStorage,isMealPlanStorage,isRatingsStorage};`,
  context
);

const { testStorage, testValidators } = context;
const fallback = [];
for (const value of ["null", "{}", '"test"', "123", "true", "not-json"]) {
  values.set("vp_pantry", value);
  assert.strictEqual(testStorage.getJSON("vp_pantry", fallback, testValidators.isPantryStorage), fallback);
  assert.strictEqual(values.get("vp_pantry"), value, "invalid stored data is not overwritten");
}
values.set("vp_pantry", "[]");
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(testStorage.getJSON("vp_pantry", fallback, testValidators.isPantryStorage))),
  []
);

const pantry = [{ name: "Rice", qty: 2, unit: "kg", category: "Grains" }];
values.set("vp_pantry", JSON.stringify(pantry));
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(testStorage.getJSON("vp_pantry", fallback, testValidators.isPantryStorage))),
  pantry
);
assert.strictEqual(testStorage.setJSON("vp_pantry", {}, testValidators.isPantryStorage), false);
assert.strictEqual(values.get("vp_pantry"), JSON.stringify(pantry));

assert.strictEqual(testValidators.isShoppingStorage([{ name: "Milk", done: false }]), true);
assert.strictEqual(testValidators.isShoppingStorage([{ done: false }]), false);
assert.strictEqual(testValidators.isMealPlanStorage({ Mon: { Breakfast: "1" } }), true);
assert.strictEqual(testValidators.isMealPlanStorage({ Funday: { Brunch: {} } }), false);
assert.strictEqual(testValidators.isStringArray(["Rice", "Milk"]), true);
assert.strictEqual(testValidators.isStringArray(["Rice", {}]), false);
assert.strictEqual(testValidators.isRatingsStorage({ Rice: 5 }), true);
assert.strictEqual(testValidators.isRatingsStorage({ Rice: "5" }), false);
assert.strictEqual(testStorage.getJSON("vp_nav_pinned", false, value => typeof value === "boolean"), false);
values.set("vp_nav_pinned", "false");
assert.strictEqual(testStorage.getJSON("vp_nav_pinned", true, value => typeof value === "boolean"), false);
assert.strictEqual(testStorage.getJSON("vp_theme", "light", value => value === "light" || value === "dark"), "light");
values.set("vp_theme", "dark");
assert.strictEqual(testStorage.getString("vp_theme", "light", value => value === "light" || value === "dark"), "dark");
assert.strictEqual(testStorage.setString("vp_active_account", "42", value => /^[1-9]\d*$/.test(value)), true);
assert.strictEqual(testStorage.setString("vp_active_account", "[]", value => /^[1-9]\d*$/.test(value)), false);

const brokenStorage = {
  getItem() { throw new Error("storage unavailable"); },
  setItem() { throw new Error("storage unavailable"); },
  removeItem() { throw new Error("storage unavailable"); }
};
const brokenContext = { localStorage: brokenStorage };
vm.runInNewContext(
  `${source.slice(helperStart, helperEnd)}\nthis.testStorage=safeStorage;`,
  brokenContext
);
assert.strictEqual(brokenContext.testStorage.getJSON("key", fallback), fallback);
assert.strictEqual(brokenContext.testStorage.setString("key", "value"), false);
assert.strictEqual(brokenContext.testStorage.remove("key"), false);

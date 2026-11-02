const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

const sourcePath = `${__dirname}\\pantry.js`;
const source = fs.readFileSync(sourcePath, "utf8").replace("catch{return d}", "catch(error){return d}");
const context = {
  Date,
  document: { addEventListener() {} },
  localStorage: { getItem() { return "[]"; }, setItem() {} }
};

vm.runInNewContext(
  `${source}\nthis.daysUntil=daysUntil;this.expiryStatus=expiryStatus;this.localDateString=localDateString;this.card=card;`,
  context
);

function assertExpiry(expiryDate, todayDate, expectedDays, expectedState, expectedLabel) {
  const status = context.expiryStatus(expiryDate, todayDate);
  assert.strictEqual(status.days, expectedDays, `${expiryDate} relative to ${todayDate}`);
  assert.strictEqual(status.state, expectedState, `${expiryDate} state`);
  assert.strictEqual(status.label, expectedLabel, `${expiryDate} label`);
  const html = context.card({ name: "Test ingredient", exp: expiryDate }, todayDate);
  assert(html.includes(`>${expectedLabel}</span>`), `${expiryDate} card label`);
}

assertExpiry("2026-05-14", "2026-05-14", 0, "soon", "Expiring Today");
assertExpiry("2026-05-15", "2026-05-14", 1, "soon", "Expiring Tomorrow");
assertExpiry("2026-05-16", "2026-05-14", 2, "soon", "Expiring Soon");
assertExpiry("2026-05-17", "2026-05-14", 3, "soon", "Expiring Soon");
assertExpiry("2026-05-13", "2026-05-14", -1, "exp", "Expired");
assertExpiry("2026-05-18", "2026-05-14", 4, "ok", "Fresh");

assertExpiry("2026-05-01", "2026-04-30", 1, "soon", "Expiring Tomorrow");
assertExpiry("2026-04-30", "2026-05-01", -1, "exp", "Expired");
assertExpiry("2027-01-01", "2026-12-31", 1, "soon", "Expiring Tomorrow");
assertExpiry("2026-12-31", "2027-01-01", -1, "exp", "Expired");
assertExpiry("2024-02-29", "2024-02-29", 0, "soon", "Expiring Today");
assertExpiry("2024-02-29", "2024-02-28", 1, "soon", "Expiring Tomorrow");
assertExpiry("2024-02-28", "2024-02-29", -1, "exp", "Expired");
assertExpiry("2024-03-01", "2024-02-29", 1, "soon", "Expiring Tomorrow");
assertExpiry("2025-03-01", "2025-02-28", 1, "soon", "Expiring Tomorrow");

assert.strictEqual(context.daysUntil("2026-02-29", "2026-02-28"), null);
assert.strictEqual(context.daysUntil("2024-02-30", "2024-02-29"), null);
assert.strictEqual(context.expiryStatus("", "2026-05-14").label, "No expiry date");
assert.strictEqual(context.localDateString(new Date(2026, 4, 14, 23, 30)), "2026-05-14");
assert.strictEqual(context.localDateString({
  getFullYear() { return 2026; },
  getMonth() { return 11; },
  getDate() { return 31; }
}), "2026-12-31");

console.log("PASS pantry expiry labels and local-calendar boundary dates");

const stored = new Map([["vp_pantry", "[]"]]);
const nodes = {};
let onReady;
const document = {
  addEventListener(event, callback) {
    if (event === "DOMContentLoaded") onReady = callback;
  },
  getElementById(id) {
    if (!nodes[id]) nodes[id] = { value: "", textContent: "", innerHTML: "" };
    return nodes[id];
  }
};
const mergeContext = {
  Date,
  document,
  window: { addEventListener() {} },
  localStorage: {
    getItem(key) { return stored.has(key) ? stored.get(key) : null; },
    setItem(key, value) { stored.set(key, String(value)); }
  },
  confirm() { return true; }
};
vm.runInNewContext(
  `${source}\nthis.addPantryItem=add;this.getPantryItems=()=>items;this.validatePantryAmount=validateAmount;`,
  mergeContext
);
onReady();

const today = context.localDateString(new Date());
const tomorrowDate = new Date();
tomorrowDate.setDate(tomorrowDate.getDate() + 1);
const tomorrow = context.localDateString(tomorrowDate);
const yesterdayDate = new Date();
yesterdayDate.setDate(yesterdayDate.getDate() - 1);
const yesterday = context.localDateString(yesterdayDate);

mergeContext.addPantryItem("  Apples ", "Fruits", 2, "pcs", today);
mergeContext.addPantryItem("apples", "Fruits", 3, "pcs", today);
assert.strictEqual(mergeContext.getPantryItems().length, 1);
assert.strictEqual(mergeContext.getPantryItems()[0].qty, 5);
assert.strictEqual(mergeContext.getPantryItems()[0].unit, "pcs");
assert.strictEqual(nodes.sItems.textContent, 1);
assert.strictEqual(nodes.sSoon.textContent, 1);
assert(nodes.groups.innerHTML.includes("5 pcs"));

mergeContext.addPantryItem("Apples", "Fruits", 4, "pcs", tomorrow);
mergeContext.addPantryItem("Apples", "Fruits", 1, "kg", today);
mergeContext.addPantryItem("Apples", "Other", 1, "pcs", today);
mergeContext.addPantryItem("Apples", "Fruits", 1, "pcs", yesterday);
const mergedItems = mergeContext.getPantryItems();
assert.strictEqual(mergedItems.length, 5);
assert.strictEqual(mergedItems[0].qty, 5);
assert.deepStrictEqual(Array.from(mergedItems, item => item.exp), [today, tomorrow, today, today, yesterday]);
assert.deepStrictEqual(Array.from(mergedItems, item => item.unit), ["pcs", "pcs", "kg", "pcs", "pcs"]);
assert.strictEqual(nodes.sItems.textContent, 5);
assert.strictEqual(nodes.sExpired.textContent, 1);
assert.strictEqual(nodes.sSoon.textContent, 4);

console.log("PASS pantry merge identity, quantity/unit preservation, separate expiry dates, and immediate tile updates");

function assertAmount(rawAmount, unit, expectedAmount, expectedUnit) {
  const result = mergeContext.validatePantryAmount(rawAmount, unit);
  assert.ifError(result.error);
  assert.strictEqual(result.amount, expectedAmount);
  assert.strictEqual(result.unit, expectedUnit);
}
function assertInvalidAmount(rawAmount, unit) {
  assert(mergeContext.validatePantryAmount(rawAmount, unit).error, `${rawAmount} ${unit} should be rejected`);
}

assertAmount("0.01", "kg", 0.01, "kg");
assertAmount("1.25", "g", 1.25, "g");
assertAmount("99999", "L", 99999, "l");
assertAmount("99999", "pcs", 99999, "pcs");
assertAmount("0.5", "ml", 0.5, "ml");
assertAmount("2.75", "cups", 2.75, "cups");
assertAmount("1", "pcs", 1, "pcs");
assertInvalidAmount("", "kg");
assertInvalidAmount("0", "kg");
assertInvalidAmount("-0.5", "kg");
assertInvalidAmount("not a number", "kg");
assertInvalidAmount("Infinity", "kg");
assertInvalidAmount("100000", "kg");
assertInvalidAmount("1.001", "kg");
assertInvalidAmount("1.5", "pcs");
assertInvalidAmount("1", "gallon");

const formStorage = new Map([["vp_pantry", "[]"]]);
const formNodes = {};
let formReady;
const formDocument = {
  addEventListener(event, callback) {
    if (event === "DOMContentLoaded") formReady = callback;
  },
  getElementById(id) {
    if (!formNodes[id]) {
      formNodes[id] = {
        value: "",
        textContent: "",
        innerHTML: "",
        dataset: {},
        setCustomValidity(message) { this.validationMessage = message; },
        reset() { this.wasReset = true; },
        focus() {},
        addEventListener() {}
      };
    }
    return formNodes[id];
  }
};
const formContext = {
  Date,
  document: formDocument,
  window: { addEventListener() {} },
  localStorage: {
    getItem(key) { return formStorage.has(key) ? formStorage.get(key) : null; },
    setItem(key, value) { formStorage.set(key, String(value)); }
  },
  confirm() { return true; }
};
formNodes.unit = { value: "pcs" };
["qty", "name", "cat", "exp", "addForm"].forEach(id => formDocument.getElementById(id));
vm.runInNewContext(`${source}\nthis.addPantryItem=add;`, formContext);
formReady();
assert.strictEqual(formNodes.qty.min, "1");
assert.strictEqual(formNodes.qty.step, "1");
formNodes.unit.value = "kg";
formNodes.unit.onchange();
assert.strictEqual(formNodes.qty.min, "0.01");
assert.strictEqual(formNodes.qty.step, "0.01");
formNodes.name.value = "Flour";
formNodes.cat.value = "Grains";
formNodes.qty.value = "0";
formNodes.unit.value = "kg";
formNodes.addForm.onsubmit({ preventDefault() {}, target: formNodes.addForm });
assert(/greater than zero/.test(formNodes.quantityError.textContent));
assert.strictEqual(formNodes.addForm.wasReset, undefined);
assert.strictEqual(JSON.parse(formStorage.get("vp_pantry")).length, 0);

formNodes.qty.value = "1.25";
formNodes.addForm.onsubmit({ preventDefault() {}, target: formNodes.addForm });
assert.strictEqual(formNodes.addForm.wasReset, true);
assert.deepStrictEqual(JSON.parse(formStorage.get("vp_pantry")).map(item => [item.qty, item.unit]), [[1.25, "kg"]]);
formContext.addPantryItem("Flour", "Grains", 100000, "kg", "");
assert.strictEqual(JSON.parse(formStorage.get("vp_pantry"))[0].qty, 1.25);
assert(/cannot exceed/.test(formNodes.quantityError.textContent));
formContext.addPantryItem("Flour", "Grains", 1, "g", "");
formContext.addPantryItem("Water", "Other", 1, "L", "");
formContext.addPantryItem("Water", "Other", 250, "ml", "");
formContext.addPantryItem("Minimum amount", "Other", 0.01, "g", "");
const savedAmounts = JSON.parse(formStorage.get("vp_pantry"));
assert.deepStrictEqual(savedAmounts.map(item => [item.name, item.qty, item.unit]), [
  ["Flour", 1.25, "kg"],
  ["Flour", 1, "g"],
  ["Water", 1, "l"],
  ["Water", 250, "ml"],
  ["Minimum amount", 0.01, "g"]
]);
assert.strictEqual(formNodes.sItems.textContent, 5);
assert(/1\.25 kg/.test(formNodes.groups.innerHTML));
assert(/250 ml/.test(formNodes.groups.innerHTML));
formContext.addPantryItem("Bulk rice", "Grains", 99999, "kg", "");
const bulk = JSON.parse(formStorage.get("vp_pantry")).find(item => item.name === "Bulk rice");
formNodes.groups.onclick({ target: { dataset: { p: String(bulk.id) } } });
assert.strictEqual(JSON.parse(formStorage.get("vp_pantry")).find(item => item.name === "Bulk rice").qty, 99999);
formContext.addPantryItem("Bulk rice", "Grains", 1, "kg", "");
assert.strictEqual(JSON.parse(formStorage.get("vp_pantry")).find(item => item.name === "Bulk rice").qty, 99999);
assert.strictEqual(formNodes.sItems.textContent, 6);
assert(/cannot exceed/.test(formNodes.quantityError.textContent));
console.log("PASS quantity bounds, decimal precision, invalid values, form feedback, unit storage, no implicit conversion, and merge limits");

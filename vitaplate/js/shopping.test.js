const assert = require("assert");
const fs = require("fs");
const vm = require("vm");

const storage = new Map();
const pantryCategoryNames = ["Vegetables", "Fruits", "Grains", "Protein", "Dairy", "Spices & sauces", "Other"];
const context = {
  Date,
  Math,
  R: [
    { id: 1, ing: ["Chicken", "Rice"] },
    { id: 2, ing: ["Rice", "Onion"] },
    { id: 3, ing: ["Not selected"] }
  ],
  normalizeIngredient(value) {
    return String(value || "").trim().toLowerCase()
      .replace(/\s+/g, " ")
      .replace(/\bcarrots\b/g, "carrot")
      .replace(/\btomatoes\b/g, "tomato")
      .replace(/\bonions\b/g, "onion");
  },
  localStorage: {
    getItem(key) { return storage.has(key) ? storage.get(key) : null; },
    setItem(key, value) { storage.set(key, String(value)); }
  },
  window: {
    VP: {
      pantryCategories: pantryCategoryNames,
      normalizePantryCategory(value) {
        if (typeof value !== "string") return "";
        return pantryCategoryNames.find(category => category.toLowerCase() === value.trim().toLowerCase()) || "";
      }
    }
  }
};

const shoppingPath = `${__dirname}\\shopping.js`;
const shoppingSource = fs.readFileSync(shoppingPath, "utf8");
vm.runInNewContext(shoppingSource, context);

const customRecipes = [
  {
    id: "custom:201",
    ingredients: [
      { name: "Carrots", quantity: 250, unit: "g" },
      { name: "Rice", quantity: 1, unit: "cup" },
      "1/2 kg Tomatoes"
    ]
  },
  {
    id: "custom:202",
    ing: [
      { ingredient: "carrot", amount: 0.5, unit: "kg" },
      "1/2 cup rice",
      { name: "Onions", quantity: 2, unit: "pcs" }
    ]
  },
  {
    id: "custom:203",
    ingredients: [{ name: "Unused ingredient", quantity: 9, unit: "kg" }]
  }
];
const quantityRecipes = [
  {
    id: "quantity:301",
    ingredients: [
      { name: "Rice", quantity: 1, unit: "kg" },
      { name: "Milk", quantity: 500, unit: "ml" },
      { name: "Flour", quantity: 2, unit: "cups" },
      { name: "Salt", quantity: 100, unit: "g" }
    ]
  }
];
const plan = {
  Mon: { Breakfast: "custom:201", Lunch: "custom:202", Dinner: 0 },
  Tue: { Breakfast: "custom:201" }
};

const generated = context.window.VPShopping.buildFromMealPlan(plan, customRecipes);
const quantities = generated.reduce((result, item) => {
  result[item.name.toLowerCase()] = [item.quantity, item.unit];
  return result;
}, {});

assert.deepStrictEqual(quantities.carrots, [1000, "g"]);
assert.deepStrictEqual(quantities.rice, [2.5, "cups"]);
assert.deepStrictEqual(quantities.tomatoes, [1, "kg"]);
assert.deepStrictEqual(quantities.onions, [2, "pcs"]);
assert.strictEqual(generated.length, 4);
assert(!generated.some(item => item.name === "Unused ingredient"));

const builtInGenerated = context.window.VPShopping.buildFromMealPlan(
  { Mon: { Lunch: 1 }, Tue: { Dinner: 2 } },
  customRecipes
);
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(builtInGenerated.map(item => [item.name, item.quantity, item.unit]))),
  [["Chicken", 1, "item"], ["Rice", 2, "item"], ["Onion", 1, "item"]]
);
assert(!builtInGenerated.some(item => item.name === "Not selected"));

const updated = context.window.VPShopping.buildFromMealPlan(
  { Wed: { Lunch: "custom:202" } },
  customRecipes,
  generated
);
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(updated.map(item => [item.name, item.quantity, item.unit]))),
  [["Carrots", 0.5, "kg"], ["Rice", 0.5, "cups"], ["Onions", 2, "pcs"]]
);
assert.strictEqual(updated[0].id, generated[0].id);
assert.strictEqual(context.window.VPShopping.formatQuantity(updated[1]), "0.5 cups");

const duplicateRecipes = [
  {
    id: "duplicates:401",
    ingredients: [
      { name: "Rice", quantity: 1, unit: "cup" },
      { name: "  RICE  ", quantity: 240, unit: "ml" },
      { name: "rice", quantity: 250, unit: "g" },
      { name: "Rice", quantity: 1, unit: "pcs" }
    ]
  },
  {
    id: "duplicates:402",
    ing: [{ name: " rice ", quantity: 0.5, unit: "cups" }]
  }
];
const duplicatePlanItems = context.window.VPShopping.buildFromMealPlan(
  { Mon: { Lunch: "duplicates:401", Dinner: "duplicates:402" } },
  duplicateRecipes
);
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(duplicatePlanItems.map(item => [item.name, item.quantity, item.unit]))),
  [["Rice", 2.5, "cups"], ["rice", 250, "g"], ["Rice", 1, "pcs"]]
);

const pantryPlan = { Mon: { Lunch: "quantity:301" } };
const fullPantry = context.window.VPShopping.buildFromMealPlan(
  pantryPlan,
  quantityRecipes,
  [],
  [
    { name: "RICE", qty: 1000, unit: "g" },
    { name: "milk", qty: 0.5, unit: "l" },
    { name: "Flour", qty: 2, unit: "cups" },
    { name: "Pepper", qty: 100, unit: "g" },
    { name: "Rice noodles", qty: 5, unit: "kg" }
  ]
);
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(fullPantry.map(item => [item.name, item.quantity, item.unit]))),
  [["Salt", 100, "g"]]
);

const partialPantry = context.window.VPShopping.buildFromMealPlan(
  pantryPlan,
  quantityRecipes,
  [],
  [
    { name: "rice", qty: 500, unit: "g" },
    { name: "Milk", qty: 250, unit: "ml" },
    { name: "Flour", qty: 1, unit: "cups" },
    { name: "Salt", qty: 1, unit: "ml" }
  ]
);
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(partialPantry.map(item => [item.name, item.quantity, item.unit]))),
  [["Rice", 0.5, "kg"], ["Milk", 250, "ml"], ["Flour", 1, "cups"], ["Salt", 100, "g"]]
);

const noPantry = context.window.VPShopping.buildFromMealPlan(pantryPlan, quantityRecipes, [], []);
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(noPantry.map(item => [item.name, item.quantity, item.unit]))),
  [["Rice", 1, "kg"], ["Milk", 500, "ml"], ["Flour", 2, "cups"], ["Salt", 100, "g"]]
);

const createManualItem = context.window.VPShopping.createManualShoppingItem;
const resolveImage = context.window.VPShopping.resolveShoppingImage;
const imageMap = {rice: "/assets/food/rice.jpg"};
assert.strictEqual(resolveImage({name: "Rice"}, imageMap, "/fallback.svg"), "/assets/food/rice.jpg");
assert.strictEqual(resolveImage({name: "Rice", image: "/custom.jpg"}, imageMap, "/fallback.svg"), "/custom.jpg");
assert.strictEqual(resolveImage({name: "Rice", recipeImage: "/recipe.jpg"}, imageMap, "/fallback.svg"), "/recipe.jpg");
assert.strictEqual(resolveImage({name: "Unknown"}, imageMap, "/fallback.svg"), "/fallback.svg");
const manualItem = createManualItem("  Oats  ", "1.25", "kg");
assert.ifError(manualItem.error);
assert.deepStrictEqual(
  JSON.parse(JSON.stringify([
    manualItem.item.name,
    manualItem.item.quantity,
    manualItem.item.unit,
    manualItem.item.done,
    manualItem.item.source
  ])),
  ["Oats", 1.25, "kg", false, "manual"]
);
assert.strictEqual(createManualItem("  ", "1", "pcs").error, "Enter an item name.");
assert.strictEqual(createManualItem("Oats", "", "kg").error, "Enter a quantity greater than zero.");
assert.strictEqual(createManualItem("Oats", "0", "kg").error, "Enter a quantity greater than zero.");
assert.strictEqual(createManualItem("Oats", "-2", "kg").error, "Enter a quantity greater than zero.");
assert.strictEqual(createManualItem("Oats", "1.5", "pcs").error, "Use a whole number for pieces (pcs).");
assert.strictEqual(createManualItem("Oats", "1.234", "kg").error, "Use no more than two decimal places.");
assert.strictEqual(createManualItem("Oats", "100000", "kg").error, "Quantity cannot exceed 99999.");
assert.strictEqual(createManualItem("Oats", "1", "gallon").error, "Select a supported unit.");

const existingList = [{ id: "planned", name: "Rice", quantity: 1, unit: "kg", source: "meal-plan" }];
const addedManual = context.window.VPShopping.addManualShoppingItem(existingList, "Tea", "2", "cups");
assert.ifError(addedManual.error);
assert.strictEqual(existingList.length, 2);
assert.strictEqual(existingList[0].source, "meal-plan");
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(existingList[1])),
  JSON.parse(JSON.stringify(addedManual.item))
);
const invalidList = existingList.slice();
const rejectedManual = context.window.VPShopping.addManualShoppingItem(invalidList, "", "2", "cups");
assert.strictEqual(rejectedManual.error, "Enter an item name.");
assert.strictEqual(invalidList.length, existingList.length);

const manualDuplicates = [];
const firstTea = context.window.VPShopping.addManualShoppingItem(manualDuplicates, "  Green   Tea ", "1", "kg");
assert.ifError(firstTea.error);
assert.strictEqual(firstTea.merged, false);
const secondTea = context.window.VPShopping.addManualShoppingItem(manualDuplicates, "green tea", "500", "g");
assert.ifError(secondTea.error);
assert.strictEqual(secondTea.merged, true);
assert.strictEqual(manualDuplicates.length, 1);
assert.strictEqual(manualDuplicates[0].quantity, 1.5);
assert.strictEqual(manualDuplicates[0].unit, "kg");
context.window.VPShopping.addManualShoppingItem(manualDuplicates, "Green tea", "2", "pcs");
assert.strictEqual(manualDuplicates.length, 2);
context.window.VPShopping.addManualShoppingItem(manualDuplicates, "Tea leaves", "1", "kg");
assert.strictEqual(manualDuplicates.length, 3);

const maximumQuantityItem = [{ id: "maximum", name: "Rice", quantity: 99999, unit: "kg", source: "manual" }];
const excessiveDuplicate = context.window.VPShopping.addManualShoppingItem(maximumQuantityItem, "rice", "1", "kg");
assert.strictEqual(excessiveDuplicate.error, "Combined quantity cannot exceed 99999.");
assert.strictEqual(maximumQuantityItem.length, 1);
assert.strictEqual(maximumQuantityItem[0].quantity, 99999);

const planAndManual = [{ id: "rice-plan", name: "Rice", quantity: 1, unit: "kg", done: false, source: "meal-plan" }];
const extraRice = context.window.VPShopping.addManualShoppingItem(planAndManual, " rice ", "0.5", "kg");
assert.ifError(extraRice.error);
assert.strictEqual(planAndManual.length, 1);
assert.strictEqual(planAndManual[0].quantity, 1.5);
const refreshedRice = context.window.VPShopping.buildFromMealPlan(
  { Mon: { Lunch: "quantity:301" } },
  quantityRecipes,
  planAndManual,
  [{ name: "Rice", qty: 500, unit: "g" }]
);
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(refreshedRice.map(item => [item.name, item.quantity, item.unit]))),
  [["Rice", 1, "kg"], ["Milk", 500, "ml"], ["Flour", 2, "cups"], ["Salt", 100, "g"]]
);
const removedPlanRice = context.window.VPShopping.buildFromMealPlan({}, quantityRecipes, refreshedRice, []);
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(removedPlanRice.map(item => [item.name, item.quantity, item.unit, item.source]))),
  [["Rice", 0.5, "kg", "manual"]]
);

const legacyDuplicates = context.window.VPShopping.deduplicateShoppingItems([
  { id: "legacy-1", name: "Rice  ", quantity: 1, unit: "kg", source: "manual", done: false },
  { id: "legacy-2", name: " rice ", quantity: 500, unit: "g", source: "manual", done: false },
  { id: "legacy-3", name: "RICE", quantity: 2, unit: "pcs", source: "manual", done: false }
]);
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(legacyDuplicates.map(item => [item.name, item.quantity, item.unit]))),
  [["Rice  ", 1.5, "kg"], ["RICE", 2, "pcs"]]
);

const boughtItem = { id: "bought", name: "Rice", quantity: 1, unit: "kg", done: false, source: "meal-plan" };
const unrelatedItem = { id: "keep", name: "Beans", quantity: 2, unit: "pcs", done: false, source: "manual" };
const interactiveItems = [boughtItem, unrelatedItem];
assert.strictEqual(context.window.VPShopping.toggleBoughtItem(interactiveItems, "bought"), boughtItem);
assert.strictEqual(boughtItem.done, true);
assert.strictEqual(context.window.VPShopping.toggleBoughtItem(interactiveItems, "bought"), boughtItem);
assert.strictEqual(boughtItem.done, false);
assert.strictEqual(context.window.VPShopping.toggleBoughtItem(interactiveItems, "missing"), null);

const generatedBoughtState = context.window.VPShopping.buildFromMealPlan(
  { Mon: { Lunch: 1 } },
  []
);
const generatedRice = generatedBoughtState.find(item => item.name === "Rice");
context.window.VPShopping.toggleBoughtItem(generatedBoughtState, generatedRice.id);
const refreshedBoughtState = context.window.VPShopping.buildFromMealPlan(
  { Mon: { Lunch: 1 } },
  [],
  generatedBoughtState
);
assert.strictEqual(refreshedBoughtState.find(item => item.name === "Rice").done, true);

assert.strictEqual(context.window.VPShopping.removeShoppingItem(interactiveItems, "missing"), null);
const removedItem = context.window.VPShopping.removeShoppingItem(interactiveItems, "bought");
assert.strictEqual(removedItem, boughtItem);
assert.deepStrictEqual(interactiveItems, [unrelatedItem]);

function testClearConfirmation() {
  const confirmAndClear = context.window.VPShopping.confirmAndClearShoppingList;
  const preservedItems = [{ id: "keep", name: "Rice" }];
  let clearRequests = 0;
  return confirmAndClear(
    () => false,
    () => { clearRequests += 1; preservedItems.splice(0); return Promise.resolve(); }
  ).then(cancelled => {
    assert.strictEqual(cancelled, false);
    assert.strictEqual(clearRequests, 0);
    assert.strictEqual(preservedItems.length, 1);
    return confirmAndClear(
    () => true,
    () => { clearRequests += 1; preservedItems.splice(0); return Promise.resolve(); }
    );
  }).then(confirmed => {
    assert.strictEqual(confirmed, true);
    assert.strictEqual(clearRequests, 1);
    assert.strictEqual(preservedItems.length, 0);
  });
}

const excludedPlanItems = context.window.VPShopping.buildFromMealPlan(
  { Mon: { Lunch: "quantity:301" } },
  quantityRecipes,
  [],
  [],
  [context.window.VPShopping.ingredientKey("Rice", "kg")]
);
assert(!excludedPlanItems.some(item => item.name === "Rice"));
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(excludedPlanItems.map(item => item.name))),
  ["Milk", "Flour", "Salt"]
);

const moveBought = context.window.VPShopping.moveBoughtItemsToPantry;
const purchasedItems = [
  { id: "purchased-rice", name: "Rice", quantity: 500, unit: "g", done: true },
  { id: "not-bought-tea", name: "Tea", quantity: 2, unit: "cups", done: false }
];
const pantryBeforePurchase = [
  { id: "existing-rice", name: "Rice", cat: "Grains", qty: 1000, unit: "g", exp: "2027-01-15" }
];
const pantryTransfer = moveBought(purchasedItems, pantryBeforePurchase, "2027-01-15");
assert.ifError(pantryTransfer.error);
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(pantryTransfer.pantryItems.map(item => [
    item.name, item.cat, item.qty, item.unit, item.exp
  ]))),
  [["Rice", "Grains", 1500, "g", "2027-01-15"]]
);
assert.deepStrictEqual(JSON.parse(JSON.stringify(pantryTransfer.movedIds)), ["purchased-rice"]);
const repeatedTransfer = moveBought(purchasedItems, pantryTransfer.pantryItems, "2027-01-15");
assert.ifError(repeatedTransfer.error);
assert.strictEqual(repeatedTransfer.pantryItems[0].qty, 1500);
assert.deepStrictEqual(JSON.parse(JSON.stringify(repeatedTransfer.movedIds)), ["purchased-rice"]);

const newPantryTransfer = moveBought(
  [{ id: "purchased-coconut", name: "Coconut", quantity: 2, unit: "pcs", done: true }],
  [],
  ""
);
assert.ifError(newPantryTransfer.error);
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(newPantryTransfer.pantryItems.map(item => [
    item.name, item.cat, item.qty, item.unit, item.exp
  ]))),
  [["Coconut", "Fruits", 2, "pcs", ""]]
);

const categorizedTransfers = moveBought([
  { id: "valid-category", name: "Eggs", category: " dairy ", quantity: 1, unit: "pcs", done: true, expiry_date: "2027-02-01" },
  { id: "category-alias", name: "Tea", cat: "Spices & sauces", quantity: 1, unit: "cups", done: true },
  { id: "invalid-category", name: "Spinach", category: "Not a Pantry category", quantity: 2, unit: "pcs", done: true },
  { id: "missing-category", name: "Rice", quantity: 1, unit: "kg", done: true }
], [], "2027-03-01");
assert.ifError(categorizedTransfers.error);
assert(categorizedTransfers.pantryItems.every(item => pantryCategoryNames.includes(item.cat)));
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(categorizedTransfers.pantryItems.map(item => [item.name, item.cat, item.exp]))),
  [["Eggs", "Dairy", "2027-02-01"], ["Tea", "Spices & sauces", "2027-03-01"], ["Spinach", "Vegetables", "2027-03-01"], ["Rice", "Grains", "2027-03-01"]]
);

const mergeDifferentExpiry = moveBought(
  [{ id: "second-rice-purchase", name: "Rice", category: "Other", quantity: 500, unit: "g", done: true, expiry_date: "2027-01-01" }],
  [{ id: "existing-rice", name: "Rice", cat: "Grains", qty: 1000, unit: "g", exp: "2027-02-01" }],
  "2027-03-01"
);
assert.ifError(mergeDifferentExpiry.error);
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(mergeDifferentExpiry.pantryItems.map(item => [item.name, item.cat, item.qty, item.exp]))),
  [["Rice", "Grains", 1500, "2027-01-01"]]
);

const convertedPantryTransfer = moveBought(
  [{ id: "purchased-spice", name: "Cinnamon", quantity: 2, unit: "tsp", done: true }],
  [],
  ""
);
assert.ifError(convertedPantryTransfer.error);
assert.deepStrictEqual(
  JSON.parse(JSON.stringify(convertedPantryTransfer.pantryItems.map(item => [item.qty, item.unit]))),
  [[10, "ml"]]
);

const unsupportedTransfer = moveBought(
  [{ id: "purchased-spice", name: "Cinnamon", quantity: 1, unit: "clove", done: true }],
  [],
  ""
);
assert(unsupportedTransfer.error);
assert.strictEqual(unsupportedTransfer.pantryItems, undefined);
assert.strictEqual(unsupportedTransfer.movedIds, undefined);
const partialFailure = moveBought([
  { id: "valid-first", name: "Rice", quantity: 1, unit: "kg", done: true },
  { id: "invalid-second", name: "Cinnamon", quantity: 1, unit: "clove", done: true }
], []);
assert(partialFailure.error);
assert.strictEqual(partialFailure.pantryItems, undefined);
assert.strictEqual(partialFailure.movedIds, undefined);
assert(moveBought([{ id: "bought-exp", name: "Rice", quantity: 1, unit: "kg", done: true }], [], "2026-02-30").error);
const noSelectedItems = [{ id: "no-bought", name: "Rice", quantity: 1, unit: "kg", done: false }];
const noSelectedTransfer = moveBought(noSelectedItems, []);
assert.strictEqual(noSelectedTransfer.error, "Mark items as bought before moving them to the Pantry.");
assert.strictEqual(noSelectedItems.length, 1);
assert.strictEqual(noSelectedTransfer.pantryItems, undefined);

testClearConfirmation().then(() => {
  console.log("PASS shopping generation, transfer validation, and Clear confirmation behavior");
}).catch(error => {
  console.error(error);
  process.exitCode = 1;
});

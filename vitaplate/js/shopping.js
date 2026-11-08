(function (global) {
	const unitDefinitions = {
		g: { dimension: "weight", factor: 1 },
		gram: { dimension: "weight", factor: 1 },
		grams: { dimension: "weight", factor: 1 },
		kg: { dimension: "weight", factor: 1000 },
		kilogram: { dimension: "weight", factor: 1000 },
		kilograms: { dimension: "weight", factor: 1000 },
		oz: { dimension: "weight", factor: 28.349523125 },
		ounce: { dimension: "weight", factor: 28.349523125 },
		ounces: { dimension: "weight", factor: 28.349523125 },
		lb: { dimension: "weight", factor: 453.59237 },
		lbs: { dimension: "weight", factor: 453.59237 },
		pound: { dimension: "weight", factor: 453.59237 },
		pounds: { dimension: "weight", factor: 453.59237 },
		ml: { dimension: "volume", factor: 1 },
		milliliter: { dimension: "volume", factor: 1 },
		milliliters: { dimension: "volume", factor: 1 },
		l: { dimension: "volume", factor: 1000 },
		liter: { dimension: "volume", factor: 1000 },
		liters: { dimension: "volume", factor: 1000 },
		item: { dimension: "count", factor: 1 },
		pcs: { dimension: "count", factor: 1 },
		pc: { dimension: "count", factor: 1 },
		piece: { dimension: "count", factor: 1 },
		pieces: { dimension: "count", factor: 1 },
		tsp: { dimension: "volume", factor: 5 },
		teaspoon: { dimension: "volume", factor: 5 },
		teaspoons: { dimension: "volume", factor: 5 },
		tbsp: { dimension: "volume", factor: 15 },
		tablespoon: { dimension: "volume", factor: 15 },
		tablespoons: { dimension: "volume", factor: 15 },
		cup: { dimension: "volume", factor: 240 },
		cups: { dimension: "volume", factor: 240 }
	};
	const ingredientUnitPattern = "kilograms?|kg|grams?|g|milliliters?|ml|liters?|l|ounces?|oz|pounds?|lbs?|teaspoons?|tsp|tablespoons?|tbsp|cups?|pieces?|piece|pcs|pc|items?|cloves?|bunches?|cans?|tins?";
	const amountPattern = "(?:\\d+\\s+\\d+\\/\\d+|\\d+\\/\\d+|\\d+(?:\\.\\d+)?)";

	function parseAmount(value) {
		const text = String(value).trim();
		const mixed = /^(\d+)\s+(\d+)\/(\d+)$/.exec(text);
		if (mixed) return Number(mixed[1]) + Number(mixed[2]) / Number(mixed[3]);
		const fraction = /^(\d+)\/(\d+)$/.exec(text);
		if (fraction) return Number(fraction[1]) / Number(fraction[2]);
		return Number(text);
	}

	function normalizeUnit(value) {
		const unit = String(value || "").trim().toLowerCase();
		const aliases = {
			gram: "g", grams: "g", kilogram: "kg", kilograms: "kg",
			milliliter: "ml", milliliters: "ml", liter: "l", liters: "l",
			ounce: "oz", ounces: "oz", pound: "lb", pounds: "lb", lbs: "lb",
			teaspoon: "tsp", teaspoons: "tsp", tablespoon: "tbsp", tablespoons: "tbsp",
			cup: "cups", piece: "pcs", pieces: "pcs", pc: "pcs", item: "item", items: "item",
			cloves: "clove", bunches: "bunch", cans: "can", tins: "tin"
		};
		return aliases[unit] || unit || "item";
	}

	function parseIngredient(value) {
		if (typeof value === "string" || typeof value === "number") {
			const text = String(value).trim();
			const match = new RegExp("^(" + amountPattern + ")\\s*(?:" + "(" + ingredientUnitPattern + ")\\b\\s*)?(?:of\\s+)?(.+)$", "i").exec(text);
			const quantity = match ? parseAmount(match[1]) : 1;
			const unit = match && match[2] ? normalizeUnit(match[2]) : "item";
			const name = match ? match[3].trim() : text;
			return validateIngredient(name, quantity, unit);
		}

		if (!value || typeof value !== "object") {
			throw new Error("A recipe contains an ingredient in an unsupported format.");
		}

		const name = value.name || value.ingredient || value.item;
		const rawAmount = value.quantity !== undefined && value.quantity !== null
			? value.quantity
			: value.qty !== undefined && value.qty !== null
				? value.qty
				: value.amount !== undefined && value.amount !== null ? value.amount : 1;
		const objectUnit = value.unit || value.uom || "";
		const amountText = typeof rawAmount === "object" && rawAmount !== null
			? rawAmount.value
			: rawAmount;
		const unit = objectUnit || (typeof rawAmount === "object" && rawAmount !== null ? rawAmount.unit : "");
		const amountWithUnit = String(amountText) + (unit ? " " + unit : "") + " " + String(name || "");
		const match = new RegExp("^(" + amountPattern + ")\\s*(?:" + "(" + ingredientUnitPattern + ")\\b\\s*)?(?:of\\s+)?(.+)$", "i").exec(amountWithUnit.trim());
		if (!match) return validateIngredient(name, Number(amountText), normalizeUnit(unit));
		return validateIngredient(match[3].trim(), parseAmount(match[1]), normalizeUnit(match[2] || unit));
	}

	function validateIngredient(name, quantity, unit) {
		if (!String(name || "").trim()) {
			throw new Error("A recipe contains an ingredient without a name.");
		}
		if (!Number.isFinite(quantity) || quantity <= 0) {
			throw new Error("Recipe ingredient quantities must be greater than zero.");
		}
		return { name: String(name).trim(), quantity, unit: normalizeUnit(unit) };
	}

	function normalizeName(value) {
		const normalized = typeof normalizeIngredient === "function"
			? normalizeIngredient(value)
			: String(value || "").trim().toLowerCase().replace(/\s+/g, " ");
		return (normalized || String(value || "").trim().toLowerCase()).replace(/\s+/g, " ");
	}

	function unitGroup(unit) {
		const definition = unitDefinitions[unit];
		return definition ? definition.dimension : unit;
	}

	function unitFactor(unit) {
		const definition = unitDefinitions[unit];
		return definition ? definition.factor : 1;
	}

	function recipeIngredients(recipe) {
		const ingredients = recipe.ingredients && recipe.ingredients.length
			? recipe.ingredients
			: recipe.ing || recipe.ingredients || [];
		return Array.isArray(ingredients) ? ingredients : String(ingredients).split(",");
	}

	function ingredientKey(name, unit) {
		return normalizeName(name) + "|" + unitGroup(normalizeUnit(unit));
	}

	function buildFromMealPlan(plan, catalog, previousItems = [], pantryItems = [], excludedKeys = []) {
		const recipes = [...(catalog || []), ...R];
		const selectedIds = Object.keys(plan || {}).reduce((ids, dayName) => {
			const day = plan[dayName];
			if (day && typeof day === "object") ids.push.apply(ids, Object.keys(day).map(meal => day[meal]));
			return ids;
		}, [])
			.filter(id => id !== "" && id !== null && id !== undefined && id !== 0);
		const aggregates = new Map();

		selectedIds.forEach(id => {
			const recipe = recipes.find(item => String(item.id) === String(id));
			if (!recipe) return;

			recipeIngredients(recipe).forEach(rawIngredient => {
				const ingredient = parseIngredient(rawIngredient);
				const nameKey = normalizeName(ingredient.name);
				const group = unitGroup(ingredient.unit);
				const key = nameKey + "|" + group;
				if (excludedKeys.indexOf(key) !== -1) return;
				let aggregate = aggregates.get(key);

				if (!aggregate) {
					aggregate = {
						name: ingredient.name,
						unit: ingredient.unit,
						quantity: 0,
						baseQuantity: 0,
						nameKey,
						group
					};
					aggregates.set(key, aggregate);
				}

				aggregate.baseQuantity += ingredient.quantity * unitFactor(ingredient.unit);
			});
		});

		const generated = Array.from(aggregates.values()).reduce((items, aggregate) => {
			const availableQuantity = pantryItems.reduce((total, pantryItem) => {
				if (!pantryItem || normalizeName(pantryItem.name) !== aggregate.nameKey) return total;
				const pantryUnit = normalizeUnit(pantryItem.unit);
				if (unitGroup(pantryUnit) !== aggregate.group) return total;
				const pantryAmount = pantryItem.qty !== undefined && pantryItem.qty !== null
					? pantryItem.qty
					: pantryItem.quantity;
				const pantryQuantity = Number(pantryAmount);
				if (!Number.isFinite(pantryQuantity) || pantryQuantity <= 0) return total;
				return total + pantryQuantity * unitFactor(pantryUnit);
			}, 0);
			const neededBaseQuantity = aggregate.baseQuantity - availableQuantity;
			const previous = previousItems.find(item =>
				(item.source === "meal-plan" || item.source === "manual") &&
				normalizeName(item.name) === aggregate.nameKey &&
				unitGroup(normalizeUnit(item.unit)) === aggregate.group
			);
			const manualQuantityBase = previous
				? Number(previous.manualQuantityBase) || (previous.source === "manual"
					? Number(previous.quantity !== undefined ? previous.quantity : previous.qty) * unitFactor(normalizeUnit(previous.unit))
					: 0)
				: 0;
			const requiredBaseQuantity = Math.max(0, neededBaseQuantity) + manualQuantityBase;
			if (requiredBaseQuantity <= 0) return items;

			const quantity = Number((requiredBaseQuantity / unitFactor(aggregate.unit)).toFixed(3));
			items.push({
				id: previous ? previous.id : Date.now().toString() + Math.random().toString(36).slice(2, 7),
				name: previous ? previous.name : aggregate.name,
				quantity,
				unit: aggregate.unit,
				done: previous ? Boolean(previous.done) : false,
				source: "meal-plan",
				manualQuantityBase
			});
			return items;
		}, []);

		const plannedKeys = new Set(Array.from(aggregates.values()).map(aggregate => aggregate.nameKey + "|" + aggregate.group));
		previousItems.forEach(previous => {
			if (previous.source !== "meal-plan" || !previous.manualQuantityBase) return;
			const unit = normalizeUnit(previous.unit);
			const group = unitGroup(unit);
			const key = normalizeName(previous.name) + "|" + group;
			if (plannedKeys.has(key)) return;
			const quantity = Number((Number(previous.manualQuantityBase) / unitFactor(unit)).toFixed(3));
			if (quantity <= 0) return;
			generated.push({
				id: previous.id,
				name: previous.name,
				quantity,
				unit,
				done: Boolean(previous.done),
				source: "manual"
			});
		});
		return generated;
	}

	function formatQuantity(item) {
		const quantity = Number(item.quantity !== undefined && item.quantity !== null ? item.quantity : item.qty);
		if (!Number.isFinite(quantity) || quantity <= 0) return "";
		return quantity + " " + normalizeUnit(item.unit);
	}

	function resolveShoppingImage(item, imageMap, fallback) {
		if (item && typeof item.image === "string" && item.image) return item.image;
		if (item && typeof item.recipeImage === "string" && item.recipeImage) return item.recipeImage;
		const name = String(item && item.name || "").trim().toLowerCase();
		return imageMap[name] || fallback;
	}

	function createManualShoppingItem(name, rawQuantity, rawUnit) {
		const itemName = String(name || "").trim().replace(/\s+/g, " ");
		if (!itemName) return { error: "Enter an item name." };

		const unit = normalizeUnit(rawUnit);
		const supportedUnits = ["pcs", "g", "kg", "ml", "l", "cups"];
		if (supportedUnits.indexOf(unit) === -1) return { error: "Select a supported unit." };

		const quantityText = String(rawQuantity === undefined || rawQuantity === null ? "" : rawQuantity).trim();
		const quantity = Number(quantityText);
		if (!quantityText || !Number.isFinite(quantity) || quantity <= 0) {
			return { error: "Enter a quantity greater than zero." };
		}
		if (quantity > 99999) return { error: "Quantity cannot exceed 99999." };
		if (unit === "pcs" && !Number.isInteger(quantity)) {
			return { error: "Use a whole number for pieces (pcs)." };
		}
		if (unit !== "pcs" && Math.abs(quantity * 100 - Math.round(quantity * 100)) > 1e-8) {
			return { error: "Use no more than two decimal places." };
		}

		return {
			item: {
				id: Date.now().toString() + Math.random().toString(36).slice(2, 7),
				name: itemName,
				quantity,
				unit,
				done: false,
				source: "manual"
			}
		};
	}

	function addManualShoppingItem(items, name, rawQuantity, rawUnit) {
		const result = createManualShoppingItem(name, rawQuantity, rawUnit);
		if (result.error) return result;

		const uniqueItems = deduplicateShoppingItems(items);
		items.splice(0, items.length);
		items.push.apply(items, uniqueItems);
		const incoming = result.item;
		const incomingName = normalizeName(incoming.name);
		const incomingGroup = unitGroup(incoming.unit);
		const existing = items.find(item =>
			normalizeName(item.name) === incomingName &&
			unitGroup(normalizeUnit(item.unit)) === incomingGroup
		);
		if (!existing) {
			items.push(incoming);
			result.merged = false;
			return result;
		}

		const existingUnit = normalizeUnit(existing.unit);
		const existingQuantity = Number(existing.quantity !== undefined ? existing.quantity : existing.qty);
		const currentBaseQuantity = Number.isFinite(existingQuantity) && existingQuantity > 0
			? existingQuantity * unitFactor(existingUnit)
			: 0;
		const addedBaseQuantity = incoming.quantity * unitFactor(incoming.unit);
		const mergedQuantity = Number(((currentBaseQuantity + addedBaseQuantity) / unitFactor(existingUnit)).toFixed(3));
		if (mergedQuantity > 99999) {
			return { error: "Combined quantity cannot exceed 99999." };
		}
		if (existingUnit === "pcs" && !Number.isInteger(mergedQuantity)) {
			return { error: "Combined pieces must be a whole number." };
		}
		existing.quantity = mergedQuantity;
		existing.unit = existingUnit;
		if (existing.source === "meal-plan") {
			existing.manualQuantityBase = (Number(existing.manualQuantityBase) || 0) + addedBaseQuantity;
		}
		result.item = existing;
		result.merged = true;
		return result;
	}

	function deduplicateShoppingItems(items) {
		return items.reduce((unique, item) => {
			if (!item || !String(item.name || "").trim()) return unique;
			const nameKey = normalizeName(item.name);
			const itemUnit = normalizeUnit(item.unit);
			const group = unitGroup(itemUnit);
			const existing = unique.find(candidate =>
				normalizeName(candidate.name) === nameKey &&
				unitGroup(normalizeUnit(candidate.unit)) === group
			);
			if (!existing) {
				item.name = String(item.name).trim().replace(/\s+/g, " ");
				unique.push(item);
				return unique;
			}

			const existingUnit = normalizeUnit(existing.unit);
			const existingQuantity = Number(existing.quantity !== undefined ? existing.quantity : existing.qty);
			const itemQuantity = Number(item.quantity !== undefined ? item.quantity : item.qty);
			const existingBase = Number.isFinite(existingQuantity) && existingQuantity > 0
				? existingQuantity * unitFactor(existingUnit)
				: 0;
			const itemBase = Number.isFinite(itemQuantity) && itemQuantity > 0
				? itemQuantity * unitFactor(itemUnit)
				: 0;
			existing.quantity = Number(((existingBase + itemBase) / unitFactor(existingUnit)).toFixed(3));
			existing.unit = existingUnit;
			existing.name = String(existing.name).trim().replace(/\s+/g, " ");
			if (!existing.category && item.category) existing.category = item.category;
			if (!existing.image && item.image) existing.image = item.image;
			existing.done = Boolean(existing.done && item.done);

			const existingManualBase = Number(existing.manualQuantityBase)
				|| (existing.source === "manual" ? existingBase : 0);
			const itemManualBase = Number(item.manualQuantityBase)
				|| (item.source === "manual" ? itemBase : 0);
			const manualQuantityBase = existingManualBase + itemManualBase;
			if (existing.source === "meal-plan" || item.source === "meal-plan") {
				existing.source = "meal-plan";
				existing.manualQuantityBase = manualQuantityBase;
			} else if (manualQuantityBase) {
				existing.source = "manual";
			}
			return unique;
		}, []);
	}

	function toggleBoughtItem(items, id) {
		const item = items.find(entry => String(entry.id) === String(id));
		if (!item) return null;
		item.done = !item.done;
		return item;
	}

	function removeShoppingItem(items, id) {
		const index = items.findIndex(entry => String(entry.id) === String(id));
		if (index === -1) return null;
		return items.splice(index, 1)[0];
	}

	function confirmAndClearShoppingList(confirmClear, clearRequest) {
		if (!confirmClear()) return Promise.resolve(false);
		return Promise.resolve().then(clearRequest).then(() => true);
	}

	function validPantryCategory(value) {
		return global.VP.normalizePantryCategory(value);
	}

	function pantryCategory(name, preferredCategory) {
		const preferred = validPantryCategory(preferredCategory);
		if (preferred) return preferred;

		const item = normalizeName(name);
		if (/chicken|beef|pork|meat|fish|salmon|tuna|egg|prawn|maldive|dhal|lentil|gram|bean/.test(item)) return "Protein";
		if (/milk|cheese|yogurt|dairy|butter|cream|curd/.test(item)) return "Dairy";
		if (/banana|apple|fruit|coconut|papaya|mango|pineapple|lime|lemon|avocado/.test(item)) return "Fruits";
		if (/tomato|onion|garlic|ginger|vegetable|broccoli|carrot|potato|salad|spinach|pumpkin|brinjal|gourd|okra|cabbage|gotukola|mukunuwenna/.test(item)) return "Vegetables";
		if (/rice|bread|flour|grain|quinoa|pasta|oat|sugar|salt/.test(item)) return "Grains";
		if (/chili|turmeric|curry|pepper|cinnamon|cardamom|clove|oil|sauce|tea|coffee/.test(item)) return "Spices & sauces";
		return "Other";
	}

	function pantryQuantity(quantity, unit) {
		const normalizedUnit = normalizeUnit(unit);
		const supported = ["pcs", "g", "kg", "ml", "l", "cups"];
		const conversions = {
			item: { unit: "pcs", factor: 1 },
			pc: { unit: "pcs", factor: 1 },
			piece: { unit: "pcs", factor: 1 },
			pieces: { unit: "pcs", factor: 1 },
			oz: { unit: "g", factor: 28.349523125 },
			lb: { unit: "kg", factor: 0.45359237 },
			tsp: { unit: "ml", factor: 5 },
			tbsp: { unit: "ml", factor: 15 },
			cup: { unit: "cups", factor: 1 }
		};
		const conversion = conversions[normalizedUnit];
		const targetUnit = conversion ? conversion.unit : normalizedUnit;
		if (supported.indexOf(targetUnit) === -1) {
			return { error: `Cannot move ${normalizedUnit} to the pantry because that unit is not supported.` };
		}
		const amount = Number(quantity) * (conversion ? conversion.factor : 1);
		const roundedAmount = targetUnit === "pcs" ? amount : Number(amount.toFixed(2));
		if (!Number.isFinite(roundedAmount) || roundedAmount <= 0 || roundedAmount > 99999) {
			return { error: "The item quantity is outside the Pantry limits." };
		}
		if (targetUnit === "pcs" && !Number.isInteger(roundedAmount)) {
			return { error: "The Pantry requires a whole number for pieces." };
		}
		return { amount: roundedAmount, unit: targetUnit };
	}

	function validExpiryDate(expiryDate) {
		if (!expiryDate) return true;
		const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(expiryDate);
		if (!match) return false;
		const year = Number(match[1]), month = Number(match[2]), day = Number(match[3]);
		const date = new Date(Date.UTC(year, month - 1, day));
		return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
	}

	function moveBoughtItemsToPantry(shoppingItems, pantryItems, expiryDate = "") {
		const boughtItems = shoppingItems.filter(item => item.done);
		if (!boughtItems.length) return { error: "Mark items as bought before moving them to the Pantry." };
		if (!validExpiryDate(expiryDate)) return { error: "Enter a valid expiry date." };

		const nextPantry = pantryItems.map(item => {
			const copy = Object.assign({}, item);
			copy.shoppingIds = Array.isArray(item.shoppingIds) ? item.shoppingIds.slice() : [];
			return copy;
		});
		const movedIds = [];

		for (const shoppingItem of boughtItems) {
			const itemId = String(shoppingItem.id);
			const alreadyTransferred = nextPantry.some(item => item.shoppingIds.indexOf(itemId) !== -1);
			if (alreadyTransferred) {
				movedIds.push(itemId);
				continue;
			}

			const rawQuantity = shoppingItem.quantity !== undefined && shoppingItem.quantity !== null
				? shoppingItem.quantity
				: shoppingItem.qty !== undefined && shoppingItem.qty !== null ? shoppingItem.qty : 1;
			const converted = pantryQuantity(rawQuantity, shoppingItem.unit || "pcs");
			if (converted.error) return { error: `${shoppingItem.name}: ${converted.error}` };

			const category = pantryCategory(
				shoppingItem.name,
				validPantryCategory(shoppingItem.category) || shoppingItem.cat
			) || "Other";
			const itemExpiry = shoppingItem.expiry_date || shoppingItem.exp || expiryDate || "";
			if (!validExpiryDate(itemExpiry)) return { error: `${shoppingItem.name}: Enter a valid expiry date.` };
			const existing = nextPantry.find(item =>
				String(item.name || "").trim().toLowerCase() === String(shoppingItem.name || "").trim().toLowerCase() &&
				String(item.unit || "").trim().toLowerCase() === converted.unit
			);
			if (existing) {
				const amount = Number(existing.qty) + converted.amount;
				if (!Number.isFinite(amount) || amount > 99999 ||
					(converted.unit === "pcs" && !Number.isInteger(amount)) ||
					(converted.unit !== "pcs" && Math.abs(amount * 100 - Math.round(amount * 100)) > 1e-8)) {
					return { error: `${shoppingItem.name}: combined quantity exceeds Pantry limits.` };
				}
				existing.qty = amount;
				existing.cat = validPantryCategory(existing.cat || existing.category) || category;
				if (!existing.exp || (itemExpiry && itemExpiry < existing.exp)) existing.exp = itemExpiry;
				if (existing.shoppingIds.indexOf(itemId) === -1) existing.shoppingIds.push(itemId);
			} else {
				nextPantry.push({
					id: Date.now() + Math.random(),
					name: String(shoppingItem.name).trim(),
					cat: category,
					qty: converted.amount,
					unit: converted.unit,
					exp: itemExpiry,
					shoppingIds: [itemId]
				});
			}
			movedIds.push(itemId);
		}

		return { pantryItems: nextPantry, movedIds };
	}

	global.VPShopping = {
		buildFromMealPlan,
		formatQuantity,
		resolveShoppingImage,
		createManualShoppingItem,
		addManualShoppingItem,
		deduplicateShoppingItems,
		ingredientKey,
		toggleBoughtItem,
		removeShoppingItem,
		confirmAndClearShoppingList,
		moveBoughtItemsToPantry
	};
})(window);

const express = require("express");
const path = require("path");
const fs = require("fs");
const multer = require("multer");

const uploadDirectory = path.join(__dirname, "../vitaplate/assets/food");
fs.mkdirSync(uploadDirectory, { recursive: true });

const uploadStorage = multer.diskStorage({
  destination: (req, file, callback) => {
    callback(null, uploadDirectory);
  },
  filename: (req, file, callback) => {
    const extension = path.extname(file.originalname).toLowerCase();
    const uniqueName = `recipe-${Date.now()}-${Math.round(Math.random() * 1e9)}${extension}`;
    callback(null, uniqueName);
  },
});

const allowedImageExtensions = {
  "image/jpeg": [".jpg", ".jpeg"],
  "image/png": [".png"],
  "image/webp": [".webp"],
};

const upload = multer({
  storage: uploadStorage,
  limits: { fileSize: 5 * 1024 * 1024 },
  fileFilter: (req, file, callback) => {
    const extension = path.extname(file.originalname).toLowerCase();
    const validExtensions = allowedImageExtensions[file.mimetype] || [];
    if (validExtensions.includes(extension)) {
      callback(null, true);
    } else {
      callback(new Error("Choose a JPG, PNG, or WebP image."));
    }
  },
});
const app = express();
app.use((req, res, next) => {
  res.setHeader("Access-Control-Allow-Origin", "http://127.0.0.1:5000");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (req.method === "OPTIONS") return res.sendStatus(204);
  next();
});
app.use(express.static(path.join(__dirname, "../vitaplate")));
app.use(express.json());

const PORT = 3000;

const recipes = [
  {
    id: 1,
    name: "Chickpea Salad Bowl",
    ingredients: ["chickpeas", "cucumber", "tomato", "lemon"],
    instructions: "Mix the ingredients in a bowl and season with lemon.",
    image: "/assets/food/api-chickpea-salad.jpg",
  },
  {
    id: 2,
    name: "Spinach Omelette",
    ingredients: ["eggs", "spinach", "onion"],
    instructions: "Cook the onion and spinach, add beaten eggs, and cook until set.",
    image: "/assets/food/api-spinach-omelette.jpg",
  },
  {
    id: 3,
    name: "Mango Yogurt Bowl",
    ingredients: ["mango", "yogurt", "honey"],
    instructions: "Mix the mango and yogurt, then drizzle with honey.",
    image: "/assets/food/api-mango-yogurt.jpg",
  },
  {
    id: 4,
    name: "Chicken Quinoa Bowl",
    ingredients: ["chicken", "quinoa", "spinach", "lemon"],
    instructions: "Cook the quinoa and chicken, then serve with spinach and lemon.",
    image: "/assets/food/chicken-quinoa.jpg",
  },
  {
    id: 5,
    name: "Baked Salmon with Vegetables",
    ingredients: ["salmon", "broccoli", "lemon", "olive oil"],
    instructions: "Bake the salmon and broccoli with olive oil and lemon until cooked.",
    image: "/assets/food/baked-salmon.jpg",
  },
  {
    id: 6,
    name: "Lentil Vegetable Soup",
    ingredients: ["lentils", "carrot", "onion", "vegetable broth"],
    instructions: "Simmer the lentils and vegetables in broth until tender.",
    image: "/assets/food/lentil-soup.jpg",
  },
  {
  id: 7,
  name: "Vegetable Rice Bowl",
  ingredients: ["rice", "carrot", "peas"],
  instructions: "Cook the rice and vegetables, then serve together.",
  image: "/assets/food/vegetable-rice.jpeg",
},
];

app.get("/api/recipes", (req, res) => {
  res.json(recipes);
});

app.post("/api/recipes", upload.single("imageFile"), (req, res) => {
  const body = req.body || {};
  const name = typeof body.name === "string" ? body.name.trim() : "";
  const ingredients = typeof body.ingredients === "string"
    ? body.ingredients.split(",").map(item => item.trim()).filter(Boolean)
    : [];
  const instructions = typeof body.instructions === "string" ? body.instructions.trim() : "";

  if (!name || ingredients.length === 0 || !instructions || !req.file) {
    return res.status(400).json({
      error: "Add a name, at least one ingredient, instructions, and a photo.",
    });
  }

  const newRecipe = {
    id: Math.max(0, ...recipes.map(recipe => recipe.id)) + 1,
    name,
    ingredients,
    instructions,
    image: `/assets/food/${req.file.filename}`,
  };

  recipes.push(newRecipe);
  res.status(201).json(newRecipe);
});

app.use((error, req, res, next) => {
  const message = error.message || "Photo upload failed.";
  const status = error instanceof multer.MulterError ? 400 : 400;
  res.status(status).json({
    error: error.code === "LIMIT_FILE_SIZE" ? "Choose a photo smaller than 5 MB." : message,
  });
});
app.listen(PORT, () => {
  console.log(`Recipe API is running at http://localhost:${PORT}`);
});



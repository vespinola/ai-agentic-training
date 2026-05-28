const express = require("express");

const app = express();
app.use(express.json());

const users = [
  { id: 1, name: "Ada Lovelace", role: "engineer" },
  { id: 2, name: "Grace Hopper", role: "admiral" }
];

app.get("/health", (req, res) => {
  res.json({ status: "ok", framework: "express" });
});

app.get("/users", (req, res) => {
  res.json({ items: users, count: users.length });
});

app.get("/users/:id", (req, res) => {
  const userId = Number(req.params.id);
  const user = users.find((item) => item.id === userId);

  if (!user) {
    return res.status(404).json({ error: "User not found" });
  }

  return res.json(user);
});

app.post("/users", (req, res) => {
  const name = String(req.body.name || "").trim();
  const role = String(req.body.role || "").trim();

  if (!name || !role) {
    return res.status(400).json({ error: "name and role are required" });
  }

  const newUser = {
    id: users.length + 1,
    name,
    role
  };

  users.push(newUser);
  return res.status(201).json(newUser);
});

app.listen(3000, () => {
  console.log("Express app listening on port 3000");
});

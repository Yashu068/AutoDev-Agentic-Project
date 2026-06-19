const express = require('express');
const cors = require('cors');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 5000;

// Middleware
app.use(cors());
app.use(express.json());

// In-memory storage for tasks
let tasks = [];
let taskIdCounter = 1;

// Helper function to find task by ID
const findTaskById = (id) => {
  return tasks.find(task => task.id === parseInt(id));
};

// Helper function to find task index by ID
const findTaskIndexById = (id) => {
  return tasks.findIndex(task => task.id === parseInt(id));
};

// GET /api/tasks - Retrieve all tasks
const getTodos = (req, res) => {
  res.json(tasks);
};

// POST /api/tasks - Create a new task
const createTodo = (req, res) => {
  const { text } = req.body;
  
  if (!text || text.trim() === '') {
    return res.status(400).json({ error: 'Task text is required' });
  }
  
  const newTask = {
    id: taskIdCounter++,
    text: text.trim(),
    completed: false,
    createdAt: new Date().toISOString()
  };
  
  tasks.push(newTask);
  res.status(201).json(newTask);
};

// PUT /api/tasks/:id - Update a task
const updateTodo = (req, res) => {
  const { id } = req.params;
  const { text, completed } = req.body;
  
  const taskIndex = findTaskIndexById(id);
  
  if (taskIndex === -1) {
    return res.status(404).json({ error: 'Task not found' });
  }
  
  if (text !== undefined) {
    if (text.trim() === '') {
      return res.status(400).json({ error: 'Task text cannot be empty' });
    }
    tasks[taskIndex].text = text.trim();
  }
  
  if (completed !== undefined) {
    tasks[taskIndex].completed = completed;
  }
  
  tasks[taskIndex].updatedAt = new Date().toISOString();
  
  res.json(tasks[taskIndex]);
};

// DELETE /api/tasks/:id - Delete a task
const deleteTodo = (req, res) => {
  const { id } = req.params;
  
  const taskIndex = findTaskIndexById(id);
  
  if (taskIndex === -1) {
    return res.status(404).json({ error: 'Task not found' });
  }
  
  const deletedTask = tasks.splice(taskIndex, 1)[0];
  res.json(deletedTask);
};

// Start server function
const startServer = () => {
  app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
  });
};

// API Routes
app.get('/api/tasks', getTodos);
app.post('/api/tasks', createTodo);
app.put('/api/tasks/:id', updateTodo);
app.delete('/api/tasks/:id', deleteTodo);

// Start the server
startServer();

module.exports = { app, getTodos, createTodo, updateTodo, deleteTodo };
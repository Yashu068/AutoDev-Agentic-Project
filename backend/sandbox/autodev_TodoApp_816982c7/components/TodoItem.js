import { useState } from 'react';
import { updateTask, deleteTask } from '../lib/api';
import TodoForm from './TodoForm';

export default function TodoItem({ task, onUpdate, onDelete }) {
  const [isEditing, setIsEditing] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleToggle = async () => {
    try {
      const updatedTask = await updateTask(task.id, { completed: !task.completed });
      onUpdate(updatedTask);
    } catch (error) {
      console.error('Error toggling task completion:', error);
    }
  };

  const handleDelete = async () => {
    if (window.confirm('Are you sure you want to delete this task?')) {
      setIsDeleting(true);
      try {
        await deleteTask(task.id);
        onDelete(task.id);
      } catch (error) {
        console.error('Error deleting task:', error);
        setIsDeleting(false);
      }
    }
  };

  const handleEditSave = (updatedTask) => {
    setIsEditing(false);
    onUpdate(updatedTask);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
  };

  if (isEditing) {
    return (
      <div className="todo-item editing">
        <TodoForm 
          task={task} 
          onSuccess={handleEditSave} 
          onCancel={handleCancelEdit} 
        />
      </div>
    );
  }

  return (
    <div className={`todo-item ${task.completed ? 'completed' : ''}`}>
      <div className="todo-content">
        <input
          type="checkbox"
          checked={task.completed}
          onChange={handleToggle}
          className="todo-checkbox"
        />
        <span className="todo-text">{task.text}</span>
      </div>
      <div className="todo-actions">
        <button
          onClick={() => setIsEditing(true)}
          className="todo-edit-btn"
          disabled={isDeleting}
        >
          Edit
        </button>
        <button
          onClick={handleDelete}
          disabled={isDeleting}
          className="todo-delete-btn"
        >
          {isDeleting ? 'Deleting...' : 'Delete'}
        </button>
      </div>
    </div>
  );
}
import { useState, useEffect } from 'react';
import { createTask, updateTask } from '../lib/api';

export default function TodoForm({ task, onSuccess, onCancel }) {
  const [text, setText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (task) {
      setText(task.text);
    } else {
      setText('');
    }
  }, [task]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!text.trim()) {
      return;
    }
    
    setIsSubmitting(true);
    
    try {
      if (task) {
        await updateTask(task.id, { text: text.trim() });
      } else {
        await createTask({ text: text.trim() });
      }
      
      setText('');
      onSuccess();
    } catch (error) {
      console.error('Error saving task:', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => {
    setText('');
    if (onCancel) {
      onCancel();
    }
  };

  return (
    <form onSubmit={handleSubmit} className="todo-form">
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={task ? "Edit task..." : "Add a new task..."}
        disabled={isSubmitting}
        className="todo-input"
      />
      <button 
        type="submit" 
        disabled={isSubmitting || !text.trim()}
        className="todo-submit-btn"
      >
        {task ? 'Update' : 'Add'}
      </button>
      {task && onCancel && (
        <button 
          type="button" 
          onClick={handleCancel}
          disabled={isSubmitting}
          className="todo-cancel-btn"
        >
          Cancel
        </button>
      )}
    </form>
  );
}
import TodoItem from './TodoItem';

export default function TodoList({ tasks, onUpdate, onDelete }) {
  if (!tasks || tasks.length === 0) {
    return (
      <div className="todo-list empty">
        <p className="empty-message">No tasks yet. Add your first task above!</p>
      </div>
    );
  }

  return (
    <div className="todo-list">
      {tasks.map((task) => (
        <TodoItem
          key={task.id}
          task={task}
          onUpdate={onUpdate}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}
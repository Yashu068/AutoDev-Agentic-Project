# TodoApp

A simple TODO application that allows users to add, delete, update, and mark tasks as completed, with data persisted via a Node.js Express API and optional localStorage fallback.

## Features

- **Create Tasks**: Add new tasks to your todo list
- **Read Tasks**: View all your tasks in a clean, organized list
- **Update Tasks**: Edit existing tasks to modify their content
- **Delete Tasks**: Remove tasks you no longer need
- **Toggle Completion**: Mark tasks as completed or incomplete
- **Data Persistence**: Tasks are stored on the backend server with localStorage fallback

## Tech Stack

- **Backend**: Node.js, Express.js
- **Frontend**: React.js, Next.js
- **Other**: localStorage for client-side data persistence

## Prerequisites

- Node.js (v14 or higher)
- npm or yarn

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd todoapp
```

2. Install dependencies:
```bash
npm install
```

3. Set up environment variables:
```bash
cp .env.example .env
```
Edit the `.env` file to configure your environment (e.g., PORT).

## Usage

### Development Mode

Run both the Next.js frontend and Express backend:

```bash
npm run dev
```

This will start the Next.js development server on `http://localhost:3000`.

To run the Express server separately:
```bash
npm run server:dev
```

### Production Mode

Build and start the application:

```bash
npm run build
npm start
```

## API Endpoints

The Express backend provides the following RESTful endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tasks` | Retrieve all tasks |
| POST | `/api/tasks` | Create a new task |
| PUT | `/api/tasks/:id` | Update a task |
| DELETE | `/api/tasks/:id` | Delete a task |

## Project Structure

```
todoapp/
├── components/
│   ├── TodoForm.js    # Form for adding/editing tasks
│   ├── TodoItem.js    # Individual task component
│   └── TodoList.js    # Task list container
├── lib/
│   └── api.js         # API utility functions
├── pages/
│   ├── _app.js        # Custom App component
│   └── index.js       # Main page
├── server.js          # Express server
├── package.json
├── next.config.js
├── .env.example
└── README.md
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes and commit them: `git commit -m 'Add some feature'`
4. Push to the branch: `git push origin feature/your-feature-name`
5. Submit a pull request

## License

This project is licensed under the MIT License.
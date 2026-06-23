const canvas = document.getElementById('game-canvas');
const ctx = canvas.getContext('2d');
let snake = [];
let direction = 'RIGHT';
let food = null;
let score = 0;
let gameOver = false;
let intervalId = null;

function initGame() {
    snake = [
        { x: 200, y: 200 },
        { x: 220, y: 200 },
        { x: 240, y: 200 }
    ];
    direction = 'RIGHT';
    food = generateFood();
    score = 0;
    gameOver = false;
    intervalId = setInterval(updateGame, 100);
}

function generateFood() {
    let x = Math.floor(Math.random() * (canvas.width / 20)) * 20;
    let y = Math.floor(Math.random() * (canvas.height / 20)) * 20;
    return { x, y };
}

function updateGame() {
    if (gameOver) {
        clearInterval(intervalId);
        return;
    }
    updateSnake();
    checkCollision();
    drawGame();
}

function updateSnake() {
    let head = snake[snake.length - 1];
    let newHead = null;
    if (direction === 'RIGHT') {
        newHead = { x: head.x + 20, y: head.y };
    } else if (direction === 'LEFT') {
        newHead = { x: head.x - 20, y: head.y };
    } else if (direction === 'UP') {
        newHead = { x: head.x, y: head.y - 20 };
    } else if (direction === 'DOWN') {
        newHead = { x: head.x, y: head.y + 20 };
    }
    snake.push(newHead);
    if (newHead.x === food.x && newHead.y === food.y) {
        score++;
        food = generateFood();
    } else {
        snake.shift();
    }
}

function checkCollision() {
    let head = snake[snake.length - 1];
    if (head.x < 0 || head.x >= canvas.width || head.y < 0 || head.y >= canvas.height) {
        gameOver = true;
    }
    for (let i = 0; i < snake.length - 1; i++) {
        if (head.x === snake[i].x && head.y === snake[i].y) {
            gameOver = true;
            break;
        }
    }
}

function drawGame() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = 'black';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = 'green';
    for (let i = 0; i < snake.length; i++) {
        ctx.fillRect(snake[i].x, snake[i].y, 20, 20);
    }
    ctx.fillStyle = 'red';
    ctx.fillRect(food.x, food.y, 20, 20);
    ctx.fillStyle = 'white';
    ctx.font = '24px Arial';
    ctx.textAlign = 'left';
    ctx.textBaseline = 'top';
    ctx.fillText(`Score: ${score}`, 10, 10);
    if (gameOver) {
        ctx.font = '48px Arial';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('Game Over', canvas.width / 2, canvas.height / 2);
    }
}

function handleKeyPress(event) {
    if (event.key === 'ArrowRight' && direction !== 'LEFT') {
        direction = 'RIGHT';
    } else if (event.key === 'ArrowLeft' && direction !== 'RIGHT') {
        direction = 'LEFT';
    } else if (event.key === 'ArrowUp' && direction !== 'DOWN') {
        direction = 'UP';
    } else if (event.key === 'ArrowDown' && direction !== 'UP') {
        direction = 'DOWN';
    }
}

document.addEventListener('keydown', handleKeyPress);
initGame();
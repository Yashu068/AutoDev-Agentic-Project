FROM python:3.9-slim

# Set working directory to /app
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port 8000 for the game
EXPOSE 8000

# Run the command to start the game when the container launches
CMD ["python", "main.py"]
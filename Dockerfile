# -----------------------------------
# Stage 1: Base image
# -----------------------------------
FROM python:3.11-slim

# Prevent Python from writing pyc files to disk & buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# -----------------------------------
# Stage 2: Working directory setup
# -----------------------------------
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .

# Install dependencies (use no-cache to keep image small)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# -----------------------------------
# Stage 3: Environment setup
# -----------------------------------
# Flask env vars
ENV FLASK_APP=app.py
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_ENV=production

# Expose port 5000 for Flask
EXPOSE 5000

# -----------------------------------
# Stage 4: Run the app
# -----------------------------------
CMD ["python", "app.py"]

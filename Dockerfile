# --- Base image ---
FROM python:3.12-slim

# --- Set working directory ---
WORKDIR /app

# --- Copy project files ---
COPY . .

# --- Install dependencies ---
RUN pip install --no-cache-dir -r requirements.txt

# --- Expose Flask port ---
EXPOSE 2000

# --- Run Flask app ---
CMD ["python", "app.py"]

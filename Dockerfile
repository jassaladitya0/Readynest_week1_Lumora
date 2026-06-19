# Use official lightweight Python image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY lumora/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY lumora/ .

# Create uploads and outputs directories and set full permissions (needed for Hugging Face UID 1000)
RUN mkdir -p uploads outputs && chmod -R 777 uploads outputs

# Expose the port Hugging Face expects
EXPOSE 7860

# Run the Flask app with gunicorn on port 7860
CMD ["gunicorn", "-b", "0.0.0.0:7860", "--workers", "2", "app:app"]

FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set environment variable to ensure prints are flushed instantly
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies as root
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files
COPY . .

# Change ownership of the folder to user 1000 so Hugging Face can write screenshots to it!
RUN chown -R 1000:1000 /app

# Switch to the Hugging Face restricted user
USER 1000

# Expose the required Hugging Face port
EXPOSE 7860

# Start Xvfb in the background and run the Flask app directly
CMD ["/bin/sh", "-c", "Xvfb :99 -screen 0 1280x1024x24 -ac +extension GLX +render -noreset & export DISPLAY=:99 && python main.py"]

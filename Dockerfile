# Dockerfile
# Use a Python base image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot code
COPY Task_Pilot.py .

# Command to run the bot when the container starts
CMD ["python", "Task_Pilot.py"]
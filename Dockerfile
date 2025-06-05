FROM python:3.10-slim

WORKDIR /usr/src/app

# Install system dependencies that might be needed by some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /usr/src/app
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
# Using --no-cache-dir to reduce image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container at /usr/src/app
COPY ./app ./app

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variable for the port (optional, Uvicorn default is 8000)
ENV PORT 8000

# Run app.main:app when the container launches
# Use 0.0.0.0 to make it accessible from outside the container
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

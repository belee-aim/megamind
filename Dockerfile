# Use a specific version of Python for reproducibility
FROM python:3.12-slim as builder

# Set the working directory
WORKDIR /usr/src/app

# Create a temporary directory for pip to use, if it doesn't exist
RUN mkdir -p /tmp

# Install pip-tools
RUN pip install --no-cache-dir pip-tools

# Copy project definition files
COPY pyproject.toml poetry.lock README.md ./

# Compile requirements.txt from pyproject.toml
RUN pip-compile --output-file=requirements.txt pyproject.toml

# Install the compiled requirements
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source code
COPY ./src .

# Install the project itself in editable mode
RUN pip install -e .

# Final stage
FROM python:3.12-slim

# Create a non-root user
RUN addgroup --system app && adduser --system --group app

# Set the working directory
WORKDIR /home/app

# Copy installed packages from the builder stage
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY --from=builder /usr/src/app /home/app

# Set ownership for the app user
RUN chown -R app:app /home/app

# Switch to the non-root user
USER app

# Expose the port the app runs on
EXPOSE 8000

# Run the application
CMD ["uvicorn", "megamind.main:app", "--host", "0.0.0.0", "--port", "8000"]

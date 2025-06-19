# Use a specific version of Python for reproducibility
FROM python:3.11-slim as builder

# Set the working directory
WORKDIR /usr/src/app

# Install poetry
RUN pip install --no-cache-dir poetry

# Configure poetry to not create a virtual environment
RUN poetry config virtualenvs.create false

# Copy only the dependency files to leverage Docker cache
COPY pyproject.toml poetry.lock README.md ./

# Install dependencies, caching the results
RUN --mount=type=cache,target=/root/.cache/pypoetry poetry install --no-interaction --no-ansi --no-root

# Copy the rest of the application code
COPY ./src .

# Final stage
FROM python:3.11-slim

# Create a non-root user
RUN addgroup --system app && adduser --system --group app

# Set the working directory
WORKDIR /home/app

# Copy installed packages and executables from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the application code from the builder stage
COPY --from=builder /usr/src/app /home/app

# Set ownership for the app user
RUN chown -R app:app /home/app

# Switch to the non-root user
USER app

# Expose the port the app runs on
EXPOSE 8000

# Run the application
CMD ["uvicorn", "megamind.main:app", "--host", "0.0.0.0", "--port", "8000"]

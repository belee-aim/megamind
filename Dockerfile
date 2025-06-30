# Use a specific version of Python for reproducibility
FROM python:3.12-slim as builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set the working directory
WORKDIR /app

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project 

# Copy the application source code
COPY pyproject.toml uv.lock /app/
COPY src/ /app/src

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# Final stage
FROM python:3.12-slim

# Create a non-root user
RUN addgroup --system app && adduser --system --group app

# Set the working directory
WORKDIR /app

# Copy installed packages from the builder stage
# Copy the environment, but not the source code
COPY --from=builder --chown=app:app /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

# Copy the application source code
COPY --from=builder --chown=app:app /app/src /app/src

# Switch to the non-root user
USER app

# Expose the port the app runs on
EXPOSE 8000

# Run the application
CMD ["uvicorn", "src.megamind.main:app", "--host", "0.0.0.0", "--port", "8000"]

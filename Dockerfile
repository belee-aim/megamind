# Use a specific version of Python for reproducibility
FROM python:3.12-slim as builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

###############################################################
# Install git and ssh client
RUN apt-get update && apt-get install -y openssh-client git

# Set up SSH to trust the Git provider's host key automatically
# This prevents interactive prompts that would break the build
RUN mkdir -p -m 0700 ~/.ssh && \
    ssh-keyscan github.com >> ~/.ssh/known_hosts
###############################################################

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
# Clone the frappe_mcp_server repository
RUN --mount=type=ssh,id=default \
    git clone git@github.com:AIMlink-team/frappe_mcp_server.git /app/frappe_mcp_server

# Install Node.js and npm
RUN apt-get update && apt-get install -y nodejs npm

# Install dependencies for frappe_mcp_server && build the project
RUN cd /app/frappe_mcp_server && npm install && npm run build

# Sync the project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked

# Final stage
FROM python:3.12-slim

# Install Node.js and npm
RUN apt-get update && apt-get install -y nodejs npm

# Create a non-root user
RUN addgroup --system app && adduser --system --group app

# Set the working directory
WORKDIR /app

# Copy installed packages from the builder stage
# Copy the environment, but not the source code
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/frappe_mcp_server /app/frappe_mcp_server


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

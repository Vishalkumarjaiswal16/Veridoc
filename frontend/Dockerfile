# Use a slim Node image
FROM node:20-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install pnpm
RUN npm install -g pnpm

# Set working directory
WORKDIR /app

# Copy dependency files
COPY package.json pnpm-lock.yaml ./

# Install dependencies
RUN pnpm install

# Copy the rest of the application
COPY . .

# Expose the Vite port
EXPOSE 5173

# Run the development server
# --host 0.0.0.0 is required for access from outside the container
CMD ["pnpm", "dev", "--host", "0.0.0.0"]

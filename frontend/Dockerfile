# --- Stage 1: Build ---
FROM node:20-slim AS build

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

# Build the application
# Note: VITE_ variables must be present at build time
RUN pnpm build

# --- Stage 2: Runtime ---
FROM nginx:stable-alpine

# Copy the built assets from the build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy the custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]

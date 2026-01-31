# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# Build-time envs for Vite
ARG VITE_API_URL
ARG VITE_MAX_FILE_SIZE
ARG VITE_ALLOWED_FILE_TYPES
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_MAX_FILE_SIZE=$VITE_MAX_FILE_SIZE
ENV VITE_ALLOWED_FILE_TYPES=$VITE_ALLOWED_FILE_TYPES

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code 
COPY . .

# Build the app
RUN npm run build

# Stage 2: Production with Nginx
FROM nginx:1.27-alpine

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

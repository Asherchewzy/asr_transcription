# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# buildtime envs for Vite
ARG VITE_API_URL
ARG VITE_MAX_FILE_SIZE
ARG VITE_ALLOWED_FILE_TYPES
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_MAX_FILE_SIZE=$VITE_MAX_FILE_SIZE
ENV VITE_ALLOWED_FILE_TYPES=$VITE_ALLOWED_FILE_TYPES

COPY package*.json ./

# install dependencies
RUN npm ci

# cp source code
COPY . .

# Build the app
RUN npm run build

# Stage 2: Production with Nginx
FROM nginx:1.27-alpine

# copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

#nginx
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

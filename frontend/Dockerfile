# FRONTEND DOCKERFILE
# Project: Research Assistant
# File: frontend/Dockerfile
#
# Builds the Node.js environment for the Next.js React application.

FROM node:20-alpine

# Set work directory
WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm install

# Copy project files
COPY . .

# Build the application
RUN npm run build

# Expose port
EXPOSE 3000

# Start the application
CMD ["npm", "run", "start"]

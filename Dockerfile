FROM node:20-slim

# Install Python 3
RUN apt-get update && apt-get install -y python3 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy entire project (Python engine + Node extension)
COPY .. /app/

# Install Node dependencies
WORKDIR /app/copilot-extension
RUN npm install --production

# Expose port
EXPOSE 3000

# Start the extension server
CMD ["node", "server.js"]

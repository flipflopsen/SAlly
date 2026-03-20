FROM node:20-alpine3.19 AS scada-builder

# Install libraries from package-lock.json
WORKDIR /app
COPY package.json .
COPY package-lock.json .
RUN mkdir backend
RUN mkdir frontend
COPY backend/package.json backend
COPY frontend/package.json frontend
# Using ci instead of install because we want to install
# from package-lock.json instead of package.json
RUN npm ci --include=dev

COPY . .

RUN npm run build
CMD ["npm", "start"]

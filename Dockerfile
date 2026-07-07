# Binance TR Coin Bot - uretim imaji
FROM node:22-alpine

WORKDIR /app
COPY package.json ./
COPY src ./src

# Kok olmayan kullanici: guvenlik icin zorunlu pratik
RUN mkdir -p data logs && chown -R node:node /app
USER node

# Durum ve loglar volume ile kalici tutulmali (docker-compose.yml'e bakin)
VOLUME ["/app/data", "/app/logs"]

CMD ["node", "src/index.js"]
